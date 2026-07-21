# Sonnet Brief — Phase 2 Task A Fix Cycle

Repo: `/Users/ajinkyagajananraochintawar/ad-ci`. The Task A build
(`heads/` package, docs/SONNET_PHASE2_BRIEF.md) is structurally good but the
buyer smoke test FAILED with Groq 413s. Review found the root causes. This
brief is the fix list — apply exactly these changes, nothing else.

Smoke failure evidence (buyer run):
- Weaviate produced **78 gated claims** (extractor prompt says 1-4 per
  dimension × 7 dims = 28 max — the model ignores the instruction and no code
  enforces it).
- Round 1 8B prompts: 413 "Requested 11213, Limit 6000".
- Judge 70B prompt: 413 "Requested 12307, Limit 12000" (~thousands of those
  tokens are raw 64-char evidence hashes rendered into the prompt).
- Head raised: "judge output invalid after re-ask: empty LLM response".

**Ground rules**: `.venv/bin/python`. No commits. Only the files named below
change. Keep existing style. Fix 1 touches `claims/extractor.py` — that file
was frozen in your earlier brief; this is now an authorized, eval-gated
change (re-run its eval afterward, see Verification).

---

## Fix 1 — Enforce the claims cap at the source (`claims/extractor.py`)

In `extract_claims`, after a dimension's claims are parsed and validated,
enforce top-4 by strength:

```python
dim_claims.sort(key=lambda c: c.strength, reverse=True)
dim_claims = dim_claims[:4]
```

(Place it where both the first-attempt and retry paths flow through — right
after the parse succeeds, before `all_claims.extend`.) A stable sort keeps
the model's own ordering among equal strengths.

## Fix 2 — Heads cite claim indexes, never hashes (heads/buyer.py, seller.py, analyst.py)

The Phase 1 lesson (E-labels) applies to the judge too: LLMs can't reliably
copy 64-char hashes, and hashes bloat prompts (~30 tokens each). Change the
flow so **no prompt ever contains an evidence hash**:

1. In each head, build one enumerated claim list per prompt context:
   label claims `C1..Cn` (global across companies in that prompt — e.g. the
   judge sees `MongoDB: C1-C24`, `Pinecone: C25-C51`, ...). Render as:
   `[C7] (cost, weakness, strength 4) <claim text>` — NO evidence ids shown.
2. Prompts instruct: cite `claim_ids` (e.g. `["C7", "C12"]`), only labels
   shown above are valid.
3. After parsing the verdict JSON, deterministically resolve each cited
   claim label → that claim's `evidence_ids` (union, deduped, order-stable)
   and write them into the schema's `evidence_ids` fields. Strip invalid
   labels (same pattern as claims/extractor.py `_parse_claims`); an item
   whose labels all resolve to nothing keeps `evidence_ids: []` and will be
   caught by schema/consistency as before.
4. Schemas stay unchanged on the wire (`verdict_json` still carries real
   evidence_ids — the UI contract is untouched). The LLM-facing JSON asks
   for `claim_ids`; the resolution step swaps them for `evidence_ids`.
   Implement the label→claim map + resolution helper once in
   `heads/schemas.py` or a small `heads/citations.py`, reuse from all three
   heads.
5. The debate rounds (buyer round1/round2, seller red-team/counter) already
   use per-list indexes — leave their protocol, but REMOVE the
   `[evidence: ...]` suffix from `_render_claims` so hashes disappear from
   those prompts too.

## Fix 3 — Token budget guard (`heads/llm.py`)

Add a pre-flight size check to `call_llm`:

```python
TOKEN_CAPS = {"llama-3.1-8b-instant": 6000, "llama-3.3-70b-versatile": 12000}
def estimate_tokens(messages, max_tokens): return sum(len(m["content"]) for m in messages) // 2.5 + max_tokens
```

(chars/2.5 — measured on this corpus's table-heavy text, not the optimistic
/4.) If a prompt exceeds the model's cap, `call_llm` returns a distinct
sentinel/raise so callers know it's oversized (do NOT silently truncate in
llm.py — content decisions belong to the head).

In the heads, before each judge/synthesis call: if over budget, drop the
lowest-strength claims from the rendered block (recompute the C-labels after
dropping — labels must match what's rendered) until it fits, printing
`⚠️ budget: dropped N low-strength claims to fit <model>`. Same guard for the
8B debate prompts (rival claim lists are the fat part — cap rivals' rendered
claims first, own claims last).

## Fix 4 — Mechanical review findings

- `heads/schemas.py`: `DimensionScore.score: int = Field(ge=0, le=10)`.
- `heads/consistency.py`: `check(verdict, claims_by_company, vertical=None)`;
  `_check_analyst` must take the dimension list from
  `get_dimensions(vertical)` when vertical is given (fall back to
  matrix-derived dims only when vertical is None). Update heads/runner.py and
  eval/heads_smoke.py call sites to pass the vertical. Keep the self-check
  passing (it may pass vertical=None).
- `heads/buyer.py::recompute_confidence` (and the winner-count logic in
  `heads/consistency.py::_check_buyer`): match winner names tolerantly —
  normalize with a shared tiny helper (lowercase, strip; a per_dimension
  winner counts for the overall winner if one normalized name contains the
  other). Keep it deterministic and symmetric between buyer.py and
  consistency.py so the identity they assert is the same computation.
- `heads/buyer.py` + `heads/seller.py` system prompts: replace hard-coded
  "database vendor" with the vertical's display name (`get_vertical(vertical)["display_name"]`
  or just pass `vertical` through) so cloud/CRM work later.

---

## Verification (run all, report real numbers)

1. `.venv/bin/python -m claims.gate` and `-m heads.consistency` and
   `-m heads.schemas` — self-checks pass.
2. `.venv/bin/python -m eval.claims_eval` — regression gate for Fix 1. Bars:
   survival ≥ 90%, coverage 100%, AND every company's claims_extracted ≤ 28
   (7 dims × 4). If coverage regresses, report it — do not revert the cap
   silently.
3. `.venv/bin/python -m eval.heads_smoke all` — all three modes complete,
   zero 413s, consistency passed (or visibly flagged), results saved to
   eval/results/.
4. `.venv/bin/python -c "import pipeline.court_session"` still clean.

## Report back
Files changed, claims_eval numbers (incl. max claims per company), smoke
numbers per mode (summary line, consistency, evidence counts, head LLM calls,
wall time, any budget-drop warnings), and anything that didn't work as this
brief predicted — plainly, no silent workarounds.
