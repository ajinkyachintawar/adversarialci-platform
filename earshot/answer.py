"""
Answer
======
Plan A's core call: a rep asks a question about a competitor, gets back a
quote + a link + a date, or an honest "no evidence found" — never a
plausible-sounding invention. Copies the E-label / id_map / one-re-ask pattern
from claims/extractor.py (does not import it — different output schema).

Three gates, in order, each catching what the previous one structurally cannot
(all measured 2026-08-01, see the comments at each):
  1. SCORE_FLOOR   cheap pre-filter, zero LLM calls. Real signal (AUC 0.875)
                   but overlapping tails, so it can never be the guarantee.
  2. relevance     the model declares evidence_answers_question in the SAME
                   call. Catches "real quote, wrong question" — the failure
                   the verbatim gate waved through 20/20 times.
  3. verbatim      every quote must exist in a real chunk, or it is dropped;
                   all citations dropped -> "none". Catches fabrication.

confidence is "evidence" | "none" | "error". "error" exists because a failed
embedder must NEVER be reported as "no evidence" — that lies to the rep about
the corpus and corrupts the only claim this product makes.

Run:  .venv/bin/python -m earshot.answer                              (self-check, offline)
      .venv/bin/python -m earshot.answer "<question>" <Competitor> [<MyCompany>]
"""

import sys
import os
import re
import json
import time
import unicodedata
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest.retrieval import retrieve, RetrievalUnavailable
from ingest.chunker import norm
from heads.llm import call_llm, fits

MODEL = "llama-3.3-70b-versatile"
MAX_OUTPUT_TOKENS = 1024
# llama-3.3-70b-versatile's TOKEN_CAPS is 12K (heads/llm.py); fits() is the
# real gate before any call, this budget just keeps the initial prompt in
# the right ballpark so the fit-shrink loop rarely has to iterate.
EVIDENCE_CHAR_BUDGET = 20_000

# Calibrated 2026-08-01 by earshot/calibrate_floor.py against
# eval/golden_retrieval_v2.json (24 positives) + eval/golden_abstain.json (20).
# Measured: positives 0.860-0.911, negatives 0.789-0.893, AUC 0.875 — real
# signal, but the tails overlap, so a threshold CANNOT be the abstention
# guarantee. 0.85 sits just under the lowest observed positive: zero measured
# false-abstains while still rejecting ~a third of negatives for free.
# ponytail: this is a cheap PRE-FILTER, not the guarantee. The real abstention
# is the citation gate below (unsupported quotes dropped -> confidence "none"),
# which is grounded in evidence rather than cosine distance. A false-abstain
# here is final and unrecoverable, so stay conservative; a false-answer still
# has the citation gate downstream. Recalibrate after any re-ingest, chunker,
# or embedder change — and lower it if real ask_log questions cluster below.
SCORE_FLOOR = 0.85

_SMART_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-",
})


def _fold(s: str) -> str:
    """NFKC + smart-quote/dash folding + chunker's norm() (whitespace/case),
    so a verbatim quote survives scrape-typography noise without allowing
    any real substitution — the anti-hallucination gate must stay strict."""
    return norm(unicodedata.normalize("NFKC", s).translate(_SMART_QUOTES))


def _squash(s: str) -> str:
    """_fold() with ALL whitespace removed, for quote matching. Scraped
    markdown loses spaces ("Starts at$45/mo"), so a model quoting it correctly
    fails a whitespace-sensitive match. Removing whitespace cannot fabricate a
    claim or turn one statement into another — it only tolerates the scrape's
    own typography damage."""
    return "".join(_fold(s).split())


def _captured_at(first_seen_at) -> str:
    if isinstance(first_seen_at, str):
        try:
            first_seen_at = datetime.fromisoformat(first_seen_at)
        except ValueError:
            return ""
    if not first_seen_at:
        return ""
    return first_seen_at.strftime("%-d %b %Y")


class _Citation(BaseModel):
    evidence_id: str
    quote: str


class _AnswerLLM(BaseModel):
    # Measured 2026-08-01: verbatim verification checks a quote is REAL, not
    # that it ANSWERS THE QUESTION. On 20 unanswerable questions the citation
    # gate fired 0 times — the model quoted topically-adjacent text perfectly
    # ("Pinecone's HNSW implementation" answered from Weaviate's corpus, 3
    # verified citations). Relevance is a judgement no substring check can
    # make, so we ask for it explicitly and keep it inside the same call.
    evidence_answers_question: bool = True
    answer: str
    citations: list[_Citation] = Field(default_factory=list)


def _parse(raw: str) -> _AnswerLLM:
    """Code-fence strip, truncated-JSON salvage (mirrors
    claims/extractor.py::_parse_claims), pydantic validation. Raises on
    anything unrecoverable — caller does exactly one re-ask."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # output truncated at max_tokens mid-citation: salvage the complete
        # citations and close off the array + object ourselves
        cut = text.rfind("},")
        if cut == -1:
            raise
        data = json.loads(text[:cut + 1] + "]}")
    return _AnswerLLM(**data)


def _build_prompt(question: str, competitor: str, my_company: str | None,
                   chunks: list[dict], my_chunks: list[dict], per_chunk: int):
    """E-labels continuous across chunks + my_chunks so labels stay globally
    unique. id_map -> the chunk dict already returned by retrieve() (no
    extra DB round-trip for source_url/first_seen_at later)."""
    id_map: dict[str, dict] = {}
    comp_blocks = []
    for i, c in enumerate(chunks):
        label = f"E{i + 1}"
        id_map[label] = c
        comp_blocks.append(f"[{label}] {c['text'][:per_chunk]}")

    my_blocks = []
    for j, c in enumerate(my_chunks):
        label = f"E{len(chunks) + j + 1}"
        id_map[label] = c
        my_blocks.append(f"[{label}] {c['text'][:per_chunk]}")

    parts = [f"QUESTION: {question}",
             f"EVIDENCE ABOUT {competitor}:\n" + "\n\n".join(comp_blocks)]
    if my_blocks:
        parts.append(f"EVIDENCE ABOUT {my_company} (comparison context):\n"
                     + "\n\n".join(my_blocks))

    system = (
        "You report what a competitor's own published pages say, for a sales "
        "rep who will repeat it to a buyer. You surface evidence; you do not "
        "render verdicts. Use ONLY the evidence blocks — never prior knowledge."
    )
    user = "\n\n".join(parts) + f"""

Report what the evidence says about {competitor}, relevant to the question.
Return ONLY a JSON object, no markdown fences, no prose:
{{"evidence_answers_question": true, "answer": "...",
  "citations": [{{"evidence_id": "E1", "quote": "..."}}]}}
- FIRST decide "evidence_answers_question". Set it FALSE unless the evidence
  above directly answers THIS question. Being topically related is NOT enough.
  Set it false if the question asks about a different company than {competitor},
  or asks for something a vendor does not publish (roadmap, revenue, churn,
  headcount, unredacted audit findings, named-customer discounts). Saying "I
  don't have evidence for that" is a correct, valuable answer here — a rep
  repeating a confident guess to a buyer is the worst outcome. When it is
  false, set "answer" to "" and "citations" to [].
- "answer" is ONE short paragraph in plain language, ATTRIBUTED to the source
  — e.g. "{competitor}'s pricing page lists $45/mo for the Flex plan."
- NEVER answer with a bare verdict like "Yes", "No", or "they are cheaper".
  State what the pages say and let the rep judge. If the evidence does not
  settle the question, say exactly that.
- Each quote must be copied EXACTLY from its evidence block — a short
  fragment, not the whole block — and must DIRECTLY SUPPORT the sentence it
  backs. Do not cite a quote that merely mentions the same topic.
- Cite only labels shown above (E1-E{len(chunks) + len(my_chunks)}).
- Return "citations": [] if nothing in the evidence supports an answer."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return messages, id_map


def _fit_prompt(question, competitor, my_company, chunks, my_chunks):
    """Shrinks the prompt until fits() passes. my_chunks (comparison context)
    dropped first — cheaper than losing competitor evidence, the thing the
    question is actually about."""
    chunks, my_chunks = list(chunks), list(my_chunks)
    while True:
        total = max(len(chunks) + len(my_chunks), 1)
        per_chunk = EVIDENCE_CHAR_BUDGET // total
        messages, id_map = _build_prompt(question, competitor, my_company,
                                          chunks, my_chunks, per_chunk)
        if fits(messages, MODEL, MAX_OUTPUT_TOKENS):
            return messages, id_map
        if my_chunks:
            my_chunks = my_chunks[:-1]
        elif len(chunks) > 1:
            chunks = chunks[:-1]
        else:
            return messages, id_map  # nothing left to drop, proceed anyway


def answer(question: str, competitor: str, my_company: str | None = None, k: int = 6) -> dict:
    t0 = time.time()
    # Rep questions are pronoun-laden ("are they cheaper than us") and carry no
    # entity, so the embedding has nothing to anchor on — the company name is
    # only a metadata filter, never part of the embedded text. Measured
    # 2026-08-01: prefixing the name lifts real rep phrasings by +0.045..0.063,
    # moving 4 of 5 from below SCORE_FLOOR (false abstain) to answerable.
    try:
        chunks = retrieve(f"{competitor} {question}", competitor, k=k)
    except RetrievalUnavailable as e:
        # NEVER report an infrastructure failure as "no evidence" — that lies
        # to the rep about the corpus and corrupts the one claim this product
        # makes. Distinct confidence so callers and ask_log can tell them apart.
        return {"answer": "", "citations": [], "confidence": "error",
                "error": str(e), "seconds": round(time.time() - t0, 2)}

    # ABSTENTION GATE — before any LLM call. This is the product's core
    # guarantee, not an error path: weak/no evidence means zero risk taken.
    if not chunks or max(c["score"] for c in chunks) < SCORE_FLOOR:
        return {"answer": "", "citations": [], "confidence": "none",
                "seconds": round(time.time() - t0, 2)}

    try:
        my_chunks = retrieve(f"{my_company} {question}", my_company, k=k) if my_company else []
    except RetrievalUnavailable:
        my_chunks = []  # comparison context only — degrade, don't fail the answer
    messages, id_map = _fit_prompt(question, competitor, my_company, chunks, my_chunks)

    parsed = None
    for is_retry in (False, True):
        raw = call_llm(messages, model=MODEL, max_tokens=MAX_OUTPUT_TOKENS, temperature=0.1)
        try:
            if raw is None:
                raise ValueError("no response")
            parsed = _parse(raw)
        except (json.JSONDecodeError, ValidationError, ValueError):
            parsed = None
        if parsed is not None or is_retry:
            break
        messages = messages + [
            {"role": "assistant", "content": raw or ""},
            {"role": "user", "content":
                "Your previous output was invalid JSON for the schema. Return "
                "only the JSON object, citing only the E-labels shown above."},
        ]

    if parsed is None:
        return {"answer": "", "citations": [], "confidence": "none",
                "seconds": round(time.time() - t0, 2)}

    # RELEVANCE GATE — the model judged its own evidence insufficient. This is
    # the abstention the verbatim gate structurally cannot make (see
    # _AnswerLLM.evidence_answers_question).
    if not parsed.evidence_answers_question:
        return {"answer": "", "citations": [], "confidence": "none",
                "seconds": round(time.time() - t0, 2)}

    # unknown labels dropped silently
    resolved = [(c, id_map[c.evidence_id]) for c in parsed.citations if c.evidence_id in id_map]

    # VERBATIM QUOTE VERIFICATION — the anti-hallucination gate.
    #
    # The gate answers two questions: is this quote REAL, and WHERE is it from.
    # It must not conflate them with "did the model label it correctly."
    # Measured 2026-08-01, both dropped citations on the canonical query were
    # genuine evidence, not hallucination:
    #   1. the corpus contains "Starts at$45/mo" — no space, a Firecrawl
    #      markdown artifact. The model inserted the missing space, so the
    #      quote was human-correct but not byte-identical. norm() collapses
    #      whitespace, it cannot re-insert a space that was never scraped.
    #   2. the model quoted chunk 6 while labelling it E5 — an off-by-one in
    #      its own labelling. The quote was real; only the pointer was wrong.
    # So: match ignoring whitespace entirely, and search EVERY chunk rather
    # than only the cited one, re-attributing to whichever chunk truly holds
    # it. Deleting whitespace cannot turn one claim into a different one, and
    # resolving provenance in code is strictly more trustworthy than believing
    # the model's label. A quote found in NO chunk is still dropped outright.
    verified = []
    for cite, cited_chunk in resolved:
        needle = _squash(cite.quote)
        if not needle:
            continue
        source = None
        if needle in _squash(cited_chunk["text"]):
            source = cited_chunk
        else:
            for cand in id_map.values():  # model mislabelled — find the real source
                if needle in _squash(cand["text"]):
                    source = cand
                    break
        if source is not None:
            verified.append({
                "quote": cite.quote,
                "source_url": source["source_url"],
                "captured_at": _captured_at(source.get("first_seen_at")),
            })

    if resolved and not verified:
        # every citation was a hallucination — an answer with zero verified
        # citations is worse than the abstention this corpus already cleared
        return {"answer": "", "citations": [], "confidence": "none",
                "seconds": round(time.time() - t0, 2)}

    return {
        "answer": parsed.answer,
        "citations": verified,
        "confidence": "evidence",
        "seconds": round(time.time() - t0, 2),
    }


def _self_check():
    global retrieve, call_llm

    sample = {"text": "Weaviate charges $25 per month for the starter tier.",
              "source_url": "https://weaviate.io/pricing",
              "content_hash": "h1", "score": 0.9,
              "first_seen_at": datetime(2026, 7, 18)}

    # 1. normal path -> evidence, one verified citation with url + date
    retrieve = lambda q, c, k=6: [sample]
    call_llm = lambda *a, **kw: json.dumps({
        "answer": "Weaviate's starter tier is $25/month.",
        "citations": [{"evidence_id": "E1", "quote": "$25 per month for the starter tier"}],
    })
    r = answer("how much does it cost", "Weaviate")
    assert r["confidence"] == "evidence"
    assert len(r["citations"]) == 1
    assert r["citations"][0]["source_url"] == "https://weaviate.io/pricing"
    assert r["citations"][0]["captured_at"] == "18 Jul 2026"

    # 2. empty retrieval -> abstention, call_llm never invoked
    retrieve = lambda q, c, k=6: []
    def _boom(*a, **kw):
        raise AssertionError("call_llm must not be invoked on abstention")
    call_llm = _boom
    r = answer("what is your Q3 2027 roadmap", "Weaviate")
    assert r["confidence"] == "none" and r["citations"] == []

    # 3. invented label beside a valid one -> only the valid citation survives
    retrieve = lambda q, c, k=6: [sample]
    call_llm = lambda *a, **kw: json.dumps({
        "answer": "...",
        "citations": [
            {"evidence_id": "E1", "quote": "$25 per month for the starter tier"},
            {"evidence_id": "E99", "quote": "made up quote"},
        ],
    })
    r = answer("how much does it cost", "Weaviate")
    assert r["confidence"] == "evidence" and len(r["citations"]) == 1

    # 4. hallucinated quote dropped, real one kept
    call_llm = lambda *a, **kw: json.dumps({
        "answer": "...",
        "citations": [
            {"evidence_id": "E1", "quote": "$25 per month for the starter tier"},
            {"evidence_id": "E1", "quote": "totally invented pricing detail"},
        ],
    })
    r = answer("how much does it cost", "Weaviate")
    assert len(r["citations"]) == 1
    assert r["citations"][0]["quote"] == "$25 per month for the starter tier"

    # 5. all quotes hallucinated -> downgraded to "none"
    call_llm = lambda *a, **kw: json.dumps({
        "answer": "...",
        "citations": [{"evidence_id": "E1", "quote": "totally invented pricing detail"}],
    })
    r = answer("how much does it cost", "Weaviate")
    assert r["confidence"] == "none" and r["citations"] == []

    print("✅ earshot.answer self-check passed (offline — no network, no LLM call)")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _self_check()
    elif len(sys.argv) >= 3:
        question, competitor = sys.argv[1], sys.argv[2]
        my_company = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(answer(question, competitor, my_company), indent=2))
    else:
        print('Usage: -m earshot.answer | -m earshot.answer "<question>" <Competitor> [<MyCompany>]')
