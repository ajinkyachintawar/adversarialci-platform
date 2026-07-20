# Sonnet Brief — Phase 1: Claims Engine + Citation Gate

You are building the trust core of AdversarialCI's V2 agent pipeline in the repo
at `/Users/ajinkyagajananraochintawar/ad-ci`. Read `docs/AGENTS_V2_PLAN.md`
Phase 1 first. This brief is the executable spec; where they differ, this brief wins.

**Ground rules**
- Python interpreter is `.venv/bin/python` (plain `python`/`python3` do not work).
- Additive only: create `claims/` and `eval/claims_eval.py`. Do NOT touch
  `server.py`, `pipeline/`, `court/`, or `ingest/`. Do NOT commit anything.
- Match the codebase style: small modules, module docstring with run
  instructions, `print` progress lines with emoji prefixes, no logging framework,
  no classes where functions do.
- Every non-trivial module gets a `__main__` self-check or CLI (pattern:
  `ingest/chunker.py`, `ingest/pipeline.py`).

## Existing interfaces you will use (do not reimplement)

- `from ingest.retrieval import retrieve` —
  `retrieve(query: str, company: str, k: int = 5, source_type=None, num_candidates=50)`
  → `[{text, source_url, source_type, content_hash, score}]`. Hard company filter
  inside. Requires DB + Gemini key (embeds the query).
- `from verticals import get_dimensions` — `get_dimensions(vertical)` → list of
  dimension names, e.g. database: `["cost", "performance", "scalability", ...]`.
  Verticals: `database`, `cloud`, `crm`, `llm`.
- `from db.atlas import connect, get_collection` — call `connect()` once, then
  `get_collection("rag_chunks")`. Chunk docs have `company`, `content_hash`,
  `text`, `source_url`, `source_type`.
- Groq: follow the pattern in `court/advocates.py::call_groq` (client from
  `groq` package, `GROQ_API_KEY` env / `config.GROQ_API_KEY`). Model for
  extraction: `llama-3.1-8b-instant`, `temperature=0.1`, `max_tokens=2048`.
  Groq free tier is ~6K TPM: run calls **sequentially** with `time.sleep(2)`
  between them. On 429, sleep 20s and retry once.
- Pydantic v2 is installed (FastAPI dep).

## File 1 — `claims/__init__.py`

Empty (package marker).

## File 2 — `claims/extractor.py`

Purpose: for one company, per dimension, retrieve evidence and have the 8B model
extract structured claims that cite chunk hashes.

```python
DIMENSION_QUERY = {
    # one natural-language retrieval query template per dimension name,
    # {company} placeholder. Cover ALL dimensions across all 4 verticals
    # (union of get_dimensions() for database/cloud/crm/llm). Examples:
    "cost": "{company} pricing plans cost per month free tier",
    "performance": "{company} performance benchmarks latency throughput",
    # ... you write the rest; specific nouns beat generic phrasing.
}
```

Pydantic schema:

```python
class Claim(BaseModel):
    dimension: str
    claim: str                  # one factual sentence
    stance: Literal["strength", "weakness"]
    evidence_ids: list[str]     # content_hash values, min_length=1
    strength: int               # 1-5 (Field ge=1 le=5)
```

`extract_claims(company: str, vertical: str, k: int = 6) -> dict`:

1. For each dimension in `get_dimensions(vertical)`:
   - `chunks = retrieve(DIMENSION_QUERY[dim].format(company=company), company, k=k)`
   - If no chunks: record dimension as empty, continue.
   - Build prompt: system = you are a competitive-intelligence claim extractor;
     user = the dimension, the company, and the chunks formatted as
     `[{content_hash}] {text}` blocks. Instructions to the model:
     - Extract 1-4 claims about {company} on dimension "{dim}" ONLY from the
       evidence blocks. Nothing from prior knowledge.
     - Each claim cites the evidence_ids (the bracketed hashes) it came from.
       Only use hashes that appear in the blocks.
     - stance: "strength" if it favors {company}, "weakness" if it hurts.
     - strength 1-5: how decisive the claim is in a buying decision.
     - Return ONLY a JSON array, no markdown fences, no prose:
       `[{"dimension": ..., "claim": ..., "stance": ..., "evidence_ids": [...], "strength": ...}]`
   - Parse: strip possible ``` fences, `json.loads`, validate each item with
     `Claim`. On JSONDecodeError or ValidationError of the whole array → ONE
     re-ask appending "Your previous output was invalid JSON for this schema.
     Return only the JSON array." to the conversation. Still invalid → drop the
     dimension, count it in `malformed_dimensions`.
   - Per-item validation failures inside an otherwise-valid array: drop the item,
     keep the rest, count in `claims_invalid`.
   - Force `claim.dimension = dim` after validation (model sometimes drifts).
2. Return:
   ```python
   {"company": company, "vertical": vertical,
    "claims": [c.model_dump() for c in all_claims],
    "metrics": {"dimensions_total": N, "dimensions_empty": n1,
                "malformed_dimensions": n2, "claims_invalid": n3,
                "claims_extracted": len(all_claims),
                "groq_calls": n4, "seconds": t}}
   ```

CLI: `.venv/bin/python -m claims.extractor MongoDB database` → runs, prints a
per-dimension table (dimension | chunks retrieved | claims extracted), dumps the
result dict as JSON to stdout at the end.

## File 3 — `claims/gate.py`

Deterministic, zero LLM calls.

`gate_claims(company: str, claims: list[dict]) -> dict`:

1. `connect()`, load the company's chunk hashes once:
   `hashes = {d["content_hash"]: d["source_url"] for d in rag_chunks.find({"company": company}, {"content_hash": 1, "source_url": 1})}`
2. For each claim: every `evidence_id` must be in `hashes`. Any miss → claim
   dropped, counted. Survivors get `source_urls: sorted({hashes[i] for i in ids})`
   added.
3. Return `{"claims": verified, "metrics": {"claims_total", "claims_dropped_uncited",
   "survival_rate"}}`.

`__main__` self-check with a fake in-memory hash map (monkeypatch-free: factor
the resolution step so the check can pass a dict directly) asserting: claim with
a bad id drops, claim with good ids survives and carries source_urls.

## File 4 — `eval/claims_eval.py`

The Phase 1 acceptance harness. For a list of (company, vertical) pairs —
default `[("MongoDB","database"), ("Pinecone","database"), ("Weaviate","database")]`:

1. `extract_claims` → `gate_claims`.
2. Per company report: claims extracted, survived gate, survival %, dimensions
   with ≥1 surviving claim / dimensions total, stance split, avg strength.
3. Aggregate: overall survival rate, overall dimension coverage.
4. Save full results (including every surviving claim with its evidence) to
   `eval/results/claims_eval_{ts}.json` (pattern: `eval/retrieval_eval.py`).
5. Print PASS/FAIL against the acceptance bars: survival ≥ 90%, dimension
   coverage 100% for these three vendors.

CLI: `.venv/bin/python -m eval.claims_eval` (optional args: `Company vertical`
pairs to override the default trio).

## Acceptance (what "done" means)

- `.venv/bin/python -m claims.gate` self-check passes with no DB.
- `.venv/bin/python -m eval.claims_eval` runs end-to-end against live Atlas +
  Groq + Gemini, produces the JSON in `eval/results/`, and prints the PASS/FAIL
  summary. Report the real numbers honestly — if survival < 90% or a dimension
  is empty, say so with the per-dimension breakdown; do not tune thresholds to
  pass.
- No files outside `claims/`, `eval/claims_eval.py`, `eval/results/` created or
  modified. Nothing committed.

## Report back

Final message: files created, the eval numbers (survival rate, dimension
coverage per company), total Groq calls + wall time, and anything ambiguous you
had to decide yourself.
