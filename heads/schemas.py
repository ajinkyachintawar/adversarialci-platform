"""
Head Verdict Schemas
====================
Pydantic v2 contracts for the three mode heads (buyer/seller/analyst) — these
ARE the wire format persisted as `verdict_json` in court_sessions. Every list
item that claims something must cite evidence_ids (chunk content_hashes
resolved by claims.gate) — the one exception is AnalystVerdict's
DimensionScore, which allows an empty list for the "no evidence, score=0"
case (see heads/analyst.py); heads/consistency.py enforces non-empty when
score > 0.

Also provides parse_verdict_json(raw, model_cls): strips markdown fences,
salvages truncated JSON (same rfind trick as claims/extractor.py, adapted for
a top-level JSON *object* instead of an array), and validates against the
given pydantic model. Raises ValueError on unrecoverable JSON / ValidationError
on schema mismatch — callers do one re-ask then propagate.

Run:  .venv/bin/python -m heads.schemas    (self-check, no network/DB)
"""

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class CitedItem(BaseModel):
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
    confidence: int  # 0-100
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
    win_probability: int  # 0-100
    advantages: list[CitedItem]
    vulnerabilities: list[CitedItem]
    objections: list[Objection]
    landmines: list[CitedItem]  # traps to set for the competitor
    talk_tracks: list[str]
    do_not_say: list[str]


class DimensionScore(BaseModel):
    score: int = Field(ge=0, le=10)
    reason: str
    # empty only for the no-evidence/score==0 case — see module docstring
    evidence_ids: list[str] = []


class AnalystVerdict(BaseModel):
    mode: Literal["analyst"] = "analyst"
    matrix: dict[str, dict[str, DimensionScore]]  # company -> dimension -> score
    summary: str


def normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def names_match(a: str, b: str) -> bool:
    """Tolerant company-name match, shared by heads/buyer.py::
    recompute_confidence and heads/consistency.py::_check_buyer so both
    compute the same winner-count identity: normalized equality, or one
    normalized name containing the other (e.g. judge writes "Mongo" for
    "MongoDB"). Symmetric and deterministic."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return na == nb
    return na == nb or na in nb or nb in na


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def _close_open_brackets(text: str) -> str:
    """Return the closing brace/bracket suffix that balances `text`,
    string-aware (so a literal '{' inside a quoted value isn't counted) and
    closed in the correct innermost-first order."""
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return "".join(reversed(stack))


def parse_verdict_json(raw: str, model_cls: type[BaseModel], resolve_ids=None) -> BaseModel:
    """Strip fences, parse JSON (salvaging truncation), optionally resolve
    citations (resolve_ids: dict -> dict, applied before validation — see
    heads/citations.py::resolve_claim_ids, used by buyer/seller/analyst to
    turn the LLM's claim_ids into real evidence_ids), validate against
    model_cls. Raises ValueError (bad/unsalvageable JSON) or ValidationError
    (schema mismatch) — caller does one re-ask, then propagates."""
    if raw is None:
        raise ValueError("empty LLM response")
    text = _strip_fences(raw)

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # truncated mid-object at max_tokens: cut back to the last complete
        # "}," or "]," (whichever is later — a finished nested object or
        # array element), then close every brace/bracket still open at that
        # point. Mirrors the claims/extractor.py rfind trick, adapted for a
        # top-level object instead of a top-level array.
        cut = max(text.rfind("},"), text.rfind("],"))
        if cut == -1:
            raise ValueError("could not salvage truncated JSON object")
        salvaged = text[:cut + 1]
        obj = json.loads(salvaged + _close_open_brackets(salvaged))

    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")

    if resolve_ids is not None:
        obj = resolve_ids(obj)

    return model_cls(**obj)


def _self_check():
    good_buyer = {
        "mode": "buyer", "winner": "MongoDB", "confidence": 67,
        "per_dimension": [
            {"dimension": "cost", "winner": "MongoDB", "reason": "cheaper tier",
             "evidence_ids": ["h1"]},
            {"dimension": "performance", "winner": "Pinecone", "reason": "faster p99",
             "evidence_ids": ["h2"]},
        ],
        "summary": "MongoDB fits the budget-constrained profile.",
        "caveats": ["Pricing may have changed"],
    }
    v = BuyerVerdict(**good_buyer)
    assert v.winner == "MongoDB"

    raw = "```json\n" + json.dumps(good_buyer) + "\n```"
    parsed = parse_verdict_json(raw, BuyerVerdict)
    assert parsed.confidence == 67

    # truncated JSON salvage: cut off after the per_dimension array closes
    # (before summary/caveats) — the JSON itself recovers cleanly; whether
    # the resulting object still satisfies the schema is a separate concern
    # (summary is required, so this particular cut correctly raises
    # ValidationError rather than silently accepting a bogus verdict).
    full = json.dumps(good_buyer)
    cut = full.rfind("],") + 1  # end of the per_dimension array
    truncated = full[:cut]
    try:
        parse_verdict_json(truncated, BuyerVerdict)
        assert False, "expected ValidationError — summary field was truncated away"
    except ValidationError:
        pass  # correct: truncated JSON recovered, but schema validation caught the gap

    bad = {"mode": "buyer", "winner": "MongoDB"}  # missing required fields
    try:
        BuyerVerdict(**bad)
        assert False, "should have raised"
    except ValidationError:
        pass

    assert names_match("MongoDB", "mongodb")
    assert names_match("Mongo", "MongoDB")  # tolerant substring match
    assert names_match("MongoDB", "Mongo")  # symmetric
    assert not names_match("MongoDB", "Pinecone")

    print("✅ heads.schemas self-check passed")


if __name__ == "__main__":
    _self_check()
