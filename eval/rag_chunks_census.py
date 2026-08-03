"""
rag_chunks Census
=================
Read-only census of the rag_chunks collection. Per company: total chunks,
chunks by source_type, distinct source_url count (headline metric — Phase 0
exists to move this from ~4 to >=15), first_seen_at age (days) min/median/max,
and provenance (what fraction of chunks come from the vendor's own domain,
per _vendor_domain in ingest/pipeline.py).

Run:  .venv/bin/python -m eval.rag_chunks_census [label]
Out:  eval/results/rag_chunks_census_<label>_<timestamp>.json
"""

import sys
import os
import json
from datetime import datetime, UTC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.atlas import connect, get_collection
from ingest.pipeline import registrable_domain, _vendor_domain


def census(label: str = "baseline") -> dict:
    connect()
    col = get_collection("rag_chunks")
    now = datetime.now(UTC)

    pipeline = [
        {"$group": {
            "_id": {"company": "$company", "source_type": "$source_type",
                     "vertical": "$vertical", "source_url": "$source_url"},
            "chunks": {"$sum": 1},
            "ages": {"$push": "$first_seen_at"},
        }},
    ]
    rows = list(col.aggregate(pipeline))

    per_company = {}
    for r in rows:
        company = r["_id"]["company"]
        source_type = r["_id"]["source_type"]
        vertical = r["_id"]["vertical"]
        source_url = r["_id"]["source_url"]
        chunks = r["chunks"]
        c = per_company.setdefault(company, {
            "total_chunks": 0, "by_source_type": {}, "urls": set(), "ages_days": [],
            "vertical_chunks": {},  # vertical -> chunk count, to resolve the company's dominant vertical
            "url_chunks": {},       # source_url -> chunk count, for provenance classification
        })
        c["total_chunks"] += chunks
        c["by_source_type"][source_type] = c["by_source_type"].get(source_type, 0) + chunks
        c["urls"].add(source_url)
        c["vertical_chunks"][vertical] = c["vertical_chunks"].get(vertical, 0) + chunks
        c["url_chunks"][source_url] = c["url_chunks"].get(source_url, 0) + chunks
        for a in r["ages"]:
            if isinstance(a, datetime):
                if a.tzinfo is None:
                    a = a.replace(tzinfo=UTC)
                c["ages_days"].append((now - a).days)

    result = {"label": label, "timestamp": now.isoformat(), "by_company": {}}
    total_chunks = 0
    total_first_party = 0
    total_classified = 0
    for company, c in per_company.items():
        ages = sorted(c["ages_days"])
        total_chunks += c["total_chunks"]

        # vertical varies per company (database/cloud/crm) — use the vertical that
        # actually shows up on this company's chunks, not a hardcoded default.
        vertical = max(c["vertical_chunks"], key=c["vertical_chunks"].get)
        vendor_domain = _vendor_domain(company, vertical)

        first_party_chunks = third_party_chunks = provenance_pct = None
        third_party_urls = []
        if vendor_domain is not None:
            first_party_chunks = 0
            third_party_chunks = 0
            third_party_counts = {}
            for url, n in c["url_chunks"].items():
                if registrable_domain(url) == vendor_domain:
                    first_party_chunks += n
                else:
                    third_party_chunks += n
                    third_party_counts[url] = n
            provenance_pct = round(100 * first_party_chunks / c["total_chunks"], 1) if c["total_chunks"] else None
            third_party_urls = [
                {"source_url": url, "chunks": n}
                for url, n in sorted(third_party_counts.items(), key=lambda kv: -kv[1])
            ]
            total_first_party += first_party_chunks
            total_classified += c["total_chunks"]

        result["by_company"][company] = {
            "total_chunks": c["total_chunks"],
            "by_source_type": c["by_source_type"],
            "distinct_urls": len(c["urls"]),
            "age_days": {
                "min": ages[0] if ages else None,
                "median": ages[len(ages) // 2] if ages else None,
                "max": ages[-1] if ages else None,
            },
            "vendor_domain": vendor_domain,
            "first_party_chunks": first_party_chunks,
            "third_party_chunks": third_party_chunks,
            "provenance_pct": provenance_pct,
            "third_party_urls": third_party_urls,
        }
    result["totals"] = {
        "companies": len(per_company),
        "chunks": total_chunks,
        "provenance_pct": round(100 * total_first_party / total_classified, 1) if total_classified else None,
    }

    os.makedirs("eval/results", exist_ok=True)
    path = f"eval/results/rag_chunks_census_{label}_{now.strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    # worst-first: unresolved vendor (None) sorts last, not "worst" — it's unmeasured.
    def sort_key(kv):
        pct = kv[1]["provenance_pct"]
        return (pct is None, pct if pct is not None else 0)

    print(f"{'company':<15}{'chunks':>8}{'urls':>7}{'min':>6}{'med':>6}{'max':>6}{'1st-party%':>12}")
    for company, s in sorted(result["by_company"].items(), key=sort_key):
        a = s["age_days"]
        pct = f"{s['provenance_pct']:.1f}" if s["provenance_pct"] is not None else "N/A"
        print(f"{company:<15}{s['total_chunks']:>8}{s['distinct_urls']:>7}"
              f"{a['min']:>6}{a['median']:>6}{a['max']:>6}{pct:>12}")
    corp_pct = result["totals"]["provenance_pct"]
    corp_pct_str = f"{corp_pct:.1f}%" if corp_pct is not None else "N/A"
    print(f"{'TOTAL':<15}{result['totals']['chunks']:>8}   ({result['totals']['companies']} companies, "
          f"{corp_pct_str} 1st-party)")
    print(f"saved -> {path}")
    return result


if __name__ == "__main__":
    census(sys.argv[1] if len(sys.argv) > 1 else "baseline")
