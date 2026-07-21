# Sonnet Brief — Phase 2: Mode Heads + JSON Verdicts + Consistency Checker

Repo: `/Users/ajinkyagajananraochintawar/ad-ci`. Read `docs/AGENTS_V2_PLAN.md`
Phase 2 for background; this brief wins on any conflict. Phase 1 (`claims/`)
is built, evaluated (100% survival/coverage), and committed locally — use it,
do not modify it.

Phase 2 is split into **Task A (backend)** and **Task B (UI)**. They are
separate work sessions; Task B starts only after Task A is reviewed. If you
were told which task you're doing, skip the other section entirely.

**Ground rules (both tasks)**
- Python: `.venv/bin/python`. No `python`/`python3`.
- **The old pipeline keeps working untouched.** All new behavior is gated by
  env flag `AGENTS_V2` (unset/`0` = old path exactly as today). The only edits
  allowed in existing files are the minimal routing/persistence hooks named
  below — nothing else in `court/`, `pipeline/`, `server.py` changes.
- No commits. Match codebase style (docstring headers, emoji prints, functions
  over classes, `__main__` self-checks).
- Groq free tier: sequential calls, `time.sleep(2)` between, ~6K TPM per key.
  Reuse the claims extractor's proven patterns.

**Existing interfaces (do not reimplement)**
- `from claims.extractor import extract_claims` →
  `extract_claims(company, vertical, k=6)` → `{company, vertical, claims: [...], metrics: {...}, _rows}`.
  Each claim: `{dimension, claim, stance: "strength"|"weakness", evidence_ids: [chunk content_hash], strength: 1-5}`.
- `from claims.gate import gate_claims` → `gate_claims(company, claims)` →
  `{claims: [... + source_urls], metrics}`. Run the gate after every extraction;
  heads consume ONLY gated claims.
- `court/advocates.py::call_groq` / `claims/extractor.py::_call_groq` — Groq
  call patterns. 8B = `llama-3.1-8b-instant`, 70B = `llama-3.3-70b-versatile`
  (`config.LLM_MODEL`). Key rotation lives in claims/extractor.py — copy that
  pattern (do not import its private helper).
- `state.py::WarRoomState` — dict with `mode, vertical, primary, competitors,
  my_company, plaintiff, verdict, stage, ...`.
- `pipeline/court_session.py::court_session(state)` — current orchestration:
  build_challenge → argument banks → advocates → judge deliberate →
  parse_verdict → process_verdict (saves to `court_sessions` Mongo collection).
- `db.atlas`: `connect()`, `get_collection("court_sessions")`, `get_collection("rag_chunks")`.

---

## TASK A — heads package + wiring behind flag

### A1. `heads/__init__.py`
Empty.

### A2. `heads/llm.py`
One shared Groq caller for all heads:
`call_llm(messages, model, max_tokens=2048, temperature=0.2) -> str | None`
with the key-rotation-on-429 pattern from `claims/extractor.py` (rotate across
`config.GROQ_API_KEYS`, 20s wait after all keys exhausted, one full second
round, None on hard error). `time.sleep(2)` after every successful call.

### A3. `heads/schemas.py`
Pydantic v2 schemas — these ARE the verdict contract, be exact:

```python
class CitedItem(BaseModel):        # any list entry that must cite evidence
    text: str
    evidence_ids: list[str] = Field(min_length=1)

class DimensionVerdict(BaseModel):
    dimension: str
    winner: str
    reason: str
    evidence_ids: list[str] = Field(min_length=1)

class BuyerVerdict(BaseModel):
    mode: Literal["buyer"] = "buyer"
    winner: str
    confidence: int              # 0-100
    per_dimension: list[DimensionVerdict]
    summary: str
    caveats: list[str] = []

class Objection(BaseModel):
    objection: str
    response: str
    evidence_ids: list[str] = Field(min_length=1)

class SellerVerdict(BaseModel):
    mode: Literal["seller"] = "seller"
    my_company: str
    win_probability: int         # 0-100
    advantages: list[CitedItem]
    vulnerabilities: list[CitedItem]
    objections: list[Objection]
    landmines: list[CitedItem]   # traps to set for the competitor
    talk_tracks: list[str]
    do_not_say: list[str]

class DimensionScore(BaseModel):
    score: int                   # 1-10
    reason: str
    evidence_ids: list[str] = Field(min_length=1)

class AnalystVerdict(BaseModel):
    mode: Literal["analyst"] = "analyst"
    matrix: dict[str, dict[str, DimensionScore]]   # company -> dimension -> score
    summary: str
```

Also `parse_verdict_json(raw: str, model_cls)` helper: strip fences, salvage
truncated JSON (copy the `rfind` trick from claims/extractor.py — for objects
use the last complete `}`), validate with `model_cls`, raise on failure.

### A4. `heads/evidence.py`
`gather(companies: list[str], vertical: str) -> dict`:
runs `extract_claims` + `gate_claims` per company, returns
`{company: [gated claims]}` plus merged metrics. Print per-company one-liners.
This is the single entry every head calls first — claims never bypass the gate.

### A5. `heads/buyer.py`
`run_buyer(state) -> BuyerVerdict`. 2-round debate, then 70B judge:
1. `claims_by_company = evidence.gather([primary]+competitors, vertical)`.
2. Round 1 (8B, one call per company): advocate picks its 3 strongest claims
   for this plaintiff profile + names the top weakness claim of each rival.
   Output: short JSON (claims referenced by list index — validate indexes).
3. Round 2 (8B, one call per company): rebuttal — respond to the attacks on
   you using your claims only. Same JSON shape.
4. Judge (70B, one call): give it the plaintiff profile/challenge (reuse
   `build_challenge` from pipeline/court_session.py), all gated claims with
   their evidence_ids, and both debate rounds. Ask for BuyerVerdict JSON only.
   `evidence_ids` in the verdict must come from the claims' evidence_ids.
   One re-ask on invalid JSON (pattern from claims extractor), then raise.
5. Return validated BuyerVerdict.

Confidence formula (deterministic, judge doesn't pick it): after validation,
recompute `confidence = round(100 * dims_won_by_winner / len(per_dimension))`
and overwrite — the consistency checker (A8) asserts this identity.

### A6. `heads/seller.py`
`run_seller(state) -> SellerVerdict`. 1-round red-team:
1. Gather claims for my_company + competitors.
2. Red-team (8B, one call per competitor): competitor advocate attacks
   my_company using its own strength claims and my_company's weakness claims →
   objections + landmines (JSON, cite claim indexes).
3. Counter (8B, one call): my_company advocate answers each objection using
   my_company claims → responses + talk_tracks.
4. Synthesize (70B, one call): SellerVerdict JSON. Every advantages/
   vulnerabilities/objections/landmines item carries evidence_ids from the
   underlying claims. win_probability justified by claim strengths.
5. Validate, return.

### A7. `heads/analyst.py`
`run_analyst(state) -> AnalystVerdict`. No debate. One 70B call: all gated
claims for all companies → scoring matrix (every company × every vertical
dimension gets `{score, reason, evidence_ids}`). Validate: matrix covers every
company and every dimension (fill gaps with score=0, reason="no evidence",
evidence_ids omitted — make DimensionScore.evidence_ids optional with
default [] ONLY for this no-evidence case… simpler: allow `evidence_ids: list[str] = []`
in DimensionScore and let the consistency checker require non-empty only when
score > 0).

### A8. `heads/consistency.py`
`check(verdict, claims_by_company) -> dict` — deterministic, no LLM:
- every evidence_id in the verdict exists in some gated claim's evidence_ids
  for the relevant company (build the valid-id set from claims_by_company);
- buyer: winner == company winning most per_dimension entries; confidence
  matches the A5 formula; per_dimension has no duplicate dimensions;
- seller: 0 <= win_probability <= 100; every objection has a response;
- analyst: matrix covers all companies × dimensions; score>0 ⇒ evidence_ids non-empty.
Returns `{passed: bool, failures: [str]}`. On failure the caller does ONE 70B
re-ask quoting the failures verbatim ("Fix these inconsistencies, return the
corrected JSON only"); still failing → set `inconsistent: true` on the stored
verdict and continue (never crash the session).
`__main__` self-check with hand-built verdicts (one passing, one failing per
mode) — no DB, no LLM.

### A9. Wiring (the ONLY edits to existing files)
`pipeline/court_session.py::court_session`: at the top,
```python
if os.getenv("AGENTS_V2") == "1":
    from heads.runner import run_v2
    return run_v2(state)
```
`heads/runner.py`: dispatch mode → run_buyer/run_seller/run_analyst, run
consistency check + optional re-ask, then persist: insert into
`court_sessions` a doc with the same core fields the old
`court/verdict.py::process_verdict` writes (`winner`, `confidence`,
`vertical`, `mode`, timestamp — read process_verdict and mirror its doc shape
so the History UI keeps working) **plus** `verdict_json: <validated verdict
dict>` and `consistency: {passed, failures}` and `claims_metrics`. Print the
same style of completion banner. Return `{**state, "verdict": {...}, "stage": "complete"}`
where state["verdict"] carries at minimum `overall_winner` for old callers.

### A10. `eval/heads_smoke.py`
CLI: `.venv/bin/python -m eval.heads_smoke [buyer|seller|analyst|all]`.
For MongoDB vs Pinecone vs Weaviate (database vertical, canned plaintiff
profile — copy a realistic one from pipeline/court_session.py `__main__`):
run the head, run consistency.check, print: verdict summary line, consistency
result, count of cited evidence_ids, Groq calls, wall time. Save full verdict
JSON to `eval/results/heads_smoke_{mode}_{ts}.json`. Exit non-zero if a head
raises or consistency fails without recovery.

### Task A acceptance
- `heads/consistency.py` self-check passes offline.
- `eval/heads_smoke.py all` completes: three valid verdicts, consistency
  passed (or visibly flagged), zero unresolvable evidence_ids, results saved.
- With `AGENTS_V2` unset, `pipeline/court_session.py` behaves byte-identically
  to today (no import of heads at module level — import inside the flag branch).
- Report honestly: verdict quality, consistency failures, wall time, token use.

---

## TASK B — UI renders verdict_json (after Task A review)

Read `ui/src/pages/ReportView.tsx` and `ui/src/lib/reportParser.ts` fully
before writing anything.

- `server.py`: add `GET /api/chunks/{content_hash}` → `{text, source_url,
  source_type, company}` from `rag_chunks` (404 if missing). Add
  `verdict_json` + `consistency` to the session detail response if the
  existing endpoint filters fields (check `GET /api/sessions` and the
  session-by-id path around server.py:483 — if it already returns the whole
  doc, no change needed).
- `ReportView.tsx`: if `session.verdict_json` exists, render from it directly
  (typed per mode — buyer/seller/analyst layouts already exist visually;
  reuse the existing styled components, swap the data source from
  reportParser extraction to verdict_json fields). Sessions without
  verdict_json fall back to the current reportParser path unchanged.
- Citation chips: wherever a verdict item has evidence_ids, render small
  numbered chips; click/hover fetches `/api/chunks/{hash}` (cache per hash)
  and shows source_url link + chunk text preview (popover or expandable).
- `inconsistent: true` or `consistency.passed == false` → visible amber
  banner "Consistency check flagged this report" listing failures.
- No new UI deps. Match the existing design system components/tokens.

### Task B acceptance
- One real session per mode run with `AGENTS_V2=1` renders from verdict_json
  with working citation chips (chunk text + source link visible on click).
- Old sessions (no verdict_json) still render via reportParser.
- `npm run build` (or the repo's build script) passes clean.

---

## Report back (both tasks)
Files created/edited (exact list), eval/smoke numbers, Groq calls + wall
time, judgment calls you made, anything in the brief that turned out wrong
against the real code (say so plainly — do not silently work around it).
