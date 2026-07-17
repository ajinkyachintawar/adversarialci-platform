"""
Corpus Health Snapshot
======================
Read-only census of research_data quality. Run before/after any
ingestion change and commit the JSON so improvements are provable.

Run:  python eval/corpus_snapshot.py [label]
Out:  eval/results/corpus_<label>_<timestamp>.json
"""

import sys
import os
import re
import json
import hashlib
from collections import Counter, defaultdict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.atlas import connect, get_collection

JUNK_PATTERNS = [
    "cookie", "accept all", "sign up", "sign in", "log in", "subscribe",
    "newsletter", "privacy policy", "terms of service", "all rights reserved",
    "get started free", "start free", "contact sales", "learn more",
]

URL_RE = re.compile(r"https?://\S+")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def looks_truncated(b: str) -> bool:
    t = b.rstrip()
    if not t:
        return False
    # ends without sentence-final punctuation AND is near a known cap
    near_cap = len(t) in range(490, 512) or len(t) in range(780, 812)
    return near_cap or (len(t) > 80 and t[-1] not in ".!?)\"'›»]")


def looks_junk(b: str) -> bool:
    low = b.lower()
    return len(b.strip()) < 30 or any(p in low for p in JUNK_PATTERNS)


def snapshot(label: str = "baseline") -> dict:
    connect()
    col = get_collection("research_data")
    now = datetime.utcnow()

    docs = list(col.find({}, {
        "company": 1, "source_type": 1, "data_type": 1,
        "content_bullets": 1, "verified": 1, "confidence_score": 1,
        "scraped_at": 1,
    }))

    per_company = defaultdict(lambda: defaultdict(lambda: {
        "docs": 0, "bullets": 0, "dup_bullets": 0, "junk_bullets": 0,
        "truncated_bullets": 0, "bullets_with_url": 0, "chars": 0,
    }))
    global_hashes = Counter()
    ages_days = []

    # first pass: hash counts for dup detection (per company+source)
    seen = defaultdict(Counter)
    for d in docs:
        key = (d.get("company"), d.get("source_type"))
        for b in d.get("content_bullets", []):
            seen[key][hashlib.md5(norm(b).encode()).hexdigest()] += 1

    for d in docs:
        company = d.get("company", "?")
        source = d.get("source_type", "?")
        s = per_company[company][source]
        s["docs"] += 1
        sa = d.get("scraped_at")
        if isinstance(sa, datetime):
            ages_days.append((now - sa).days)
        for b in d.get("content_bullets", []):
            h = hashlib.md5(norm(b).encode()).hexdigest()
            s["bullets"] += 1
            s["chars"] += len(b)
            if seen[(company, source)][h] > 1:
                s["dup_bullets"] += 1
            if looks_junk(b):
                s["junk_bullets"] += 1
            if looks_truncated(b):
                s["truncated_bullets"] += 1
            if URL_RE.search(b):
                s["bullets_with_url"] += 1
            global_hashes[h] += 1

    total_bullets = sum(global_hashes.values())
    unique_bullets = len(global_hashes)
    dup_bullets = total_bullets - unique_bullets

    def agg(field):
        return sum(s[field] for c in per_company.values() for s in c.values())

    result = {
        "label": label,
        "timestamp": now.isoformat(),
        "totals": {
            "research_docs": len(docs),
            "companies": len(per_company),
            "bullets": total_bullets,
            "unique_bullets": unique_bullets,
            "duplicate_bullets": dup_bullets,
            "duplicate_pct": round(dup_bullets / total_bullets * 100, 1) if total_bullets else 0,
            "junk_bullets": agg("junk_bullets"),
            "junk_pct": round(agg("junk_bullets") / total_bullets * 100, 1) if total_bullets else 0,
            "truncated_bullets": agg("truncated_bullets"),
            "truncated_pct": round(agg("truncated_bullets") / total_bullets * 100, 1) if total_bullets else 0,
            "bullets_with_url": agg("bullets_with_url"),
            "url_pct": round(agg("bullets_with_url") / total_bullets * 100, 1) if total_bullets else 0,
            "avg_bullet_chars": round(agg("chars") / total_bullets, 1) if total_bullets else 0,
        },
        "freshness_days": {
            "newest": min(ages_days) if ages_days else None,
            "oldest": max(ages_days) if ages_days else None,
            "median": sorted(ages_days)[len(ages_days) // 2] if ages_days else None,
        },
        "by_company": {
            c: {src: dict(stats) for src, stats in sources.items()}
            for c, sources in sorted(per_company.items())
        },
    }

    os.makedirs("eval/results", exist_ok=True)
    path = f"eval/results/corpus_{label}_{now.strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    t = result["totals"]
    print(f"Docs {t['research_docs']} | companies {t['companies']} | bullets {t['bullets']}")
    print(f"dup {t['duplicate_pct']}% | junk {t['junk_pct']}% | "
          f"truncated {t['truncated_pct']}% | with-URL {t['url_pct']}%")
    print(f"freshness (days): {result['freshness_days']}")
    print(f"saved -> {path}")
    return result


if __name__ == "__main__":
    snapshot(sys.argv[1] if len(sys.argv) > 1 else "baseline")
