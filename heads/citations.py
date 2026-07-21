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
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
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

    print("✅ heads.citations self-check passed")


if __name__ == "__main__":
    _self_check()
