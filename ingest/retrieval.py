"""
Retrieval
=========
Vector search over rag_chunks via Atlas $vectorSearch.
Hard company filter first (cross-company contamination guard), then kNN.

setup_index() creates the vector index once (768 dims must match embedder).

Run:  .venv/bin/python -m ingest.retrieval setup
      .venv/bin/python -m ingest.retrieval "pricing free tier limits" MongoDB
"""

import sys
from pymongo.operations import SearchIndexModel
from ingest.embedder import embed_query, DIMS

INDEX_NAME = "rag_chunks_vector"


def setup_index():
    """Create the Atlas vector index on rag_chunks (idempotent-ish: skips if present)."""
    from db.atlas import connect, get_collection
    connect()
    col = get_collection("rag_chunks")

    existing = [i.get("name") for i in col.list_search_indexes()]
    if INDEX_NAME in existing:
        print(f"  ✅ index '{INDEX_NAME}' already exists")
        return

    model = SearchIndexModel(
        definition={
            "fields": [
                {"type": "vector", "path": "embedding",
                 "numDimensions": DIMS, "similarity": "cosine"},
                {"type": "filter", "path": "company"},
                {"type": "filter", "path": "source_type"},
                {"type": "filter", "path": "vertical"},
            ]
        },
        name=INDEX_NAME,
        type="vectorSearch",
    )
    col.create_search_index(model)
    print(f"  🏗️  index '{INDEX_NAME}' creation started (takes ~1 min to build)")


def retrieve(query: str, company: str, k: int = 5,
             source_type: str | None = None, num_candidates: int = 50) -> list[dict]:
    """
    Retrieve top-k chunks for a query, hard-filtered to one company.
    Returns [{text, source_url, source_type, score}, ...] best first.
    """
    from db.atlas import connect, get_collection
    connect()
    col = get_collection("rag_chunks")

    qvec = embed_query(query)
    if qvec is None:
        print("  ⚠️  [Retrieve] query embedding failed")
        return []

    vs_filter = {"company": company}
    if source_type:
        vs_filter["source_type"] = source_type

    pipeline = [
        {"$vectorSearch": {
            "index": INDEX_NAME,
            "path": "embedding",
            "queryVector": qvec,
            "numCandidates": num_candidates,
            "limit": k,
            "filter": vs_filter,
        }},
        {"$project": {
            "_id": 0, "text": 1, "source_url": 1, "source_type": 1,
            "content_hash": 1,
            "score": {"$meta": "vectorSearchScore"},
        }},
    ]
    return list(col.aggregate(pipeline))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_index()
    elif len(sys.argv) > 2:
        for r in retrieve(sys.argv[1], sys.argv[2]):
            print(f"[{r['score']:.3f}] [{r['source_type']}] {r['text'][:140]}")
            print(f"        {r['source_url']}")
    else:
        print('Usage: -m ingest.retrieval setup | -m ingest.retrieval "<query>" <Company>')
