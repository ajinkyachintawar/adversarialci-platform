# Plan A — Phase 0 (data foundation) + Phase 1 (answer function + endpoint)

## Context

**The problem, in GTM terms.** A sales rep is on a call. The buyer says *"Competitor
X is cheaper and does Y."* The rep has four seconds and no way to check. Today's
competitive-intelligence tools (Klue, Crayon, Kompyte — $15k–$40k/yr) answer this by
having a human product marketer collect sources, curate them, and write a battlecard.
That model fails four ways: it goes stale, it lives in a document nobody opens
mid-call, it runs on a weekly cycle against a real-time problem, and it gives the rep
no provenance — no quote, no link, no date — so the rep can neither verify it nor
forward it.

**What Plan A does differently.** `docs/PLAN_A.md`: *we surface evidence, we do not
assert facts.* The answer is a quote + a link + a date, with one line of framing.
Incumbents can never say "no evidence found," because a battlecard always has
content. We can, every time — and it costs zero LLM calls to say it.

**Why a Phase 0 exists.** A live census of `rag_chunks` during planning found the
corpus is not stale so much as **thin**:

| company | chunks | **URLs** | age (days) |
|---|---|---|---|
| Salesforce | 156 | **4** | 14 |
| Weaviate | 108 | **6** | 14 |
| Pinecone | 88 | **4** | 14 |
| MongoDB | 76 | **4** | 14 |
| ChromaDB | 19 | **3** | 14 |

Total 1,122 chunks / 18 companies, every one exactly 14 days old — a single ingestion
run, capped by `max_tavily_urls=3` (`ingest/pipeline.py:102`) plus one pricing page.

14-day-old pricing pages are **not** the problem: Plan A stamps a date on every
citation, so disclosed age is a feature, not a defect. **Four URLs per company is the
problem.** Questions about SOC2, data residency, migration effort, rate limits, or
enterprise SLAs hit nothing. The system then returns *no* answer rather than a wrong
one — which sounds safe but is fatal: a rep who gets "no evidence found" three times
never opens the tool again. **False abstention is the failure mode that kills Plan A**,
and 4 URLs guarantees it.

**The worse problem, found while verifying Task 0.3: 87% of the corpus is not
vendor-owned at all.** Of 272 chunks across the three targets, only 36 come from the
vendor's own domain:

| company | chunks | vendor-owned | the rest |
|---|---|---|---|
| Weaviate | 108 | **5** (`weaviate.io/pricing`) | ranksquire.com, medium.com, kunalganglani.com, u-cloud24.com, pecollective.com |
| Pinecone | 88 | **15** (`pinecone.io`, `docs.pinecone.io`) | ranksquire.com ×2 |
| MongoDB | 76 | **16** (`mongodb.com`, `investors.mongodb.com`) | tech-insider.org, zignuts.com |

This breaks the product's core premise. Asked about Weaviate today, the system would
overwhelmingly quote `ranksquire.com` — SEO affiliate content — and present it as
evidence with a clickable link. That is a worse trust violation than the Reddit/G2
sources we explicitly excluded, since a Reddit commenter at least has hands-on
experience.

Cause: `SKIP_DOMAINS` (`ingest/pipeline.py:28`) blocks only youtube.com and
reddit.com, and Tavily returns whatever ranks on the open web for "Weaviate pricing
2026" — which is comparison blogs, by construction.

**This also invalidates the old retrieval eval.** The 16/16 hit@1 was measured against
this corpus, and it only checks whether a retrieved chunk contains an expected
substring — which a third-party article satisfies as well as a vendor page. It was
passing on junk: exactly the critique `PLAN_A.md` levels at the old pipeline (it
measured that citations *resolved*, not that they were *right*).

Phase 0 therefore does three things, in order: **purge** non-vendor content, **widen**
with curated vendor pages, then **calibrate**. Calibration must come last because
`SCORE_FLOOR` is a property of a specific corpus and chunking — calibrating first
would mean calibrating twice.

**Scope decisions taken.** Re-ingest **only** Pinecone / Weaviate / MongoDB (the only
companies Phase 1 touches; all 18 at full breadth would exceed the Gemini free
embedding quota for no user benefit). Seed URLs come from **Gemini Deep Research**,
run manually — free on an existing Pro subscription, higher quality than automated
search, and it keeps editorial control over what enters the corpus. **Vendor-owned
pages only** — no Reddit, G2, X, or `agent-reach`. A Reddit comment is not a
competitor claim; citing one to a buyer trades away the verifiable-provenance
guarantee that is Plan A's entire differentiator. Social sentiment is a separate,
clearly-labelled surface for after A4. (`SKIP_DOMAINS` at `ingest/pipeline.py:28`
already excludes reddit.com and youtube.com — nothing to change.)

---

## Working environment

All Phase 0/1 work happens in a **git worktree at `~/EarshotCI` on branch `earshot`**,
created from `ad-ci@a6d658b`. The `~/ad-ci` folder stays on `main` and is not touched;
both can be open at once. Merging back is an ordinary `git merge` when Phase 1 lands.

Because `.env` and `.venv/` are gitignored, the worktree was set up with `.env` copied
and `.venv` symlinked to `~/ad-ci/.venv` (same interpreter, same deps — install once,
not twice). Verified working: Atlas connects, `retrieve()` returns from all 1,122
chunks.

The product is **EarshotCI**; the new Python package is `earshot/`, not `ask/`. The
Mongo collection stays `ask_log` — it describes what it holds.

---

## Four gaps in PLAN_A.md that Phase 1 must close

Found by reading code, not the doc. Each would break A0 on day one.

1. **No score floor exists.** `ingest/retrieval.py::retrieve()` returns up to `k`
   chunks regardless of score. The abstention path — the plan's most important
   guardrail — is unimplemented.
2. **No date is returned.** The `$project` at `ingest/retrieval.py:76` returns
   `text, source_url, source_type, content_hash, score`. Every citation is supposed
   to carry a date; today it can't.
3. **The citation pattern PLAN_A names is the wrong one.** `heads/citations.py`
   resolves `C1..Cn` claim labels — a different, more complex scheme. The right one is
   the self-contained `id_map = {f"E{i+1}": chunk}` at `claims/extractor.py:142`.
4. **`call_llm` sleeps 2s after every successful call** (`heads/llm.py`). Two of the
   ten seconds are already spent — which is why "one LLM call per question" is
   load-bearing, not stylistic.

---

# Phase 0 — Data foundation

## Task 0.1 — `eval/rag_chunks_census.py` (read-only)

Sibling of `eval/corpus_snapshot.py` (which covers the older `research_data`, with
different fields). Per company: total chunks, chunks by `source_type`, **distinct
`source_url` count**, and `first_seen_at` age min/median/max. The URL count is the
headline number — it is what Phase 0 is trying to move.

Follow the eval convention: `label` from `sys.argv[1]`, write
`eval/results/rag_chunks_census_<label>_<ts>.json`, print a summary table.

**Run it twice** — `before` (must reproduce the table above) and `after` Task 0.4.
The two committed JSONs are the evidence that Phase 0 did something.

## Task 0.2 — Gemini Deep Research seed URLs (manual, by the user)

For each of Pinecone, Weaviate, MongoDB, prompt Deep Research for the ~15 most
important public pages for *technically evaluating* the vendor — docs, security and
compliance, limits and quotas, SLAs, migration guides, architecture, changelog — in
addition to pricing. Vendor-owned domains only.

Paste into **`ingest/seed_urls.json`**: `{"Pinecone": ["https://…", …], …}`.

This is where Deep Research earns its keep: it costs nothing on the Pro sub, and
curated evaluation pages beat whatever a generic search returns.

## Task 0.3 — seed-URL support in `ingest/pipeline.py`

One optional parameter, no new module:

```python
def ingest_company(company, vertical="database", dry_run=False,
                   max_tavily_urls=3, seed_urls: list[str] | None = None) -> dict
```

Between the pricing scrape and the Tavily step, loop `seed_urls` through the existing
`_scrape_and_store(...)` with `source_type="seed_page"`, adding each to `scraped_urls`
so the Tavily step cannot re-scrape it. Load `ingest/seed_urls.json` in `__main__`
and pass the entry for the named company. Everything else — chunking, dedup,
staleness replacement, metrics — is unchanged.

Also raise the default `max_tavily_urls` 3 → 5, so the long tail widens alongside the
curated seeds.

**Accept:** `--dry-run` for one company reports seed pages scraped and Tavily URLs
excluding them, and writes zero to Mongo.

## Task 0.3b — Vendor-domain enforcement + purge  *(added after the 87% finding)*

**Part A — `ingest/pipeline.py`.** Derive the vendor's registrable domain from the
`pricing_url` already in `vendor_registry` (no new config): last two hostname labels,
so `https://www.pinecone.io/pricing/` → `pinecone.io`, which correctly *passes*
`docs.pinecone.io` and `investors.mongodb.com`. Filter Tavily candidates and seed URLs
to that domain, keeping the existing `SKIP_DOMAINS` check as well. Missing
`pricing_url` → warn and fall back to current behaviour rather than dropping
everything. Carries a `ponytail:` comment naming the ceiling — the last-two-labels
rule is wrong for `.co.uk`, upgrade to `tldextract` if such a vendor is onboarded.

**Part B — `ingest/purge_nonvendor.py`.** Delete non-vendor chunks for named companies.

- **Dry-run is the default**; deleting requires an explicit `--apply`.
- Scoped to companies named on the CLI, defaulting to the three targets. Must never
  touch the other 15.
- **Deletes from both `rag_chunks` and `rag_documents`** — `rebuild_chunks()`
  regenerates chunks from stored documents, so purging only chunks would let the junk
  resurrect on the next rebuild.
- Writes an auditable record to `eval/results/purge_nonvendor_<label>_<ts>.json` in
  both modes, with a `dry_run` flag.

**Accept:** dry run reports ~103 Weaviate / ~73 Pinecone / ~60 MongoDB chunks to
delete while keeping every vendor-owned URL; a `dry_run=True` ingest shows Tavily
candidates now restricted to the vendor domain; `rag_chunks` still totals 1,122
(nothing deleted during the build).

## Task 0.4 — Purge, then re-ingest the three companies

Per company, in order, one at a time:

```bash
.venv/bin/python -m ingest.pipeline Weaviate database --dry-run   # inspect first
.venv/bin/python -m ingest.pipeline Weaviate database
.venv/bin/python -c "from ingest.embedder import embed_missing_chunks; print(embed_missing_chunks('Weaviate'))"
```

Then once, after all three: `remove_near_duplicates()` (`ingest/embedder.py:132`).

`ingest/store.py` already handles replacement — chunks are deleted and rewritten when
`content_hash` changes for a `(company, source_url)` pair — so this is an update, not
a duplicate load. `embed_missing_chunks` takes a company filter
(`ingest/embedder.py:98`), which is what keeps this inside the Gemini free tier.

**Budget:** ~1,000 chunks total ≈ 50 batches × 15s pause ≈ 13 minutes of embedding,
plus Firecrawl credits for ~60 URLs. Run companies sequentially and watch for 429s —
`embed_missing_chunks` is resumable by design, so a quota stop is recoverable, not a
restart.

Run the purge first, once its dry run has been reviewed:

```bash
.venv/bin/python -m ingest.purge_nonvendor            # review the dry run
.venv/bin/python -m ingest.purge_nonvendor --apply    # then delete
```

**Accept:** the `after` census shows ≥15 distinct URLs per target company, every one
on the vendor's own domain, and roughly 3× the pre-purge vendor-owned chunk count.

**On the retrieval eval — expect it to drop, and that is correct.** Some entries in
`eval/golden_retrieval.json` can only be satisfied by third-party chunks; once those
are purged, those expectations fail. Record the post-purge score honestly as the new
baseline and flag every golden entry that only non-vendor content could satisfy —
those were never testing what we thought they were. Re-run as a genuine regression
check only *after* the seed re-ingest completes. Do not keep SEO chunks to protect a
number.

---

---

## Phase 0 — RESULTS (completed 2026-08-01)

| | before | after |
|---|---|---|
| corpus total | 1,122 chunks | **1,671** |
| first-party, corpus-wide | 38.9% | **63.6%** |
| Weaviate | 108 chunks / 6 URLs / 5% first-party | **169 / 17 / 100%** |
| Pinecone | 88 / 4 / 17% | **207 / 21 / 100%** |
| MongoDB | 76 / 4 / 21% | **445 / 36 / 100%** |

Artifacts: `eval/results/rag_chunks_census_{before,after}_*.json`,
`purge_nonvendor_*_*.json` (audit), `purge_backup_*.json.gz` (236 chunks + 9
documents with embeddings, restore = straight `insert_many`).

**Two silent failures found, both invisible in the pipeline's own output:**

1. **87% of the corpus was third-party SEO content** being cited as evidence.
   Fixed by the vendor-domain gate + purge.
2. **30% of seed URLs never arrived.** Firecrawl 429'd on 19 of 64 URLs;
   `sources/firecrawl_client.py` retried once after 5s and then returned `None`,
   which the pipeline recorded as a zero-chunk row. **A partial ingest looked
   exactly like a successful one.** Fixed with escalating backoff `[5, 15, 45]`
   + 3s pacing (the shape `ingest/embedder.py` already used for Gemini); a
   gap-fill pass then recovered 19/19 with zero failures.

**Standing lesson:** the ingest pipeline reports what it *attempted*, not what it
*achieved*. Coverage — seed URLs intended vs. `source_url`s actually in
`rag_chunks` — should be a permanent post-ingest check, not a manual one.

**The retrieval eval fell 16/16 → 8/16, and that is correct.** Diagnosis: all
four hard failures are eval artifacts, not retrieval regressions.
- 2 queries expect third-party URLs *by name* (`mongodb-vs-mysql`,
  `pinecone-vs-weaviate`) — no vendor publishes a fair competitor comparison, so
  these were only ever satisfiable by SEO content.
- `"768 GB"` appears nowhere in vendor pages; it came from the SEO tutorial,
  while retrieval now returns the authoritative `atlas-limits` page at 0.860.
- `"semantic search"` appears in 0/5 retrieved chunks; **"vector search" appears
  in 4/5** — MongoDB's docs use different vocabulary than the blogs did.

That last point has product consequences for Phase 1: **reps and vendor docs use
different words.** Embeddings bridge it (0.88, correct pages), exact-string evals
do not. Keep it in mind when reading calibration results.

`eval/golden_retrieval.json` is **frozen** as a historical artifact of the junk
corpus; `eval/golden_retrieval_v2.json` is authored against first-party content,
with queries deliberately in rep vocabulary. Never tune either against retrieval
output.

**Debt accepted:** the other 15 companies remain mostly third-party (Qdrant 3.5%,
Salesforce 9.6%, Microsoft Dynamics 365 6.7%). Phase 1 does not touch them. The
per-company `third_party_urls` list in the provenance census JSON is a ready-made
purge worklist. ChromaDB is unclassifiable — no `pricing_url` in
`vendor_registry`, so its 19 chunks are unaudited.

---

# Phase 1 — The answer function and the endpoint

## Task 1.1 — `eval/golden_questions.json` via Deep Research

Ask Deep Research: *"You are a sales rep selling Pinecone against Weaviate. List 60
questions and objections a buyer would actually raise — pricing, security/compliance,
scale/performance, migration, support, roadmap."* Repeat per competitor. Store as
`[{query, company}]`.

**The corpus labels them, not us.** Task 1.2 runs `retrieve()` over all of them and
partitions by score: high → golden positives, low → golden abstains. This is
deliberately better than hand-writing negatives, which are biased toward what we
*imagine* is missing; generated questions surface gaps we would not have predicted.

`eval/golden_retrieval.json` stays as the existing hand-labelled regression set —
do not modify it.

## Task 1.2 — `earshot/calibrate_floor.py`

Lives in `earshot/` because it exists only to choose a constant `earshot/answer.py` uses.

- Run the real `retrieve(query, company, k=6)` for every entry in
  `eval/golden_questions.json`; record the top score.
- Cross-check against `eval/golden_retrieval.json`'s hand-labelled entries for the
  three companies, reusing `is_match` imported from `eval/retrieval_eval.py` — do not
  reimplement it. These are the known-positives that anchor the sweep.
- Sweep floors 0.55 → 0.90 step 0.01. Per floor report **false-abstain rate** on
  known-positives and the **abstain rate** across the generated question set.
- **Choice rule:** the lowest floor with false-abstain rate == 0 on the hand-labelled
  positives — refusing to answer something the corpus supports is the costlier failure
  for a rep — and print the resulting abstain rate on the generated set so the
  human sees the real-world trade-off before committing the number.
- Write `eval/results/floor_calibration_<label>_<ts>.json`. The script *recommends*;
  a human commits the constant.

**Where the constant lives:** a module constant in `earshot/answer.py`, **not** an env
var. It is a data-derived fact about the current embedder and corpus, not a
per-environment secret; in git it shows up in `git blame` and PR review, exactly like
`EVIDENCE_CHAR_BUDGET` (`claims/extractor.py:35`) and `TOKEN_CAPS` (`heads/llm.py`).
An env var would let staging and prod silently drift to different abstention
behaviour with no diff to review.

```python
# Calibrated by earshot/calibrate_floor.py against eval/golden_questions.json +
# eval/golden_retrieval.json (Pinecone/Weaviate/MongoDB, post-Phase-0 corpus).
# Recalibrate after any re-ingest, chunker, or embedder change.
SCORE_FLOOR = 0.71  # placeholder; real value comes from the sweep
```

## Task 1.3 — add the date to `ingest/retrieval.py`

Add **`first_seen_at`** (present on every `rag_chunks` doc) to the `$project` at
`ingest/retrieval.py:76`. Modify in place; do **not** wrap.

A wrapper would need a second `find` by `content_hash` — doubling Atlas round-trips
and risking the date going stale against the chunk if a re-ingest races between the
two reads. One extra key in an existing projection is free and invisible to existing
callers (`claims/extractor.py`, `eval/retrieval_eval.py`), which read only the keys
they already use.

`first_seen_at` means "when this exact text was first captured." Because
`ingest/store.py` replaces chunks whenever `content_hash` changes, it can be *old* but
never *wrong* about what the quoted text said. Render it as "as of {date}", never as
"verified today."

**Accept:** `python -m ingest.retrieval "pricing" MongoDB` runs and each result has
`first_seen_at`; `eval/retrieval_eval.py` still passes (proves no caller broke).

## Task 1.4 — `earshot/answer.py`

```python
def answer(question: str, competitor: str, my_company: str | None = None, k: int = 6) -> dict
```

Returns `{answer, citations: [{quote, source_url, captured_at}], confidence, seconds}`,
`confidence` ∈ `"evidence" | "none"`.

1. `t0 = time.time()`.
2. `chunks = retrieve(question, competitor, k=k)`.
3. **Abstention gate, before any LLM call.** If `not chunks` or
   `max(score) < SCORE_FLOOR` → return `confidence: "none"` immediately, zero LLM
   calls. This branch is the product's credibility, not an error path.
4. If `my_company`: a second `retrieve` for our side. No floor gate — it is
   comparison context, not the thing being asked about; if empty, omit that section.
5. **E-labels**, copying `claims/extractor.py:142`: enumerate `chunks + my_chunks`
   continuously so labels are globally unique; `id_map = {f"E{i+1}": chunk}`. The
   model sees only labels and can never emit a URL or a hash.
6. **Size guard:** per-chunk char budget (`BUDGET // len(chunks)`), then `fits()` from
   `heads/llm.py` before calling. If it does not fit, shrink the `my_company` side
   first — cheaper than dropping competitor evidence.
7. **Model: `llama-3.3-70b-versatile`.** `claims/extractor.py` uses the 8B because it
   runs a high-volume batch loop where per-call quality is averaged out by a
   downstream gate. This is a single, low-QPS call whose prose a rep reads verbatim —
   coherence and quote fidelity dominate, and the 12K cap fits two companies' evidence
   where the 8B's 6K would force a smaller `k`.
8. **Prompt:** answer *only* from the evidence blocks, never prior knowledge; return
   JSON `{answer, citations: [{evidence_id, quote}]}`; the quote must be copied
   exactly — a fragment, not a whole block; cite only labels shown; return
   `citations: []` if nothing supports an answer.
9. **Parse:** pydantic `AskResult`, code-fence strip, truncation salvage, and
   **exactly one re-ask** on malformed output — the policy at
   `claims/extractor.py::_parse_claims`. Unknown labels dropped silently. If the retry
   also fails, return `confidence: "none"` rather than crashing.
10. **Resolve labels in code** via `id_map` → `source_url`, `first_seen_at`, real text.
11. **Verbatim quote verification — the anti-hallucination gate.** Normalize with
    `unicodedata.normalize("NFKC", …)`, fold smart quotes and en/em dashes to ASCII,
    then reuse **`norm()` from `ingest/chunker.py:23`** (lowercase + whitespace
    collapse) — do not write a new normalizer. A quote that is not a substring of its
    chunk is **dropped**, with no "close enough" substitution: inventing a snippet in
    code is the same trust violation the gate exists to prevent. **If every citation
    is dropped, downgrade the response to `confidence: "none"`** — an answer with zero
    verified citations is a hallucination that happened to clear the retrieval floor.
12. `seconds` set on every return path, including abstention.

## Task 1.5 — `python -m earshot.answer` self-check (offline)

Monkeypatch `retrieve` and `call_llm` inside the module — no network. Five assertions:

1. Normal answer → `confidence == "evidence"`, one citation with `source_url` and
   `captured_at`.
2. Empty retrieval → `confidence == "none"`, and a `call_llm` stub that raises if
   invoked is never invoked. **This is the assertion that proves the abstention path.**
3. Invented label `E99` beside a valid `E1` → only the valid citation survives.
4. Hallucinated quote (not a substring of any chunk) → that citation is dropped.
5. All quotes hallucinated → `confidence` downgraded to `"none"`.

**Accept:** self-check passes offline;
`python -m earshot.answer "are they cheaper than us" Weaviate Pinecone` returns a real
answer with a working URL in under 10s; a question from the abstain partition returns
`confidence: "none"` with **zero** LLM calls — verified by reading
`heads.llm.call_count` (`heads/llm.py:26`) before and after, the counter
`eval/heads_smoke.py:95` already uses.

## Task 1.6 — `POST /api/ask` in `server.py`

Follow the established pattern: sync inner `def _work()` +
`await asyncio.to_thread(_work)`, `connect()` / `get_collection()` from `db/atlas.py`
inside the thread.

- Request `{question, competitor, my_company?}`; response is `answer()`'s dict as-is.
- **Unknown competitor → 400**, validated against
  `get_collection("rag_chunks").distinct("company")` — the corpus is its own source of
  truth, so there is no second registry to keep in sync. `raise HTTPException(400, …)`
  from inside `_work()` already works here (`api_get_report`).
- **20s timeout:** `asyncio.wait_for(asyncio.to_thread(_work), timeout=20)` → 504.
- **Auth: leave `/api/ask` behind `SupabaseJWTMiddleware`** — it is a POST, so the
  existing rule in `auth_middleware.py` covers it with zero changes. It triggers
  billed LLM calls and writes the data that becomes the A4 golden set; unauthenticated
  access invites both cost abuse and eval pollution. (Slack's HMAC exemption is an A2
  decision, not this one.)
- **`ask_log` document:** `question, competitor, my_company, answer, citations,
  confidence ("evidence"|"none"|"timeout"), seconds, user_email, created_at`. Logged
  on success **and** timeout — both are real attempts a rep made. **Not** logged on
  400, which never reached `answer()` and would pollute the golden set. Add a
  `created_at` descending index in `db/atlas.py::_ensure_indexes()`, inside the
  existing never-fatal try/except.

**Accept:** `curl -X POST localhost:8000/api/ask` (localhost bypasses auth) returns a
cited answer in under 10s; `competitor: "Nonsense Corp"` returns 400, not a stack
trace; a matching `ask_log` document appears in Atlas.

---

## Verification (end to end, in order)

```bash
.venv/bin/python -m eval.rag_chunks_census before
.venv/bin/python -m ingest.pipeline Weaviate database --dry-run
.venv/bin/python -m ingest.pipeline Weaviate database   # repeat: Pinecone, MongoDB
.venv/bin/python -c "from ingest.embedder import embed_missing_chunks; print(embed_missing_chunks('Weaviate'))"
.venv/bin/python -m eval.rag_chunks_census after        # >=15 URLs/company
.venv/bin/python -m eval.retrieval_eval regression      # retrieval did not regress
.venv/bin/python -m earshot.calibrate_floor baseline        # then commit SCORE_FLOOR
.venv/bin/python -m ingest.retrieval "pricing" MongoDB  # first_seen_at present
.venv/bin/python -m earshot.answer                          # offline self-check
.venv/bin/python -m earshot.answer "are they cheaper than us" Weaviate Pinecone
```

Then run the server:

```bash
curl -sX POST localhost:8000/api/ask -H 'Content-Type: application/json' -d '{"question":"are they cheaper than us","competitor":"Weaviate","my_company":"Pinecone"}'
```

**Done when:** every quote in a citation appears verbatim in a real chunk, every
citation has a working URL and a date, an absent-topic question abstains with zero LLM
calls, `ask_log` has documents in it, and the two census JSONs show breadth went from
~4 to ≥15 URLs per target company.

---

## Critical files

`ingest/pipeline.py`, `ingest/retrieval.py`, `server.py`, `db/atlas.py` (modified);
`ingest/seed_urls.json`, `earshot/answer.py`, `earshot/calibrate_floor.py`,
`eval/rag_chunks_census.py`, `eval/golden_questions.json` (new).

## Accepted risks

- **The 20s timeout does not kill the thread.** `asyncio.wait_for` cancels the waiting
  coroutine, not the OS thread; a hung Groq call keeps a key slot after the client
  gets its 504. Inherent to `to_thread` + blocking clients. Revisit only if it bites
  during A3.
- **Gemini free-tier quota** (~1K embeds/day/key, 2 keys) is the binding constraint on
  Phase 0. Three companies fit; this is exactly why the other 15 are excluded.
  `embed_missing_chunks` is resumable, so a 429 is a pause, not a restart.
- **`SCORE_FLOOR` goes stale silently** after any re-ingest, chunker, or embedder
  change — no automatic check. The comment above the constant names the trigger.
- **The model will sometimes lightly "fix" a quote.** Normalization catches cosmetic
  drift, not paraphrase, so some legitimate citations get dropped and occasionally
  empty an answer. Intentional fail-closed behaviour; loosen only if A4's
  citation-accuracy numbers show it costs more than it protects.
- **Company matching is exact and case-sensitive**, inherited from `retrieve()`'s hard
  filter. Casing normalization belongs in Slack's `/vs` handler, not here.

## Out of scope

Slack (A2), any UI, CRM integration, change alerts, the other 15 companies, social and
review sources (`agent-reach`, Reddit, G2, X), multi-tenancy beyond the existing
per-company filter, and MCP exposure. `answer()` is already the right shape to become
an MCP tool later — the only requirement now is not to design anything that blocks it.

---

## Phase 1 — STATUS (2026-08-01)

Built: `earshot/answer.py` (three gates), `earshot/calibrate_floor.py`,
`eval/golden_abstain.json` (20 negatives), `eval/abstention_eval.py`,
`first_seen_at` + `RetrievalUnavailable` in `ingest/retrieval.py`.
Not built yet: **Task 1.6** (`POST /api/ask` + `ask_log`).

### The floor cannot be the guarantee
Positives 0.860–0.911, negatives 0.789–0.893, **AUC 0.875** — real signal, but
overlapping tails. No threshold separates them: at 0.85 zero false-abstains but
13/20 negatives pass; at 0.90 zero negatives pass but 20/24 positives die.
`SCORE_FLOOR = 0.85` is therefore a cheap PRE-FILTER, not the guarantee.

### Three gates, each catching what the previous cannot
1. `SCORE_FLOOR` — free, zero LLM calls, catches the obvious.
2. **relevance** — model returns `evidence_answers_question` in the SAME call.
3. **verbatim** — quote must exist in a real chunk; all dropped → `"none"`.

Gate 2 exists because **verbatim verification checks a quote is REAL, not that
it ANSWERS THE QUESTION.** Measured: on 20 unanswerable questions the verbatim
gate fired **0 times** — "Pinecone's HNSW implementation" was answered from
*Weaviate's* corpus with 3 perfectly-verified citations.

### Query enrichment — rep questions have no entity
"are they cheaper than us" scored **0.823** (false abstain) while the corpus
answers Weaviate pricing at 0.903. The company name was only a metadata filter,
never part of the embedded text. Prefixing it lifts real rep phrasings by
**+0.045–0.063**. The v2 golden set missed this because every query names the
vendor — *the eval was systematically easier than reality.*

### The verbatim gate was dropping real evidence
Both dropped citations on the canonical query were genuine: the corpus contains
`"Starts at$45/mo"` (no space — Firecrawl artifact) and the model quoted chunk 6
while labelling it E5. Gate now matches whitespace-insensitively and searches
every chunk, re-attributing to the true source. A quote found in no chunk is
still dropped.

### THE THIRD SILENT FAILURE — and the worst
`retrieve()` returned `[]` when `embed_query` failed, so **Gemini quota
exhaustion was reported to the rep as "no evidence found."** Same shape as the
SEO corpus and the Firecrawl 429s: a failure returning a falsy value
indistinguishable from a valid empty result. This one was about to ship as a
feature — abstention IS the product's trust claim, so a confident wrong
abstention is as damaging as a confident wrong answer. Now raises
`RetrievalUnavailable`; `answer()` returns `confidence: "error"`, never `"none"`.

### CLEAN RESULT (2026-08-03, after quota reset) — the relevance gate works
```
abstention rate  18/20 (90%)   was 30% before the relevance gate
answer rate      20/24 (83%)   was 79% — did NOT trade off
abstained at floor 6 (free) | at relevance/citation gate 12
latency  p50 12.8s  p95 16.8s  max 20.5s
```
Verified uncontaminated: 0 runs >60s, 0 floor-abstained positives, 0 errors.
Abstention tripled while the answer rate slightly IMPROVED — the gate is not
over-cautious. An LLM judging its own evidence is reliable enough at this scale;
re-test as the corpus grows. Artifact: `eval/results/abstention_eval_clean_*.json`.

**New top issue: latency.** p50 12.8s is over the 10s target and max 20.5s already
exceeds the 20s timeout Task 1.6 is specced with. Stacked causes: `call_llm`'s 2s
sleep, Groq 429 key rotations, 70B latency, embedding round-trip. The 4 remaining
false abstentions are all at the gate and 3 of 4 are pricing/plan questions —
the known scrape-typography gap.

### Earlier eval numbers were DISCARDED — both runs contaminated
30%/79% then 90%/46%, but 11 of 13 "false abstentions" in run 2 were 81-second
embedder timeouts (the `[5,15,45]` backoff exhausting), not judgement. Latency
9.25s → 32.55s for the same reason. **The abstention rate is currently
unmeasured.** Re-run `eval/abstention_eval.py` after Gemini quota resets.

---

## Latency is a PRICING problem, not a code problem (2026-08-03)

Nearly optimised the wrong thing. Decomposed the clean eval by LLM-call count —
floor-abstentions make zero LLM calls, so their elapsed time is embedding +
Atlas only, and the difference is the Groq call:

| stage | median | n |
|---|---|---|
| embedding + Atlas `$vectorSearch` | **0.33s** | 6 |
| + one Groq call | **12.95s** | 38 |

Retrieval is ~2.5% of the time; **the Groq call is ~97%**. Gemini embedding was
never the bottleneck.

**The same call has returned in 2.71s.** Same model, same prompt shape, same
code — so the 70B can answer in ~2.4s and the 12.6s median is overwhelmingly
free-tier *queueing*, not model speed. Tuning against that number is tuning
against an artifact of the plan we are on. **The 10s target in `PLAN_A.md` is
not reachable on a free Groq key — it is a pricing decision, not an
engineering one.**

Still worth fixing: `call_llm` slept 2s *after* every successful call. Correct
as pacing for the batch loops it was written for, but a trailing sleep also
delays the caller's return, which `answer()` paid on every single question.
Moved to pace on **entry** (`PACE_S`) — identical for back-to-back loops, free
when calls are already seconds apart, ~2s off every rep request. The
`heads/llm.py` self-check stubs Groq and asserts both halves, since a
cold-call-only check would also pass with the old trailing sleep.

**Consequence for A2:** no synchronous path will ever meet Slack's 3s ack
requirement. Slack must ack immediately and post the answer back afterwards.

---

## Task 1.6 — DONE (2026-08-03)

`POST /api/ask` in `server.py` + `ask_log` index in `db/atlas.py`.

**`ASK_TIMEOUT_S = 45`, not the 20s originally specced** — max observed was
20.5s, which the original spec would have 504'd on almost immediately. Derived
from measurement: ~18.5s worst case after the pacing fix, and free-tier queue
times are high-variance so the tail needs headroom. A 504 on a merely-queued
call looks to a rep like the product broke. Lower it when a paid key makes the
tail predictable.

Verified end to end against the live server and Atlas:

| path | result |
|---|---|
| `competitor: "Nonsense Corp"` | **400** listing known companies, **not logged** |
| `"are they cheaper than us"` Weaviate/Pinecone | `evidence`, 2 citations w/ URL + date, 3.48s |
| churn-rate question | `none`, 0 citations, 0.81s |
| `ask_log` | 2 docs (the 400 correctly excluded), `created_at_-1` index present |

`confidence` stays 4-valued out to the caller — `evidence` / `none` / `error`
(retrieval unavailable) / `timeout`. Collapsing `error` into `none` is the
silent failure this product cannot ship. Timeouts ARE logged: they are real
attempts a rep made, and dropping them would hide exactly the slow questions.
A failed `ask_log` write never fails the request — the answer is the product,
the log is for A4.

---

## The quote gate was rejecting real evidence (2026-08-03)

Diagnosed before building, and the earlier diagnosis in this doc was **wrong**:
it was never a chunker problem, and "3 of 4 are pricing" was also wrong.

All 4 false abstentions exit at the **verbatim gate** with retrieval healthy
(0.88–0.91) and the relevance gate passing — the model finds the right evidence
and writes a real answer; only the byte-match fails:

```
model:  Dedicated: $0.08/hour. Starts at $56.94/month. For production…
source: Dedicated  $0.08/hour  Starts at $56.94/month  For production…
```

Pricing tables scrape as **delimiter-less rows**, so the model inserts the
punctuation a human would. Content identical, bytes different. The chunks were
correct the whole time.

Searching the full corpus split the dropped quotes cleanly: **4 of 5 are
punctuation-only**, and the 5th (an HNSW claim) is **assembly** — fragments
stitched from non-contiguous text, which does not match even after
depunctuation. That asymmetry is what makes the fix safe: it widens tolerance
for the scrape's typography without admitting invented claims.

`_depunct()` is a second-chance match ignoring separator punctuation, **never
between two digits** — `$56.94` must not become `$5694` and match `$5.694`.
Verified across **109 distinct money strings** in the corpus: the only 4
collisions are a trailing sentence period (`$20` vs `$20.`), the same number.
Self-check pins all three properties (punctuation accepted, assembly rejected,
decimals never collapsed).

Result on the 4: **3 recover** with real citations; HNSW still correctly
abstains.

---

## THE FOURTH SILENT FAILURE — same pattern, LLM side (2026-08-03)

`RetrievalUnavailable` fixed this on the *retrieval* side and the identical
reasoning was never applied to the *LLM* side. `call_llm` returns `None` when
every Groq key is 429'd, `answer()` mapped that to `parsed is None` →
**`confidence: "none"`**. A quota outage reached the rep as *"the competitor's
own pages don't answer this."*

Caught live: a rate-limited eval logged **23 "giving up this call"** in 17 of 44
queries, every one of which would have been reported as a confident abstention.

Now: `parsed is None and raw is None` → `confidence: "error"`. A *parse* failure
(raw present but unusable) stays `"none"` — we did ask and got something back;
that is a model failure, not an outage.

**Fourth instance of one pattern: a falsy return value that conflates "failed"
with "found nothing."** SEO corpus → Firecrawl 429s → Gemini quota → Groq keys.
Assume it exists anywhere a function can fail and return empty.

### Contamination guard
`eval/abstention_eval.py` now reports **no rates at all** when any query returns
`confidence: "error"`, flagging `contaminated: true` instead. Three runs have
been invalidated this way; a number that must be remembered as untrustworthy
will eventually be trusted.

### Groq 8B and 70B have SEPARATE quota buckets
A health check on `llama-3.1-8b-instant` returned in 0.2s while
`llama-3.3-70b-versatile` — the model `answer()` actually uses — was 429ing on
every key. **Always probe the model in the path.** This cost a killed 17-minute
run on a wrong "the API is fine, it must be hung" conclusion.

### Open
- **Re-run `eval/abstention_eval.py` when 70B quota recovers.** The depunct fix
  is verified on the 4 target queries but NOT across all 44 — specifically
  unmeasured: whether depunctuation loosened the gate enough to let any of the
  20 negatives through. Do not quote an abstention rate until this run is clean.
- `call_llm` builds a new `Groq()` client per call and never closes it (90 open
  connections in one eval run). Harmless in batch scripts, a leak in the
  long-lived `POST /api/ask` server process.
- Free-tier 70B latency swings 10x (1.7s → 25s/query) with no code change —
  more evidence the latency ceiling is the plan, not the code.
- Re-run `eval/abstention_eval.py` to confirm the pacing fix in aggregate; the
  ~2s saving is arithmetic + two spot checks (3.48s / 0.81s), not a re-measured
  distribution.
- A2 (Slack) needs async ack — see the latency section above.
- Paid Groq key is the single biggest latency lever available.

---

## The rate limit is TPD, and the eval cannot fit in it (2026-08-03)

Read Groq's own headers instead of guessing. Per-model, per-key limits:

| model | TPM | req/day | earshot task |
|---|---|---|---|
| `llama-3.3-70b-versatile` | **12,000** | 1,000 | OK, 5.0s |
| `openai/gpt-oss-120b` | 8,000 | 1,000 | OK, **1.7s** |
| `openai/gpt-oss-20b` | 8,000 | 1,000 | OK, **0.9s** |
| `qwen/qwen3.6-27b` | 8,000 | 1,000 | **PARSE FAIL** — not bare JSON |
| `llama-3.1-8b-instant` | 6,000 | 14,400 | (untested for this task) |

**Switching off the 70B would be wrong:** it has the LARGEST budget here, not
the smallest. The intuition that "70B burns more tokens" does not apply — token
cost is the prompt, which is identical across models.

**What is true: every model has its own bucket.** Rotating keys cannot help,
since both keys share one per-model ceiling. Rotating MODELS multiplies it.
`MODEL_FALLBACKS` in `heads/llm.py` now tries `gpt-oss-120b` then `gpt-oss-20b`
before waiting. Verified live — the 70B was already 429'd and the chain
rescued the call.

**The fallback was silently useless on the main path.** `TOKEN_CAPS` counts
input + `max_tokens`, so a two-company prompt estimated **8,086** against every
fallback's **8,000** cap: the chain collapsed to the 70B alone for exactly the
"us vs them" question reps ask most. `MAX_OUTPUT_TOKENS` 1024 → **768** (answers
measure ~400 chars) brings it to 7,830 and restores the chain. **Raising
`MAX_OUTPUT_TOKENS` re-breaks this** — the constant carries the warning.

**THE BINDING CONSTRAINT IS TOKENS-PER-DAY, NOT PER-MINUTE.**
```
Rate limit reached ... on tokens per day (TPD):
Limit 100000, Used 96962, Requested 4526
```
At ~4.5K tokens per call, the 70B allows **~22 calls per day**. The abstention
eval needs **44**. *The full eval cannot complete on a free key in one day* —
which is why every attempt today ended contaminated. Options: run it in two
halves across two days, run it entirely on a fallback model, or upgrade the key.
Not "wait for quota to reset" — that was never going to work.

**Also fixed:** `call_llm` built a fresh `Groq()` per call and never closed it
(90 sockets in one run). Now `@lru_cache`d per key — harmless in batch scripts,
a real leak in the long-lived `POST /api/ask` process.

**`confidence: "error"` proved itself in production here:** the exhausted call
returned `error`, not `none`. Before today's fix this would have told the rep
"no evidence found" while the truth was "we never asked."

---

## CLEAN RESULT — abstention 95%, answer rate 100% (2026-08-03)

`eval/results/abstention_eval_gptoss120b_*.json`, `contaminated: false`,
`error_rows: 0` — the guard was armed and did not fire.

| | baseline (70B, no depunct) | now (gpt-oss-120b + depunct) |
|---|---|---|
| abstention rate | 18/20 (90%) | **19/20 (95%)** |
| answer rate | 20/24 (83%) | **24/24 (100%)** |
| false abstentions | 4 | **0** |

All four previously-failing queries now answer, and **no negative leaked**
through the loosened gate — which was the real risk of `_depunct()` and the one
thing the 4-query spot check could not see.

**CONFOUND, stated plainly: two variables changed at once.** This run swapped
BOTH the quote gate (`_depunct`) and the model (70B → gpt-oss-120b), so the
split between them is not measured. What is known: on the 70B, depunct alone
recovered 3 of the 4 targets, so it is doing real work — but the jump from 83%
to 100% cannot be attributed to it. Isolating this needs a 70B + depunct run,
blocked on that model's daily tokens. Do not quote "depunct fixed the answer
rate" until that exists.

**The one remaining false answer** — *"What did Pinecone's last internal
security incident report disclose?"* — also failed in the baseline run. A
persistent weakness, not a regression: the corpus has security *documentation*
that reads as topically adjacent to an incident *report*, and the relevance gate
accepts it. Fixing it means teaching the gate the difference between "publishes
security practices" and "discloses a specific incident."

**gpt-oss-120b is a credible primary**, not just a fallback: it beat the 70B on
both metrics here and answers in ~1.7s vs ~5.0s uncontended. Promotion should
wait for the isolating run above — otherwise we would be choosing a model on a
confounded comparison, which is the same mistake as trusting a contaminated eval.

**Latency in this run is not a product measurement:** p50 19.8s, but only 10/44
runs came in under 8s and the rest include 429 waits. It measures free-tier
contention, not the answer path. `EARSHOT_MODEL` pins the model for exactly this
kind of comparison.

---

## The 70B comparison is BLOCKED on daily tokens (2026-08-03)

Three attempts, all contaminated. The confound in the 95%/100% result — that
run changed BOTH the quote gate and the model — is **still unresolved**.

| key | org | 70B tokens used |
|---|---|---|
| #1 | `org_01khpa…` | 98,560 / 100,000 |
| #2 | `org_01kvwd…` | 98,753 / 100,000 |
| #3 | `org_01kz49…` | 98,886 / 100,000 |

A third key (third org) was added mid-session and consumed by the failed
attempts. **The limit is TOKENS PER DAY**, so no amount of pacing, retrying, or
key-adding fixes it today. Re-run with `GROQ_NO_FALLBACK=1` once the rolling
window clears.

**How this was mis-diagnosed three times, because the pattern will recur:**

1. *"Quota exhausted, wait."* — right, but abandoned when small probes passed.
2. *"It is hung."* — from probing `llama-3.1-8b-instant` while `answer()` uses
   the 70B. **Separate quota buckets.** Cost a killed 17-minute run.
3. *"It is TPM, we are out-running the per-minute ceiling."* — plausible
   arithmetic (5.2K tokens vs 12K TPM = 2.3 calls/min) and it produced two real
   fixes, but it was never the binding constraint.

**The error body said `on tokens per day (TPD)` the entire time.** Every wrong
turn came from inferring the cause from symptoms instead of reading the message
that was already on screen.

**Small probes lie about quota.** `'x'*13000` tokenizes to ~2,428 tokens because
repeated characters compress; a real 5.2K-token prompt 429s where it passes.
A probe must use a real prompt, on the real model, or it proves nothing.

**What survives and is worth keeping:**
- `GROQ_NO_FALLBACK` — a fallback firing mid-benchmark silently produces a
  mixed-model average, which cannot answer the question a benchmark is asked.
- `_pace_for()` — a flat pace cannot be right; the sustainable rate depends on
  prompt size, TPM cap, and key count. Free on the server path.
- `TPM_RETRIES = 3` — Groq's TPM window is 60s; one 20s wait cannot outlast it.
- The contamination guard **fired correctly on its first real outing.** Without
  today's `confidence: "error"` fix, attempt 1 would have reported ~75% answer
  rate and "the 70B is worse" — a plausible number, drawn entirely from quota.
