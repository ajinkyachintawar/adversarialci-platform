"""
Claim Citations Helper
=======================
Shared by heads/buyer.py, seller.py, analyst.py so their judge/synthesis
prompts never render a raw 64-char evidence hash (Phase 1's E-label lesson,
applied to the judge/synthesis prompts too — hashes bloat prompts and LLMs
can't reliably copy them).

label_and_render assigns global C1..Cn labels across every company in a
prompt (encounter order) and renders one no-evidence-shown block per company.
The LLM is asked to cite claim_ids (["C7", "C12"]); resolve_claim_ids walks
the parsed verdict dict afterward and replaces every "claim_ids" list with
the union of the cited claims' real evidence_ids (deduped, order-stable).
Invalid/unknown labels are dropped silently — same tolerance as
claims/extractor.py::_parse_claims — so an item whose labels all resolve to
nothing ends up with evidence_ids: [], caught downstream by schema
validation / consistency exactly as an invented hash would have been before.

The debate rounds (buyer round1/round2, seller red-team/counter) keep their
own local per-list index protocol — this module is only for the judge/
synthesis calls where hashes used to leak into the prompt.

Run:  .venv/bin/python -m heads.citations   (self-check, no network)
"""

import re

# Anchored on the word claim(s) — connective words are case-insensitive via
# the scoped (?i:...) group, but the label itself (C\d+) stays case-sensitive
# so we never touch lowercase tokens like "c5.large". A bare "(C55)" with no
# "claim" anchor is deliberately NOT covered — see module docstring / brief:
# stripping unanchored labels risks mangling real vendor text (C4 instances,
# P99, C++). The optional connective + optional surrounding bracket covers
# ", as stated in claim C55", "(claim C55)", "[claim C7]", "per claim C16",
# "see claim C3", "according to claim C12", and plural lists like
# "as stated in claims C1, C2 and C3".
_REF_PHRASE = (
    r"[\(\[]?(?:(?i:as\s+stated\s+in|according\s+to|per|see)\s+)?"
    r"(?i:claims?)\s+C\d+(?:\s*(?:,\s*(?:and\s+)?|\s+and\s+)C\d+)*(?:\s*[\)\]])?"
)
# Two passes so the comma consumed is always the one that actually
# delimited the aside, never the sentence's own punctuation:
#  - a leading ", " belongs to the aside (", as stated in claim C55") ->
#    eat it and stop, leave whatever follows untouched.
#  - no leading comma (mid-sentence "per claim C16", a bracketed
#    "(claim C55)", or one anchored right after a colon) -> the aside's
#    OWN trailing ", " (if any) is what needs eating instead.
_CLAIM_REF_LEADING_COMMA_RE = re.compile(r",\s*" + _REF_PHRASE)
_CLAIM_REF_BARE_RE = re.compile(_REF_PHRASE + r"(?:\s*,\s*)?")


def strip_claim_refs(text: str) -> str:
    """Remove model-authored claim-label references from free text (e.g.
    "X is free, as stated in claim C55" -> "X is free"). Pure string
    cleanup — never touches evidence_ids or the claim_ids resolution.
    Returns the input unchanged (same object) when there's nothing to
    strip, so no-op callers see zero stray whitespace changes."""
    if not isinstance(text, str) or not text:
        return text
    cleaned = _CLAIM_REF_LEADING_COMMA_RE.sub("", text)
    cleaned = _CLAIM_REF_BARE_RE.sub("", cleaned)
    if cleaned == text:
        return text
    cleaned = re.sub(r"^,\s*", "", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,!?;:])", r"\1", cleaned)
    return cleaned.strip()


def label_and_render(claims_by_company: dict) -> tuple[dict[str, str], dict[str, dict]]:
    """Global C1..Cn labels across every company (encounter order). Returns
    (block_by_company, label_to_claim) — block_by_company renders each
    company's claims with labels but NO evidence ids; label_to_claim maps
    "C7" -> the claim dict, for resolve_claim_ids to use after parsing."""
    label_to_claim: dict[str, dict] = {}
    block_by_company: dict[str, str] = {}
    n = 1
    for company, claims in claims_by_company.items():
        lines = []
        for c in claims:
            label = f"C{n}"
            label_to_claim[label] = c
            lines.append(f"  [{label}] ({c['dimension']}, {c['stance']}, "
                         f"strength {c['strength']}) {c['claim']}")
            n += 1
        block_by_company[company] = "\n".join(lines)
    return block_by_company, label_to_claim


def resolve_claim_ids(obj: dict, label_to_claim: dict) -> dict:
    """Walk a parsed (pre-validation) verdict dict in place: every
    "claim_ids" list becomes an "evidence_ids" list, resolved to the union of
    the cited claims' real evidence_ids (deduped, order-stable). Unknown
    labels are dropped."""

    def resolve(claim_ids):
        seen, ids = set(), []
        for cid in claim_ids or []:
            claim = label_to_claim.get(cid)
            if not claim:
                continue
            for eid in claim.get("evidence_ids", []):
                if eid not in seen:
                    seen.add(eid)
                    ids.append(eid)
        return ids

    def walk(node):
        if isinstance(node, dict):
            if "claim_ids" in node:
                node["evidence_ids"] = resolve(node.pop("claim_ids"))
            for k, v in node.items():
                if isinstance(v, str):
                    node[k] = strip_claim_refs(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str):
                    node[i] = strip_claim_refs(v)
                else:
                    walk(v)

    walk(obj)
    return obj


def _self_check():
    claims_by_company = {
        "MongoDB": [
            {"dimension": "cost", "stance": "strength", "strength": 4,
             "claim": "cheap tier", "evidence_ids": ["h1", "h2"]},
        ],
        "Pinecone": [
            {"dimension": "performance", "stance": "strength", "strength": 5,
             "claim": "fast p99", "evidence_ids": ["h3"]},
        ],
    }
    blocks, label_to_claim = label_and_render(claims_by_company)
    assert set(label_to_claim) == {"C1", "C2"}
    assert "h1" not in blocks["MongoDB"] and "[C1]" in blocks["MongoDB"]
    assert "[C2]" in blocks["Pinecone"]

    obj = {"per_dimension": [
        {"dimension": "cost", "claim_ids": ["C1", "C1", "made_up"]},
        {"dimension": "performance", "claim_ids": ["C2"]},
    ]}
    resolve_claim_ids(obj, label_to_claim)
    assert obj["per_dimension"][0]["evidence_ids"] == ["h1", "h2"]  # deduped, invalid dropped
    assert obj["per_dimension"][1]["evidence_ids"] == ["h3"]
    assert "claim_ids" not in obj["per_dimension"][0]

    # all-invalid labels -> empty list, not dropped/crashed
    obj2 = {"x": {"claim_ids": ["nope"]}}
    resolve_claim_ids(obj2, label_to_claim)
    assert obj2["x"]["evidence_ids"] == []

    # free-text fields get stripped alongside claim_ids resolution, in the
    # same walk (dict string values and list-of-string values both)
    obj3 = {
        "per_dimension": [{"dimension": "cost", "reason": "Weaviate is always free, as stated in claim C55",
                            "claim_ids": ["C1"]}],
        "summary": "ok",
        "caveats": ["Pinecone's performance is superior, as stated in claim C32"],
    }
    resolve_claim_ids(obj3, label_to_claim)
    assert obj3["per_dimension"][0]["reason"] == "Weaviate is always free"
    assert obj3["caveats"][0] == "Pinecone's performance is superior"

    # --- strip_claim_refs: each variant from the brief ---
    cases = [
        ("Weaviate is always free, as stated in claim C55", "Weaviate is always free"),
        ("Weaviate combines dense vector search with BM25 keyword search in a "
         "single query, as stated in claim C75",
         "Weaviate combines dense vector search with BM25 keyword search in a single query"),
        ("Weaviate is the overall winner due to its always-free pricing, as stated "
         "in claim C55, and its ability to handle complex applications, as stated in claim C79",
         "Weaviate is the overall winner due to its always-free pricing, and its "
         "ability to handle complex applications"),
        ("Pinecone's performance is superior, as stated in claim C32", "Pinecone's performance is superior"),
        ("X is cheap (claim C55) for small teams", "X is cheap for small teams"),
        ("See [claim C7] for detail", "See for detail"),
        ("Cost is low per claim C16 here", "Cost is low here"),
        ("Latency is low, see claim C3, in tests", "Latency is low, in tests"),
        ("Both hold, according to claim C12, in practice", "Both hold, in practice"),
        ("Three claims agree: as stated in claims C1, C2 and C3, it scales",
         "Three claims agree: it scales"),
        # Oxford comma — a live run leaked ", and C57." because the label
        # chain stopped at the ", and " separator. Regression case.
        ("X is free, as stated in claims C55, C56, and C57.", "X is free."),
        ("Winner due to pricing, as stated in claims C55 and C79.",
         "Winner due to pricing."),
    ]
    for raw, expected in cases:
        got = strip_claim_refs(raw)
        assert got == expected, f"{raw!r} -> {got!r}, expected {expected!r}"

    # no-op: nothing to strip -> exact same string (no stray whitespace change)
    noop = "MongoDB's scale-out approach is more cost-effective"
    assert strip_claim_refs(noop) == noop

    # must NOT strip: bare labels with no "claim" anchor
    assert strip_claim_refs("Runs fine on a c5.large instance") == "Runs fine on a c5.large instance"
    assert strip_claim_refs("Needs 4 C4 instances to scale") == "Needs 4 C4 instances to scale"

    print("✅ heads.citations self-check passed")


if __name__ == "__main__":
    _self_check()
