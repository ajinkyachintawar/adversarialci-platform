"""
Analyst Head
============
No debate. One 70B call: all gated claims for all companies -> a scoring
matrix (company -> dimension -> {score, reason, evidence_ids}).

Judgment call (brief left this ambiguous): dimensions the judge skips for a
company are filled in afterward, deterministically, as
{"score": 0, "reason": "no evidence", "evidence_ids": []} — never left to the
LLM to guess at, so "no evidence" always means literally zero claims, not a
model hallucinating a low score. heads/consistency.py enforces
evidence_ids non-empty only when score > 0.

Run:  .venv/bin/python -m heads.analyst  (requires Atlas + Groq — see eval/heads_smoke.py)
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heads import llm as llm_mod
from heads.llm import call_llm
from heads.schemas import AnalystVerdict, DimensionScore, parse_verdict_json
from heads import evidence as evidence_mod
from heads import citations
from verticals import get_dimensions

NO_EVIDENCE_SCORE = DimensionScore(score=0, reason="no evidence", evidence_ids=[])
JUDGE_MAX_TOKENS = 4000


def _synthesize(companies: list[str], claims_by_company: dict, vertical: str,
                 judge_model: str) -> AnalystVerdict:
    dims = get_dimensions(vertical)
    # local, droppable copy — never mutates the caller's claims_by_company
    pool = {c: list(claims) for c, claims in claims_by_company.items()}

    def build():
        claims_block, label_to_claim = citations.label_and_render(pool)
        rendered = "\n\n".join(f"{c}:\n{claims_block[c]}" for c in companies)
        system = ("You are an impartial market analyst scoring vendors on "
                  "fixed dimensions. Base every score only on the cited "
                  "evidence — every claim_id you cite must be one of the "
                  "labels shown. If a company has no evidence for a "
                  "dimension, omit that dimension entirely rather than "
                  "guessing.")
        user = f"""VENDORS: {', '.join(companies)}
DIMENSIONS: {', '.join(dims)}

ALL GATED CLAIMS:
{rendered}

Score every vendor on every dimension you have evidence for (1-10, higher is
better). Cite claim_ids using only the labels shown above. Each `reason` and
the `summary` must be a complete sentence: if it restates a claim, restate it
in full, keeping the comparison target and any numbers — never stop
mid-comparison ("X is cheaper" when the claim said "X is cheaper than Y").
Put claim ids ONLY in claim_ids fields — never mention them in prose.
Return ONLY JSON, no markdown fences:
{{"mode": "analyst",
  "matrix": {{"{companies[0]}": {{"cost": {{"score": 7, "reason": "...",
                                     "claim_ids": ["C1"]}}}}}},
  "summary": "..."}}"""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        return messages, label_to_claim

    dropped = 0
    while True:
        messages, label_to_claim = build()
        if llm_mod.fits(messages, judge_model, JUDGE_MAX_TOKENS):
            break
        if not llm_mod.drop_lowest_strength(pool):
            break
        dropped += 1
    if dropped:
        print(f"  ⚠️ budget: dropped {dropped} low-strength claims to fit {judge_model}")

    resolve_ids = lambda obj: citations.resolve_claim_ids(obj, label_to_claim)

    for is_retry in (False, True):
        try:
            raw = call_llm(messages, model=judge_model, max_tokens=JUDGE_MAX_TOKENS)
            return parse_verdict_json(raw, AnalystVerdict, resolve_ids=resolve_ids)
        except Exception as e:
            if is_retry:
                raise ValueError(f"analyst output invalid after re-ask: {e}")
            echo = (raw or "")[:200]
            messages = messages + [
                {"role": "assistant", "content": echo + ("..." if raw and len(raw) > 200 else "")},
                {"role": "user", "content":
                    f"Your previous output was invalid JSON for the "
                    f"AnalystVerdict schema ({e}). Return only the corrected "
                    f"JSON object, citing only real claim_ids shown above."},
            ]
    raise ValueError("unreachable")


def _fill_gaps(verdict: AnalystVerdict, companies: list[str], vertical: str) -> AnalystVerdict:
    """Deterministic post-process — never left to the LLM. Every company x
    dimension cell must exist; missing ones become the fixed
    NO_EVIDENCE_SCORE sentinel."""
    dims = get_dimensions(vertical)
    for company in companies:
        row = verdict.matrix.setdefault(company, {})
        for dim in dims:
            if dim not in row:
                row[dim] = NO_EVIDENCE_SCORE.model_copy()
    return verdict


def run_analyst(state: dict) -> AnalystVerdict:
    """Public contract per the brief. heads/runner.py calls
    `_run_with_evidence` directly to avoid a second evidence.gather."""
    verdict, _ = _run_with_evidence(state)
    return verdict


def _run_with_evidence(state: dict) -> tuple[AnalystVerdict, dict]:
    from config import LLM_MODEL
    vertical = state["vertical"]
    companies = [state["primary"]] + state["competitors"]

    print(f"  📊 Analyst head: {', '.join(companies)}")
    gathered = evidence_mod.gather(companies, vertical)
    claims_by_company = gathered["claims_by_company"]

    print("  🧑‍⚖️  Scoring pass (70B)")
    verdict = _synthesize(companies, claims_by_company, vertical, LLM_MODEL)
    verdict = _fill_gaps(verdict, companies, vertical)

    return verdict, claims_by_company


if __name__ == "__main__":
    from state import create_initial_state
    state = create_initial_state("database", "analyst")
    state.update({
        "primary": "MongoDB",
        "competitors": ["Pinecone", "Weaviate"],
        "plaintiff": {
            "mode": "analyst",
            "company_name": "TestCorp",
            "use_case": "general comparison",
            "priority": "value",
        },
    })
    verdict, claims = _run_with_evidence(state)
    print(json.dumps(verdict.model_dump(), indent=2))
