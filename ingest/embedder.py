"""
Embedder
========
Gemini embeddings (gemini-embedding-001, 768 dims) for rag_chunks.
768 matches the Atlas vector index; cosine similarity, so no normalization
needed. Free tier — batches of 100 with backoff on 429.

Run:  .venv/bin/python -m ingest.embedder            # embed all missing
      .venv/bin/python -m ingest.embedder MongoDB    # one company
"""

import sys
import time
import requests
from config import GEMINI_API_KEYS

_key_idx = 0  # rotates to the next key on quota exhaustion (per-project quotas)


def _rotate_key() -> bool:
    """Switch to the next API key. Returns False when all keys are spent."""
    global _key_idx
    if _key_idx + 1 >= len(GEMINI_API_KEYS):
        return False
    _key_idx += 1
    print(f"  🔑 [Embed] quota hit — rotating to fallback key #{_key_idx + 1}")
    return True

MODEL = "gemini-embedding-001"
BATCH_URL = (f"https://generativelanguage.googleapis.com/v1beta/"
             f"models/{MODEL}:batchEmbedContents")
DIMS = 768
# each batch item counts against the free-tier RPM/TPM quota — small batches
# + a pause between them stays under it (measured: 100-item batch → instant 429)
BATCH_SIZE = 20
BATCH_PAUSE_S = 15


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]] | None:
    """Embed up to BATCH_SIZE texts. Returns vectors or None on failure."""
    if not texts:
        return []
    body = {"requests": [
        {"model": f"models/{MODEL}",
         "content": {"parts": [{"text": t[:8000]}]},
         "outputDimensionality": DIMS,
         "taskType": task_type}
        for t in texts
    ]}
    backoffs = [5, 15, 45]
    attempt = 0
    while attempt <= len(backoffs):
        try:
            r = requests.post(BATCH_URL,
                              params={"key": GEMINI_API_KEYS[_key_idx]},
                              json=body, timeout=60)
        except requests.RequestException as e:
            print(f"  ⚠️  [Embed] request error: {e}")
            return None
        if r.status_code == 200:
            return [e["values"] for e in r.json().get("embeddings", [])]
        if r.status_code == 429:
            # daily quota (RPD) → rotate key immediately; per-minute → backoff
            if "PerDay" in r.text or "plan and billing" in r.text:
                if _rotate_key():
                    continue  # fresh quota, retry immediately, same attempt
                print("  ⚠️  [Embed] all API keys exhausted for today")
                return None
            if attempt < len(backoffs):
                wait = backoffs[attempt]
                print(f"  ⏳ [Embed] rate limited, waiting {wait}s...")
                time.sleep(wait)
                attempt += 1
                continue
        print(f"  ⚠️  [Embed] failed ({r.status_code}): {r.text[:200]}")
        return None
    return None


def embed_query(query: str) -> list[float] | None:
    """Embed one query string (RETRIEVAL_QUERY task type)."""
    vecs = embed_texts([query], task_type="RETRIEVAL_QUERY")
    return vecs[0] if vecs else None


def embed_missing_chunks(company: str | None = None) -> dict:
    """Embed all rag_chunks lacking an embedding. Idempotent."""
    from db.atlas import connect, get_collection
    connect()
    col = get_collection("rag_chunks")

    query = {"embedding": {"$exists": False}}
    if company:
        query["company"] = company

    todo = list(col.find(query, {"text": 1}))
    print(f"🧬 [Embed] {len(todo)} chunks to embed"
          + (f" for {company}" if company else ""))

    done = failed = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        vecs = embed_texts([d["text"] for d in batch])
        if vecs is None or len(vecs) != len(batch):
            failed += len(batch)
            continue
        for doc, vec in zip(batch, vecs):
            # embedding_model recorded so a future model swap can find and
            # re-embed stale vectors instead of silently mixing spaces
            col.update_one({"_id": doc["_id"]},
                           {"$set": {"embedding": vec, "embedding_model": MODEL}})
        done += len(batch)
        print(f"  ✅ {done}/{len(todo)} embedded")
        if i + BATCH_SIZE < len(todo):
            time.sleep(BATCH_PAUSE_S)

    return {"embedded": done, "failed": failed}


def remove_near_duplicates(threshold: float = 0.95,
                           company: str | None = None) -> dict:
    """
    Delete chunks whose embedding is near-identical (cosine >= threshold)
    to an earlier chunk of the same company. Catches repeated page blocks
    that exact-hash dedup misses. Keeps the first occurrence.
    """
    from db.atlas import connect, get_collection
    connect()
    col = get_collection("rag_chunks")

    removed = 0
    companies = [company] if company else col.distinct("company")
    for company in companies:
        docs = list(col.find(
            {"company": company, "embedding": {"$exists": True}},
            {"embedding": 1},
        ).sort([("created_at", 1), ("chunk_index", 1)]))

        # ponytail: O(n^2) pairwise scan — fine at hundreds of chunks per
        # company, switch to ANN self-join if a company exceeds ~5k chunks
        kept: list[list[float]] = []
        for d in docs:
            v = d["embedding"]
            nv = sum(x * x for x in v) ** 0.5
            is_dup = False
            for kv, knv in kept:
                dot = sum(a * b for a, b in zip(v, kv))
                if dot / (nv * knv) >= threshold:
                    is_dup = True
                    break
            if is_dup:
                col.delete_one({"_id": d["_id"]})
                removed += 1
            else:
                kept.append((v, nv))
        print(f"  🧹 {company}: {removed} near-dups removed so far")

    return {"removed": removed}


if __name__ == "__main__":
    if "--dedup" in sys.argv:
        print(remove_near_duplicates())
    else:
        company = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
        print(embed_missing_chunks(company))
