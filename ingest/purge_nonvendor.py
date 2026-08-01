"""
Purge Non-Vendor Chunks
=======================
Finds chunks/documents whose source_url isn't on the vendor's own domain
(registrable domain derived from vendor_registry pricing_url) and deletes
them from BOTH rag_chunks and rag_documents — deleting only rag_chunks
would let rebuild_chunks() regenerate the junk from the still-present
rag_documents rows.

Dry-run by default. Pass --apply to actually delete.

CLI:  .venv/bin/python -m ingest.purge_nonvendor [Company ...] [--apply] [--vertical database]
      (defaults to Weaviate, Pinecone, MongoDB if no companies given)
"""

import json
import os
import sys
from datetime import datetime, UTC

from ingest.pipeline import registrable_domain, _vendor_domain

DEFAULT_COMPANIES = ["Weaviate", "Pinecone", "MongoDB"]


def purge(companies: list[str], vertical: str = "database", apply: bool = False) -> dict:
    from db.atlas import connect, get_collection
    connect()
    docs_col = get_collection("rag_documents")
    chunks_col = get_collection("rag_chunks")

    report = {"dry_run": not apply, "vertical": vertical, "companies": {}}

    for company in companies:
        vendor_domain = _vendor_domain(company, vertical)
        if not vendor_domain:
            print(f"  ⚠️  {company}: no vendor domain resolved, skipping")
            continue

        before_chunks = chunks_col.count_documents({"company": company})
        by_source = {}
        bad_urls = set()
        for c in chunks_col.find({"company": company}, {"source_url": 1}):
            url = c.get("source_url", "")
            if registrable_domain(url) != vendor_domain:
                bad_urls.add(url)
                by_source[url] = by_source.get(url, 0) + 1

        chunk_count = sum(by_source.values())
        print(f"\n📋 [Purge] {company} (vendor domain: {vendor_domain})")
        print(f"  {'source_url':<70} {'chunks':>7}")
        for url, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
            print(f"  {url:<70} {n:>7}")
        print(f"  -- would delete {chunk_count} of {before_chunks} chunks --")

        deleted_chunks = deleted_docs = 0
        if apply and bad_urls:
            res = chunks_col.delete_many({"company": company, "source_url": {"$in": list(bad_urls)}})
            deleted_chunks = res.deleted_count
            res2 = docs_col.delete_many({"company": company, "source_url": {"$in": list(bad_urls)}})
            deleted_docs = res2.deleted_count

        after_chunks = chunks_col.count_documents({"company": company}) if apply else before_chunks - chunk_count

        report["companies"][company] = {
            "vendor_domain": vendor_domain,
            "before_total_chunks": before_chunks,
            "after_total_chunks": after_chunks,
            "chunks_flagged": chunk_count,
            "by_source_url": by_source,
            "deleted_chunks": deleted_chunks,
            "deleted_documents": deleted_docs,
        }

    os.makedirs("eval/results", exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    label = "_".join(c.lower().replace(" ", "_") for c in companies)
    path = f"eval/results/purge_nonvendor_{label}_{ts}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    mode = "DRY RUN" if not apply else "APPLIED"
    print(f"\n💾 [{mode}] record written -> {path}")

    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    vertical = "database"
    if "--vertical" in sys.argv:
        vertical = sys.argv[sys.argv.index("--vertical") + 1]
        args = [a for a in args if a != vertical]

    companies = args if args else DEFAULT_COMPANIES
    purge(companies, vertical=vertical, apply=apply)
