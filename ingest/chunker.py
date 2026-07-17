"""
Chunker
=======
Splits clean Firecrawl markdown into retrieval-sized chunks.
Markdown-aware: splits on headings then paragraphs, packs greedily near
target_chars, hard-splits oversized pieces at sentence boundaries, and
drops junk (cookie banners, nav chrome, etc).

JUNK_PATTERNS / norm() are the shared source of truth for "is this junk /
duplicate" logic — eval/corpus_snapshot.py imports them from here rather
than keeping its own copy.
"""

import re

JUNK_PATTERNS = [
    "cookie", "accept all", "sign up", "sign in", "log in", "subscribe",
    "newsletter", "privacy policy", "terms of service", "all rights reserved",
    "get started free", "start free", "contact sales", "learn more",
]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _strip_images(markdown: str) -> str:
    """Remove markdown image syntax — svg/logo links waste tokens and
    dilute embeddings without carrying any retrievable meaning."""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", markdown)
    return re.sub(r"[ \t]{2,}", " ", md)


def _split_pieces(markdown: str) -> list[str]:
    """Split into heading- and paragraph-delimited pieces. A markdown table
    (no blank line inside it) survives as a single piece."""
    sections = re.split(r"\n(?=#{1,6}\s)", markdown.strip())
    pieces = []
    for section in sections:
        for para in re.split(r"\n\s*\n", section.strip()):
            para = para.strip()
            if para:
                pieces.append(para)
    return pieces


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Split an oversized piece at sentence boundaries; fall back to a raw
    char cut if a single sentence still exceeds max_chars (e.g. a giant table)."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    grouped, current = [], ""
    for s in sentences:
        if not current:
            current = s
        elif len(current) + 1 + len(s) <= max_chars:
            current += " " + s
        else:
            grouped.append(current)
            current = s
    if current:
        grouped.append(current)

    out = []
    for g in grouped:
        while len(g) > max_chars:
            out.append(g[:max_chars])
            g = g[max_chars:]
        if g:
            out.append(g)
    return out


def _is_junk(chunk: str) -> bool:
    c = chunk.strip()
    if len(c) < 120:
        return True
    low = c.lower()
    if len(c) < 300 and any(p in low for p in JUNK_PATTERNS):
        return True
    return False


def _is_junk_piece(piece: str) -> bool:
    """Pattern-only junk check applied before packing, so a short-but-legit
    paragraph (e.g. a single sentence under 120 chars) doesn't get nuked just
    for being short — only actual banner/nav chrome gets dropped here."""
    low = piece.strip().lower()
    return len(piece) < 300 and any(p in low for p in JUNK_PATTERNS)


def chunk_stats(markdown: str, target_chars: int = 1600, max_chars: int = 2400) -> dict:
    """Full result incl. junk-dropped count, for callers that need metrics."""
    pieces = _split_pieces(_strip_images(markdown))

    expanded = []
    for p in pieces:
        if _is_junk_piece(p):
            continue  # drop junk pieces (e.g. cookie banners) before they get packed in with real content
        if len(p) > max_chars:
            expanded.extend(_hard_split(p, max_chars))
        else:
            expanded.append(p)

    chunks, current, current_len = [], [], 0
    for p in expanded:
        if not current:
            current, current_len = [p], len(p)
        elif current_len + 2 + len(p) <= target_chars:
            current.append(p)
            current_len += 2 + len(p)
        else:
            chunks.append("\n\n".join(current))
            current, current_len = [p], len(p)
    if current:
        chunks.append("\n\n".join(current))

    kept = [c for c in chunks if not _is_junk(c)]
    return {"kept": kept, "chunks_total": len(chunks), "junk_dropped": len(chunks) - len(kept)}


def chunk_markdown(markdown: str, target_chars: int = 1600, max_chars: int = 2400) -> list[str]:
    return chunk_stats(markdown, target_chars, max_chars)["kept"]


if __name__ == "__main__":
    sample = """# Pricing

We offer flexible plans for every team size and workload.

## Plans

The Starter plan is free forever and includes core features for small projects getting off the ground.

| Plan | Price | Storage |
|------|-------|---------|
| Free | $0 | 1GB |
| Pro | $29/mo | 100GB |
| Enterprise | Custom | Unlimited |

Accept all cookies to continue browsing this site.

## FAQ

""" + ("This is a long paragraph about billing details and support terms. " * 40) + """

Contact us any time for a custom quote tailored to your organization's needs.
"""

    result = chunk_stats(sample)
    chunks = result["kept"]

    max_chars = 2400
    assert all(len(c) <= max_chars for c in chunks), "a chunk exceeded max_chars"

    table_chunk = next((c for c in chunks if "| Free | $0 | 1GB |" in c), None)
    assert table_chunk is not None, "table not found intact in any chunk"
    assert "| Enterprise | Custom | Unlimited |" in table_chunk, "table got split across chunks"

    assert not any("accept all" in c.lower() for c in chunks), "cookie banner line was not dropped"

    img_md = ("![logo](https://cdn.x.com/a.svg)Pricing![](https://cdn.x.com/b.svg) "
              "starts at $10/mo for the base plan billed annually, and the premium "
              "tier adds unlimited storage, priority support, and advanced analytics "
              "dashboards for larger engineering teams.")
    img_chunks = chunk_markdown(img_md)
    assert not any("svg" in c for c in img_chunks), "image markdown not stripped"
    assert any("$10/mo" in c for c in img_chunks), "real text lost during image strip"

    # order preserved: "Starter plan" text should appear before the long FAQ paragraph
    starter_idx = next(i for i, c in enumerate(chunks) if "Starter plan" in c)
    faq_idx = next(i for i, c in enumerate(chunks) if "billing details" in c)
    assert starter_idx < faq_idx, "chunk order not preserved"

    print(f"✅ chunker self-check passed: {len(chunks)} kept, {result['junk_dropped']} junk dropped")
