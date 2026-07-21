"""
Consistency Checker
===================
Deterministic, no LLM. Checks a validated verdict (BuyerVerdict/SellerVerdict/
AnalystVerdict, or the equivalent dict) against the claims_by_company pool it
was built from:

- every evidence_id anywhere in the verdict resolves to a real gated claim's
  evidence_ids (built as one pooled set across all companies — see the
  judgment-call note below);
- buyer: winner == the company winning the most per_dimension entries;
  confidence matches the heads/buyer.py formula
  (round(100 * dims_won_by_winner / len(per_dimension)));
  no duplicate dimensions in per_dimension;
- seller: 0 <= win_probability <= 100; every objection has a non-empty
  response;
- analyst: matrix covers every company x every vertical dimension;
  score > 0 implies non-empty evidence_ids.

Judgment call: the brief says to validate evidence_ids "for the relevant
company," but a buyer/seller verdict item's reasoning legitimately cites a
rival's weakness claim (e.g. an objection built from a competitor's own
claim) — restricting to a single company's pool would false-positive on
exactly the cross-company citations the heads are designed to produce. This
checker instead pools evidence_ids across every company passed in
claims_by_company and checks membership there; it still catches invented
IDs, which is the actual risk the check exists for.

Returns {"passed": bool, "failures": [str]}.

Run:  .venv/bin/python -m heads.consistency   (self-check, no DB/LLM)
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verticals import get_dimensions
from heads.schemas import names_match


def _as_dict(verdict) -> dict:
    return verdict.model_dump() if hasattr(verdict, "model_dump") else verdict


def _valid_evidence_ids(claims_by_company: dict) -> set:
    ids = set()
    for claims in claims_by_company.values():
        for c in claims:
            ids.update(c.get("evidence_ids", []))
    return ids


def _check_evidence_ids(verdict: dict, valid_ids: set) -> list[str]:
    failures = []
    cited = set()

    def collect(node):
        if isinstance(node, dict):
            if "evidence_ids" in node and isinstance(node["evidence_ids"], list):
                cited.update(node["evidence_ids"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)

    collect(verdict)
    unresolved = cited - valid_ids
    if unresolved:
        failures.append(f"evidence_ids not found in any gated claim: {sorted(unresolved)}")
    return failures


def _check_buyer(verdict: dict) -> list[str]:
    failures = []
    per_dim = verdict.get("per_dimension", [])

    dims_seen = [d["dimension"] for d in per_dim]
    if len(dims_seen) != len(set(dims_seen)):
        dupes = sorted({d for d in dims_seen if dims_seen.count(d) > 1})
        failures.append(f"per_dimension has duplicate dimensions: {dupes}")

    if per_dim:
        wins = {}
        for d in per_dim:
            wins[d["winner"]] = wins.get(d["winner"], 0) + 1
        # Allow ties — verdict winner must be ONE of the top-win companies,
        # not necessarily the first one Python's max() picks by dict order.
        max_wins = max(wins.values())
        top_winners = [c for c, n in wins.items() if n == max_wins]
        winner = verdict.get("winner", "")
        if not any(names_match(w, winner) for w in top_winners):
            failures.append(
                f"winner '{winner}' does not win the most "
                f"per_dimension entries (tied top: {top_winners}, all: {wins})")

        dims_won_by_winner = sum(1 for d in per_dim
                                  if names_match(d["winner"], verdict.get("winner", "")))
        expected_confidence = round(100 * dims_won_by_winner / len(per_dim))
        if verdict.get("confidence") != expected_confidence:
            failures.append(
                f"confidence {verdict.get('confidence')} != expected "
                f"{expected_confidence} ({dims_won_by_winner}/{len(per_dim)} dims)")
    else:
        failures.append("per_dimension is empty")

    return failures


def _check_seller(verdict: dict) -> list[str]:
    failures = []
    wp = verdict.get("win_probability")
    if not isinstance(wp, int) or not (0 <= wp <= 100):
        failures.append(f"win_probability {wp} not an int in [0, 100]")
    for i, o in enumerate(verdict.get("objections", [])):
        if not o.get("response", "").strip():
            failures.append(f"objection[{i}] '{o.get('objection')}' has no response")
    return failures


def _check_analyst(verdict: dict, claims_by_company: dict, vertical: str | None) -> list[str]:
    failures = []
    companies = list(claims_by_company.keys())
    matrix = verdict.get("matrix", {})

    for company in companies:
        if company not in matrix:
            failures.append(f"matrix missing company '{company}'")
            continue

    # dimensions: the vertical's registered dimension list when given (the
    # real acceptance check — catches a judge that silently dropped a
    # dimension every company happened to omit); fall back to whatever the
    # verdict itself covers only when vertical is None (self-check below)
    all_dims = (get_dimensions(vertical) if vertical is not None
                else sorted({dim for row in matrix.values() for dim in row}))
    for company in companies:
        row = matrix.get(company, {})
        for dim in all_dims:
            if dim not in row:
                failures.append(f"matrix['{company}'] missing dimension '{dim}'")
                continue
            score = row[dim].get("score")
            if score and score > 0 and not row[dim].get("evidence_ids"):
                failures.append(
                    f"matrix['{company}']['{dim}'] has score {score} but no evidence_ids")

    return failures


def check(verdict, claims_by_company: dict, vertical: str | None = None) -> dict:
    v = _as_dict(verdict)
    mode = v.get("mode")
    valid_ids = _valid_evidence_ids(claims_by_company)

    failures = _check_evidence_ids(v, valid_ids)
    if mode == "buyer":
        failures += _check_buyer(v)
    elif mode == "seller":
        failures += _check_seller(v)
    elif mode == "analyst":
        failures += _check_analyst(v, claims_by_company, vertical)
    else:
        failures.append(f"unknown mode: {mode}")

    return {"passed": not failures, "failures": failures}


# ─── Self-check (offline, hand-built verdicts) ──────────────────────────

def _self_check():
    claims_by_company = {
        "MongoDB": [{"evidence_ids": ["h1", "h2"]}],
        "Pinecone": [{"evidence_ids": ["h3"]}],
    }

    # buyer — passing
    buyer_ok = {
        "mode": "buyer", "winner": "MongoDB", "confidence": 50,
        "per_dimension": [
            {"dimension": "cost", "winner": "MongoDB", "reason": "r", "evidence_ids": ["h1"]},
            {"dimension": "performance", "winner": "Pinecone", "reason": "r", "evidence_ids": ["h3"]},
        ],
    }
    result = check(buyer_ok, claims_by_company)
    assert result["passed"], result["failures"]

    # buyer — failing: wrong confidence + invented evidence_id + duplicate dim
    buyer_bad = {
        "mode": "buyer", "winner": "MongoDB", "confidence": 99,
        "per_dimension": [
            {"dimension": "cost", "winner": "MongoDB", "reason": "r", "evidence_ids": ["h1"]},
            {"dimension": "cost", "winner": "MongoDB", "reason": "r", "evidence_ids": ["made_up"]},
        ],
    }
    result = check(buyer_bad, claims_by_company)
    assert not result["passed"]
    assert any("duplicate" in f for f in result["failures"])
    assert any("confidence" in f for f in result["failures"])
    assert any("made_up" in f for f in result["failures"])

    # seller — passing
    seller_ok = {
        "mode": "seller", "my_company": "MongoDB", "win_probability": 70,
        "objections": [{"objection": "pricing", "response": "we have a discount", "evidence_ids": ["h1"]}],
    }
    result = check(seller_ok, claims_by_company)
    assert result["passed"], result["failures"]

    # seller — failing: out-of-range probability + unanswered objection
    seller_bad = {
        "mode": "seller", "my_company": "MongoDB", "win_probability": 150,
        "objections": [{"objection": "pricing", "response": "", "evidence_ids": ["h1"]}],
    }
    result = check(seller_bad, claims_by_company)
    assert not result["passed"]
    assert any("win_probability" in f for f in result["failures"])
    assert any("no response" in f for f in result["failures"])

    # analyst — passing
    analyst_ok = {
        "mode": "analyst",
        "matrix": {
            "MongoDB": {"cost": {"score": 8, "reason": "r", "evidence_ids": ["h1"]}},
            "Pinecone": {"cost": {"score": 0, "reason": "no evidence", "evidence_ids": []}},
        },
    }
    result = check(analyst_ok, claims_by_company)
    assert result["passed"], result["failures"]

    # analyst — failing: missing company row + score>0 with no evidence
    analyst_bad = {
        "mode": "analyst",
        "matrix": {
            "MongoDB": {"cost": {"score": 8, "reason": "r", "evidence_ids": []}},
        },
    }
    result = check(analyst_bad, claims_by_company)
    assert not result["passed"]
    assert any("missing company" in f for f in result["failures"])
    assert any("no evidence_ids" in f for f in result["failures"])

    print("✅ heads.consistency self-check passed")


if __name__ == "__main__":
    _self_check()
