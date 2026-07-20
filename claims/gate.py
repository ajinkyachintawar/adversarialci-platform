"""
Citation Gate
=============
Deterministic, zero LLM calls. Every evidence_id a claim cites must resolve
to a real chunk (content_hash) in rag_chunks for that company — otherwise the
claim is dropped. Survivors carry resolved source_urls.

Run:  .venv/bin/python -m claims.gate     (self-check, no DB needed)
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_chunk_hashes(company: str) -> dict:
    """{content_hash: source_url} for every chunk stored for this company."""
    from db.atlas import connect, get_collection
    connect()
    col = get_collection("rag_chunks")
    return {
        d["content_hash"]: d["source_url"]
        for d in col.find({"company": company}, {"content_hash": 1, "source_url": 1})
    }


def resolve_claims(claims: list[dict], hashes: dict) -> dict:
    """Pure resolution step — takes the hash map directly so it can be
    unit-tested without a DB connection."""
    verified = []
    dropped = 0
    for claim in claims:
        ids = claim.get("evidence_ids", [])
        if not ids or any(i not in hashes for i in ids):
            dropped += 1
            continue
        verified.append({**claim, "source_urls": sorted({hashes[i] for i in ids})})

    total = len(claims)
    survival_rate = round(len(verified) / total, 3) if total else 0.0
    return {
        "claims": verified,
        "metrics": {
            "claims_total": total,
            "claims_dropped_uncited": dropped,
            "survival_rate": survival_rate,
        },
    }


def gate_claims(company: str, claims: list[dict]) -> dict:
    hashes = load_chunk_hashes(company)
    return resolve_claims(claims, hashes)


def _self_check():
    hashes = {"good1": "https://example.com/a", "good2": "https://example.com/b"}
    claims = [
        {"dimension": "cost", "claim": "cites a real chunk", "stance": "strength",
         "evidence_ids": ["good1"], "strength": 4},
        {"dimension": "cost", "claim": "cites a fake chunk", "stance": "weakness",
         "evidence_ids": ["good1", "bad_hash"], "strength": 2},
    ]
    result = resolve_claims(claims, hashes)

    assert result["metrics"]["claims_total"] == 2
    assert result["metrics"]["claims_dropped_uncited"] == 1
    assert len(result["claims"]) == 1
    assert result["claims"][0]["claim"] == "cites a real chunk"
    assert result["claims"][0]["source_urls"] == ["https://example.com/a"]
    assert result["metrics"]["survival_rate"] == 0.5
    print("✅ claims.gate self-check passed")


if __name__ == "__main__":
    _self_check()
