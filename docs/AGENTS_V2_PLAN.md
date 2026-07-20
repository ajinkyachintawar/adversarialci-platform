# Agents V2 — End-to-End Build Plan

Decided 2026-07-20 after architecture debate. Principle: **one engine, three heads** —
shared evidence + claims layers are mode-blind; buyer/seller/analyst are thin heads
(one synthesis prompt + one output schema + one renderer each). The adversarial debate
survives only where it earns: buyer (2-round debate), seller (1-round red-team),
analyst (no debate). Verdict JSON is the single source of truth; the ASCII/regex
report layer gets deleted at the end.

Foundation already shipped (commit 2bd015a): `ingest/` evidence layer — Firecrawl,
chunker, dedup+staleness store, Gemini embeddings (768d, key rotation),
`retrieve(query, company, k)` with hard company filter, golden retrieval eval
(16/16 hit@1). Refresh endpoint feeds both old bullet and new RAG pipelines.

Models: llama-3.1-8b-instant extracts/diffs (cheap), llama-3.3-70b-versatile
synthesizes/judges. Groq 6K TPM is the binding constraint → token budgeter, not
parallelism.

---

## Phase 1 — Claims engine + citation gate  (the trust core)

New package `claims/`:

- `claims/extractor.py` — for each company × dimension:
  `retrieve(dimension_query(dim, company), company, k=6)` → 8B call returns JSON:
  `[{dimension, claim, stance: "strength"|"weakness", evidence_ids: [chunk content_hash], strength: 1-5}]`
  Schema-validated (pydantic); one re-ask on malformed output, then drop.
  Dimension queries come from verticals config (reuse dimension names; write one
  natural-language query template per dimension).
- `claims/gate.py` — deterministic, no LLM: resolve every `evidence_id` against
  `rag_chunks`; claim with any unresolvable id → dropped + counted. Output:
  verified claims, each carrying resolved `source_url`s.
- Store on the session doc: `claims: {company: [verified claims]}` + gate metrics
  (`claims_total, claims_dropped_uncited`).
- Eval: `eval/claims_eval.py` — % claims surviving the gate, % dimensions with ≥1
  claim per company; JSON to `eval/results/`.

Acceptance: run for MongoDB vs Pinecone vs Weaviate; ≥90% claims survive gate;
every dimension populated for registry vendors; zero unresolvable citations in
stored output.

Kills: `court/argument_builder.py` keyword routing (`route_bullet_to_dimension`,
SOURCE_PRIORITY weighting) — source priority becomes a rank feature inside
retrieval/extraction, not a gatekeeper.

## Phase 2 — Mode heads on JSON verdicts + consistency checker

New `heads/` package; all heads consume verified claims only.

- `heads/schemas.py` — pydantic verdict schemas:
  - BuyerVerdict: `{winner, confidence, per_dimension: [{dimension, winner, reason, evidence_ids}], summary, caveats}`
  - SellerVerdict: `{win_probability, advantages[], vulnerabilities[], objections[{objection, response, evidence_ids}], landmines[], talk_tracks[], do_not_say[]}` — every list item cites evidence_ids
  - AnalystVerdict: `{matrix: {company: {dimension: {score, reason, evidence_ids}}}, summary}`
- `heads/buyer.py` — 2-round debate (advocate JSON claims-picks + rebuttal), then
  70B judge over claims+full cited chunks → BuyerVerdict.
- `heads/seller.py` — red-team: competitor advocate attacks `my_company` with cited
  claims (→ objections/landmines), our advocate counters (→ talk_tracks/responses),
  70B synthesizes → SellerVerdict.
- `heads/analyst.py` — single 70B scoring pass → AnalystVerdict. No debate.
- `heads/consistency.py` — deterministic checks: priority dimension winner matches
  summary; confidence matches formula; dimensions-won count matches favorite;
  every evidence_id resolves. On failure → one judge re-ask quoting the
  contradiction; still failing → verdict flagged `inconsistent: true`, surfaced in UI.
- Persistence: `verdict_json` field on court_sessions; keep old fields during
  transition. `pipeline/court_session.py` routes to heads; old `court/judge.py`
  parse path stays behind a flag until Phase 4 proves parity.
- UI: `ReportView.tsx` renders from `verdict_json` when present (typed, no parsing);
  falls back to reportParser for old sessions. Citation chips link to source_url,
  hover shows chunk text (`/api/chunks/{hash}` endpoint).

Acceptance: one real session per mode end-to-end in UI with clickable citations;
consistency checker passes or visibly flags; Meridian-class bugs (priority-dim
mismatch, truncation) structurally impossible (assert in tests).

## Phase 3 — Jobs + checkpointed worker + token budgeter

- `jobs/` — Mongo `jobs` collection: `{_id, type, payload, status, stage,
  checkpoints: {stage: output_ref}, log: [...], created/updated_at}`.
- Worker = background thread in the API process (ponytail: same dyno, $0;
  upgrade path = move loop to separate Render service, interface unchanged).
  Stages checkpoint after: ingest → claims → debate → verdict → render. Restart
  resumes from last checkpoint instead of dying.
- SSE endpoints tail the job doc (poll ~1s) instead of in-memory queues — also
  fixes multi-instance later.
- `jobs/budget.py` — token estimator (chars/4) per pending call; scheduler sleeps
  to keep rolling 60s window under 5,500 TPM (Groq 6K cap with headroom).
  Metrics per session: tokens used, wait time, wall time → stored on job.

Acceptance: kill -9 the server mid-session → job resumes and completes; a full
seller session completes with zero 429s; wall time ≤ 2min recorded honestly.

## Phase 4 — Golden verdict set + prompt A/B  (CV bullet 9 becomes true)

- `eval/golden_verdicts.json` — ~10 sessions with expected outcomes (seed from the
  87.9% ground-truth set + the Meridian test case).
- `eval/verdict_eval.py` — per prompt version: accuracy vs expected winner,
  citation-resolution rate, consistency-pass rate, stability (same input 3 runs →
  same winner?). JSON to `eval/results/`.
- Prompts move to `prompts/` as versioned files (`buyer_judge_v1.txt`, `v2`…);
  session records prompt version used (audit trail).
- A/B runner: `eval/ab_prompts.py --head buyer --a v1 --b v2` → table committed to
  `eval/results/ab_*.json`. Run at least one real A/B (e.g., judge with vs without
  explicit "cite or drop" instruction) and keep the numbers.
- Retire old parse path once new heads beat/match old pipeline on the golden set.
  Delete `parse_verdict` regex layer + `reportParser.ts` extractors.

Acceptance: one committed A/B result with a decision taken from it; golden verdict
suite runs in one command; old regex layer deleted.

## Phase 5 — Change rail + Slack watchlist  (retention feature)

- `watch/` — `watchlists` collection: `{user/org, companies[], slack_webhook_url,
  cadence}`.
- Scheduler (in-process, e.g. schedule lib or simple loop; Render cron alt):
  weekly per watched vendor → enqueue refresh job (Phase 3 infra).
- Diff detection: refresh already marks superseded docs. `watch/differ.py` — for
  each superseded→new doc pair: 8B summarizes the change with citations
  ("Pinecone removed $300 trial credits — pricing page, 2026-07-18").
- Delivery: Slack incoming-webhook message per watchlist digest; battlecards
  referencing changed evidence marked `stale: true` in UI with "regenerate" CTA.
- UI: minimal watchlist page (pick vendors, paste webhook URL, cadence).

Acceptance: seeded watchlist + forced content change → Slack message with correct
cited diff; stale battlecard flag appears and clears on regenerate.

---

## Cross-cutting rules

- Measure everything: every phase adds its metrics to Mongo + `eval/results/` JSON
  (same discipline as loadtest/ and ingest).
- Nothing merges without its eval gate green; golden retrieval eval re-run after
  any retrieval-adjacent change (regression check).
- Golden retrieval set TODO: extend to cloud/CRM vendors (currently MongoDB/
  Pinecone only).
- Ops debts on record: Gemini free tier ~1K embeds/day/key (2 keys; enable billing
  before real users); Render env needs FIRECRAWL_API_KEY + GEMINI_API_KEYS (done
  2026-07-20); old bullet pipeline deleted only after Phase 4 parity.
- Sonnet delegation: Phases 1-2 briefs are well-specified — delegate build, senior
  review + fixes by main session (pattern that worked for ingest layer).

## Sequence & why this order

1 → 2 → 3 → 4 → 5. Claims engine first because every head consumes it; heads
before jobs so there's something worth checkpointing; eval before Slack because
trust math must exist before we broadcast outputs; Slack last because it rides on
jobs + diffs that phases 1-3 built. Each phase ships value standalone — stopping
after any phase leaves the product strictly better than before it.
