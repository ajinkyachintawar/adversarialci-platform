"""
Ingest Pipeline
===============
Orchestrator for the new RAG ingestion path: Firecrawl -> clean markdown ->
chunks with metadata -> store. Runs alongside (never replaces) the existing
bullet pipeline in sources/*.py.

Sources, in order:
  a) pricing page (vendor_registry pricing_url)
  b) Tavily URL-follow: run vertical query templates, collect result URLs
     (deduped, capped at max_tavily_urls TOTAL to bound Firecrawl spend),
     firecrawl-scrape each.

CLI:  .venv/bin/python -m ingest.pipeline <Company> [vertical] [--dry-run]
"""

import sys
from datetime import datetime

from tavily import TavilyClient
from config import TAVILY_API_KEY
from vendor_registry import get_vendor_urls
from verticals import get_tavily_templates
from sources.firecrawl_client import scrape_url, get_credits_used
from ingest.chunker import chunk_stats
from ingest.store import save_document, record_metrics, flush_dry_run

SKIP_DOMAINS = ("youtube.com", "reddit.com")


def _scrape_and_store(company: str, vertical: str, url: str, source_type: str, dry_run: bool) -> dict:
    """Scrape one URL, chunk it, save it. Returns per-source stats for the summary table."""
    credits_before = get_credits_used()
    scraped = scrape_url(url)
    if not scraped:
        return {"source_type": source_type, "url": url, "docs": 0, "chunks_kept": 0,
                "chunks_junk_dropped": 0, "credits": 0, "seconds": 0}

    stats = chunk_stats(scraped["markdown"])
    chunks = stats["kept"]

    doc = {
        "company": company,
        "vertical": vertical,
        "source_type": source_type,
        "source_url": url,
        "title": scraped.get("title"),
        "markdown": scraped["markdown"],
        "scraped_at": datetime.utcnow(),
        "firecrawl": True,
    }
    save_document(doc, chunks, dry_run=dry_run)

    credits = get_credits_used() - credits_before
    metrics = {
        "url": url,
        "seconds": scraped["seconds"],
        "markdown_chars": len(scraped["markdown"]),
        "chunks_total": stats["chunks_total"],
        "chunks_kept": len(chunks),
        "chunks_junk_dropped": stats["junk_dropped"],
        "firecrawl_credits": credits,
    }
    record_metrics(company, source_type, metrics, dry_run=dry_run)

    return {"source_type": source_type, "url": url, "docs": 1, "chunks_kept": len(chunks),
            "chunks_junk_dropped": stats["junk_dropped"], "credits": credits,
            "seconds": scraped["seconds"]}


def _collect_tavily_urls(company: str, vertical: str, exclude: set, max_urls: int) -> list[str]:
    templates = get_tavily_templates(vertical)
    if not templates:
        print(f"  ⚠️  No tavily query templates for vertical '{vertical}'")
        return []

    client = TavilyClient(api_key=TAVILY_API_KEY)
    year = datetime.now().year
    seen = set(exclude)
    candidates = []

    for template in templates:
        query = template.format(company=company, year=year)
        try:
            results = client.search(query=query, max_results=3)
        except Exception as e:
            print(f"  ⚠️  [Tavily] error for '{query}': {e}")
            continue
        for r in results.get("results", []):
            url = r.get("url", "")
            if not url or url in seen:
                continue
            if any(d in url.lower() for d in SKIP_DOMAINS):
                continue
            seen.add(url)
            candidates.append(url)

    return candidates[:max_urls]  # cap TOTAL, not per-query, to bound Firecrawl spend


def ingest_company(company: str, vertical: str = "database", dry_run: bool = False,
                    max_tavily_urls: int = 3) -> dict:
    print(f"🚀 [Ingest] {company} ({vertical}) — dry_run={dry_run}")
    results = []
    scraped_urls = set()

    # a) pricing page
    vendor_data = get_vendor_urls(company, vertical)
    pricing_url = vendor_data.get("pricing_url") if vendor_data else None
    if pricing_url:
        print(f"  💰 [Pricing] scraping {pricing_url}")
        results.append(_scrape_and_store(company, vertical, pricing_url, "pricing_scrape", dry_run))
        scraped_urls.add(pricing_url)
    else:
        print(f"  ⚠️  No pricing URL configured for {company}, skipping pricing scrape")

    # b) tavily url-follow
    print(f"  🌐 [Tavily] collecting candidate URLs (cap={max_tavily_urls})")
    tavily_urls = _collect_tavily_urls(company, vertical, scraped_urls, max_tavily_urls)
    for url in tavily_urls:
        print(f"  🌐 [Tavily] scraping {url}")
        results.append(_scrape_and_store(company, vertical, url, "tavily_page", dry_run))

    # summary table
    print(f"\n📊 [Ingest] summary for {company}")
    print(f"  {'source':<16} {'docs':>5} {'kept':>6} {'dropped':>8} {'credits':>8} {'seconds':>8}")
    for r in results:
        print(f"  {r['source_type']:<16} {r['docs']:>5} {r['chunks_kept']:>6} "
              f"{r['chunks_junk_dropped']:>8} {r['credits']:>8} {r['seconds']:>8.1f}")

    summary = {
        "company": company,
        "vertical": vertical,
        "dry_run": dry_run,
        "sources": results,
        "totals": {
            "docs": sum(r["docs"] for r in results),
            "chunks_kept": sum(r["chunks_kept"] for r in results),
            "chunks_junk_dropped": sum(r["chunks_junk_dropped"] for r in results),
            "credits": sum(r["credits"] for r in results),
            "seconds": round(sum(r["seconds"] for r in results), 1),
        },
    }

    if dry_run:
        flush_dry_run(f"{company.lower().replace(' ', '_')}_{vertical}")

    return summary


def rebuild_chunks() -> dict:
    """
    Re-chunk every stored rag_document with the current chunker and replace
    its chunks. No re-scraping (raw markdown is stored) — run after any
    chunker change, then embed_missing_chunks() + remove_near_duplicates().
    """
    from db.atlas import connect, get_collection
    connect()
    docs_col = get_collection("rag_documents")
    chunks_col = get_collection("rag_chunks")

    rebuilt = total_chunks = 0
    for doc in docs_col.find({}):
        stats = chunk_stats(doc["markdown"])
        chunks_col.delete_many({"company": doc["company"],
                                "doc_hash": doc["content_hash"]})
        save_document(
            {k: doc[k] for k in ("company", "vertical", "source_type",
                                 "source_url", "title", "markdown",
                                 "scraped_at", "firecrawl")},
            stats["kept"],
        )
        rebuilt += 1
        total_chunks += len(stats["kept"])
        print(f"  🔁 {doc['company']} {doc['source_type']}: {len(stats['kept'])} chunks")

    return {"docs_rebuilt": rebuilt, "chunks": total_chunks}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv

    if "--rebuild" in sys.argv:
        print(rebuild_chunks())
        sys.exit(0)

    company = args[0] if args else None
    vertical = args[1] if len(args) > 1 else "database"

    if not company:
        print("Usage: .venv/bin/python -m ingest.pipeline <Company> [vertical] [--dry-run|--rebuild]")
        sys.exit(1)

    ingest_company(company, vertical, dry_run=dry_run)
