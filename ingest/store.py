"""
Ingest Store
============
Persistence for the RAG ingestion path. New collections only —
"rag_documents" and "rag_chunks" — never touches research_data.

dry_run=True never opens a DB connection: results buffer in memory and
flush_dry_run() writes them to eval/results/ as JSON for inspection.
"""

import os
import json
import hashlib
from datetime import datetime

from ingest.chunker import norm

_dry_docs: list[dict] = []
_dry_chunks: list[dict] = []
_dry_metrics: list[dict] = []


def _hash(text: str) -> str:
    return hashlib.md5(norm(text).encode()).hexdigest()


def save_document(doc: dict, chunks: list[str], dry_run: bool = False) -> dict:
    """
    doc: {company, vertical, source_type, source_url, title, markdown, scraped_at, firecrawl}
    chunks: list of chunk text strings (already junk-filtered).

    Returns a small summary dict: {content_hash, chunks_saved}.
    """
    content_hash = _hash(doc["markdown"])
    doc_record = {**doc, "content_hash": content_hash}

    chunk_records = []
    for i, text in enumerate(chunks):
        chunk_records.append({
            "doc_hash": content_hash,
            "company": doc["company"],
            "vertical": doc["vertical"],
            "source_type": doc["source_type"],
            "source_url": doc["source_url"],
            "text": text,
            "chunk_index": i,
            "content_hash": _hash(text),
            "created_at": datetime.utcnow(),
        })

    if dry_run:
        _dry_docs.append(doc_record)
        _dry_chunks.extend(chunk_records)
        return {"content_hash": content_hash, "chunks_saved": len(chunk_records)}

    # ponytail: real-mode path coded per spec but never exercised in this task
    # (all testing is dry-run only) — upsert-by-content_hash is the dedup story.
    from db.atlas import connect, get_collection
    connect()
    docs_col = get_collection("rag_documents")
    chunks_col = get_collection("rag_chunks")

    # staleness guard: a re-scraped page whose content changed gets a new
    # hash — retire the outdated chunks for this (company, url) so retrieval
    # never serves last quarter's pricing next to this quarter's. The old
    # document row is kept (marked superseded) as cheap history.
    chunks_col.delete_many({
        "company": doc["company"],
        "source_url": doc["source_url"],
        "doc_hash": {"$ne": content_hash},
    })
    docs_col.update_many(
        {"company": doc["company"], "source_url": doc["source_url"],
         "content_hash": {"$ne": content_hash}},
        {"$set": {"superseded": True}},
    )

    # dedup is scoped per company: the same page (e.g. a "X vs Y" comparison
    # article) can legitimately be evidence for two companies, and retrieval
    # filters by company — a global hash would silently drop the second copy.
    docs_col.update_one(
        {"company": doc["company"], "content_hash": content_hash},
        {
            "$set": {"last_seen_at": datetime.utcnow()},
            "$setOnInsert": {**doc_record, "first_seen_at": datetime.utcnow()},
        },
        upsert=True,
    )

    deduped = 0
    for c in chunk_records:
        result = chunks_col.update_one(
            {"company": c["company"], "content_hash": c["content_hash"]},
            {
                "$set": {"last_seen_at": datetime.utcnow()},
                "$setOnInsert": {**c, "first_seen_at": datetime.utcnow()},
            },
            upsert=True,
        )
        if result.matched_count:
            deduped += 1

    return {"content_hash": content_hash, "chunks_saved": len(chunk_records), "chunks_deduped": deduped}


def record_metrics(company: str, source_type: str, metrics: dict, dry_run: bool = False):
    metrics = {"company": company, "source_type": source_type, **metrics, "ts": datetime.utcnow()}
    if dry_run:
        _dry_metrics.append(metrics)
        return
    from db.atlas import connect, get_collection
    connect()
    get_collection("scrape_metrics").insert_one(metrics)


def flush_dry_run(label: str) -> str:
    """Write buffered dry-run docs/chunks/metrics to eval/results/ as JSON.
    Markdown is truncated to 500 chars in the JSON to keep it readable;
    chunk text is kept in full."""
    os.makedirs("eval/results", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"eval/results/ingest_dryrun_{label}_{ts}.json"

    docs_out = []
    for d in _dry_docs:
        d2 = dict(d)
        if d2.get("markdown"):
            d2["markdown"] = d2["markdown"][:500]
        if isinstance(d2.get("scraped_at"), datetime):
            d2["scraped_at"] = d2["scraped_at"].isoformat()
        docs_out.append(d2)

    chunks_out = []
    for c in _dry_chunks:
        c2 = dict(c)
        if isinstance(c2.get("created_at"), datetime):
            c2["created_at"] = c2["created_at"].isoformat()
        chunks_out.append(c2)

    metrics_out = []
    for m in _dry_metrics:
        m2 = dict(m)
        if isinstance(m2.get("ts"), datetime):
            m2["ts"] = m2["ts"].isoformat()
        metrics_out.append(m2)

    payload = {
        "label": label,
        "timestamp": datetime.utcnow().isoformat(),
        "docs": docs_out,
        "chunks": chunks_out,
        "metrics": metrics_out,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  💾 dry-run flush -> {path} ({len(docs_out)} docs, {len(chunks_out)} chunks)")
    return path
