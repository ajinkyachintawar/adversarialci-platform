"""
Head Evidence Gathering
=======================
Single entry point every head calls first: extract -> gate per company.
Claims never bypass claims.gate before reaching a head prompt.

Run:  .venv/bin/python -m heads.evidence MongoDB Pinecone database
"""

import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claims.extractor import extract_claims
from claims.gate import gate_claims


def _corpus_fingerprint(company: str) -> str:
    """Cheap change-detector for a company's rag_chunks slice: doc count +
    newest last_seen_at. Ingestion refresh changes either -> cache miss."""
    from db.atlas import get_collection
    col = get_collection("rag_chunks")
    count = col.count_documents({"company": company})
    newest = col.find_one({"company": company}, {"last_seen_at": 1},
                          sort=[("last_seen_at", -1)])
    ts = (newest or {}).get("last_seen_at")
    return f"{count}:{ts}"


def _gather_one(company: str, vertical: str) -> tuple[list, dict, bool]:
    """Extract + gate one company, reusing the Atlas claims cache when the
    underlying chunk corpus hasn't changed. Claims are a pure function of the
    corpus, so a fingerprint match means the cached gated claims are current."""
    from db.atlas import get_collection
    cache = get_collection("claims_cache")
    fp = _corpus_fingerprint(company)

    hit = cache.find_one({"company": company, "vertical": vertical, "fingerprint": fp})
    if hit:
        print(f"  🏢 {company}: {len(hit['claims'])} gated claims (cached)")
        return hit["claims"], hit["metrics"], True

    extracted = extract_claims(company, vertical)
    extracted.pop("_rows", None)
    gated = gate_claims(company, extracted["claims"])
    metrics = {"extraction": extracted["metrics"], "gate": gated["metrics"]}
    print(f"  🏢 {company}: {extracted['metrics']['claims_extracted']} extracted -> "
          f"{len(gated['claims'])} gated "
          f"({round(gated['metrics']['survival_rate'] * 100, 1)}% survival)")

    cache.replace_one(
        {"company": company, "vertical": vertical},
        {"company": company, "vertical": vertical, "fingerprint": fp,
         "claims": gated["claims"], "metrics": metrics,
         "cached_at": datetime.utcnow()},
        upsert=True,
    )
    return gated["claims"], metrics, False


last_gather_seconds = 0.0  # wall time of the most recent gather() — read by
                           # heads/runner.py for the session's stage timings
                           # (same module-global pattern as llm.py::call_count)
last_gather_cached = False  # True when every company came from claims_cache


def gather(companies: list[str], vertical: str) -> dict:
    """Returns {"claims_by_company": {company: [gated claims]}, "metrics": {...}}."""
    global last_gather_seconds, last_gather_cached
    t0 = time.time()
    claims_by_company = {}
    metrics_by_company = {}

    cached = []
    for company in companies:
        claims, metrics, was_cached = _gather_one(company, vertical)
        claims_by_company[company] = claims
        metrics_by_company[company] = metrics
        cached.append(was_cached)

    last_gather_seconds = round(time.time() - t0, 1)
    last_gather_cached = all(cached)

    total_claims = sum(len(c) for c in claims_by_company.values())
    return {
        "claims_by_company": claims_by_company,
        "metrics": {
            "companies": len(companies),
            "total_gated_claims": total_claims,
            "by_company": metrics_by_company,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: -m heads.evidence <Company> [Company2 ...] <vertical>")
        sys.exit(1)
    *companies, vertical = sys.argv[1:]
    result = gather(companies, vertical)
    print(f"\n📊 total gated claims: {result['metrics']['total_gated_claims']}")
