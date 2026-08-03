"""
Abstention Eval
===============
The number Plan A lives or dies on: does answer() say "no evidence" when the
corpus cannot support an answer, and does it still answer when it can?

Measured against both sides:
  positives  eval/golden_retrieval_v2.json  -> should return confidence "evidence"
  negatives  eval/golden_abstain.json       -> should return confidence "none"

Also splits WHERE each abstention happened, which matters architecturally:
  "floor"    the SCORE_FLOOR pre-filter caught it, zero LLM calls (free)
  "gate"     the LLM ran and the citation gate rejected the result (1 call)
A single similarity threshold cannot be the guarantee (positives 0.860-0.911 vs
negatives 0.789-0.893, AUC 0.875 — overlapping tails), so the citation gate is
the real mechanism. This eval measures the mechanism, not the threshold.

Run:  .venv/bin/python -m eval.abstention_eval [label]
Out:  eval/results/abstention_eval_<label>_<timestamp>.json
"""

import json
import os
import re
import sys
from datetime import datetime, UTC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heads.llm as llm_mod
from earshot.answer import answer, SCORE_FLOOR


class QuotaBlocked(RuntimeError):
    """Not enough provider budget to produce a trustworthy run — raised BEFORE
    burning any, or the moment a run starts erroring."""


def preflight(model: str) -> None:
    """Refuse to start unless every key can serve a REAL-sized prompt.

    Three runs were wasted on 2026-08-03 by starting blind: the 70B was at
    ~98.7K of its 100,000 daily tokens on all three keys, and each attempt
    ground through dozens of queries discovering that.

    Groq exposes per-MINUTE token headers and per-DAY *request* counts, but no
    per-day token header — the only way to learn TPD state is to be refused, so
    this deliberately spends one real prompt per key to find out cheaply.

    The probe must be a genuine prompt: 'x'*13000 tokenizes to ~2.4K because
    repeated characters compress, so it passes where a real 5.2K prompt 429s.
    """
    import json as _json
    from groq import Groq
    from config import GROQ_API_KEYS
    import earshot.answer as A
    from ingest.retrieval import retrieve

    here = os.path.dirname(os.path.abspath(__file__))
    q = _json.load(open(os.path.join(here, "golden_retrieval_v2.json")))["queries"][0]
    chunks = retrieve(f"{q['company']} {q['query']}", q["company"], k=6)
    messages, _ = A._fit_prompt(q["query"], q["company"], None, chunks, [])
    est = llm_mod.estimate_tokens(messages, A.MAX_OUTPUT_TOKENS)

    print(f"🔎 preflight: {model}, real prompt ≈{est:.0f} tokens, "
          f"{len(GROQ_API_KEYS)} key(s)")
    blocked = []
    for i, k in enumerate(GROQ_API_KEYS):
        try:
            Groq(api_key=k).chat.completions.create(
                model=model, messages=messages, max_tokens=1)
            print(f"   key #{i+1}: OK")
        except Exception as e:
            s = str(e)
            m = re.search(r"\((TPD|TPM)\): Limit (\d+), Used (\d+)", s)
            t = re.search(r"try again in ([\dhms.]+)", s)
            detail = (f"{m.group(1)} {m.group(3)}/{m.group(2)}" if m else s[:80])
            print(f"   key #{i+1}: BLOCKED — {detail}"
                  + (f", retry in {t.group(1)}" if t else ""))
            blocked.append(i + 1)
    if blocked:
        raise QuotaBlocked(
            f"keys {blocked} cannot serve a real prompt on {model}. "
            "Not starting — a partial run is a contaminated run.")
    print("   ✅ all keys can serve a real prompt\n")


# "Surface evidence, never assert facts" is the product, so HOW an answer is
# framed is a correctness property, not a style preference. An answer reading
# "The cheapest Pinecone plan is $20/month" makes EarshotCI the claimant; the
# rep forwards it and we own the claim. "Pinecone's pricing page lists $20/month"
# attributes it, which is the whole promise.
#
# Measured 2026-08-03 on 20 answers both models produced: llama-3.3-70b 60%,
# openai/gpt-oss-120b 95%. The abstention eval scores those two IDENTICALLY —
# this is the axis it cannot see, and it is the axis the prompt explicitly asks
# for. Heuristic and imperfect; treat a small gap as noise and read the answers.
_ATTRIBUTION = re.compile(
    r"\b(pricing page|docs?|documentation|according to|lists|states|says|"
    r"guarantees|enforces|specifies|advertises|per (?:the|its)|page)\b", re.I)


def _is_attributed(answer: str, company: str) -> bool:
    a = answer.strip()
    return bool(a.lower().startswith(company.lower()) or _ATTRIBUTION.search(a))


def _run(entries: list[dict], expect: str) -> list[dict]:
    rows = []
    for e in entries:
        before = llm_mod.call_count
        out = answer(e["query"], e["company"])
        calls = llm_mod.call_count - before
        # ABORT ON FIRST INFRASTRUCTURE ERROR. Today's runs ground through
        # dozens of queries after the provider gave out, burning the budget the
        # retry would need. One error means the run is already contaminated, so
        # every further query is waste.
        if out["confidence"] == "error":
            raise QuotaBlocked(
                f"provider failed on {e['company']!r}: {e['query'][:60]!r} — "
                f"{out.get('error', 'confidence=error')}. Aborting: the run is "
                "already contaminated and continuing only burns quota.")
        correct = out["confidence"] == expect
        rows.append({
            "query": e["query"],
            "company": e["company"],
            "confidence": out["confidence"],
            "expected": expect,
            "correct": correct,
            "llm_calls": calls,
            # an abstention with zero calls came from the floor; with calls,
            # from the citation gate
            "abstained_at": (None if out["confidence"] != "none"
                             else ("floor" if calls == 0 else "gate")),
            "citations": len(out["citations"]),
            "seconds": out["seconds"],
            "answer": out["answer"][:200],
            "attributed": (_is_attributed(out["answer"], e["company"])
                           if out["confidence"] == "evidence" else None),
        })
        mark = "✅" if correct else "❌"
        where = rows[-1]["abstained_at"] or f'{rows[-1]["citations"]} cites'
        print(f"  {mark} [{out['confidence']:<8}] {where:<10} {e['company']:<9} {e['query'][:58]}",
              flush=True)
    return rows


def main(label: str = "baseline") -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    pos = json.load(open(os.path.join(here, "golden_retrieval_v2.json")))["queries"]
    neg = json.load(open(os.path.join(here, "golden_abstain.json")))["queries"]

    from earshot.answer import MODEL
    print(f"\n📊 Abstention eval (SCORE_FLOOR={SCORE_FLOOR}, MODEL={MODEL})")
    if not os.environ.get("SKIP_PREFLIGHT"):
        preflight(MODEL)
    print(f"\n-- NEGATIVES ({len(neg)}) — should abstain --")
    neg_rows = _run(neg, "none")
    print(f"\n-- POSITIVES ({len(pos)}) — should answer --")
    pos_rows = _run(pos, "evidence")

    abstained = sum(r["correct"] for r in neg_rows)
    answered = sum(r["correct"] for r in pos_rows)
    at_floor = sum(r["abstained_at"] == "floor" for r in neg_rows)
    at_gate = sum(r["abstained_at"] == "gate" for r in neg_rows)
    false_abstain = [r for r in pos_rows if not r["correct"]]

    # CONTAMINATION GUARD. Three runs of this eval have now been invalidated by
    # infrastructure failure masquerading as product behaviour (Gemini quota,
    # then Groq key exhaustion — 23 exhausted calls in one run, each of which
    # answer() would once have reported as a confident abstention). Both now
    # surface as confidence "error", so the eval can detect its own
    # contamination rather than waiting for a human to notice the timings look
    # odd. A contaminated run reports NO rates at all: a number that must be
    # remembered as untrustworthy will eventually be trusted.
    answered_rows = [r for r in pos_rows if r["confidence"] == "evidence"]
    attributed = sum(bool(r["attributed"]) for r in answered_rows)
    errors = [r for r in neg_rows + pos_rows if r["confidence"] == "error"]
    contaminated = bool(errors)

    result = {
        "label": label,
        "timestamp": datetime.now(UTC).isoformat(),
        "model": os.environ.get("EARSHOT_MODEL", "llama-3.3-70b-versatile"),
        "fallback_pinned": bool(os.environ.get("GROQ_NO_FALLBACK")),
        "contaminated": contaminated,
        "error_rows": len(errors),
        "score_floor": SCORE_FLOOR,
        "abstention_rate": (None if contaminated else
                            round(abstained / len(neg_rows), 3) if neg_rows else None),
        "answer_rate": (None if contaminated else
                        round(answered / len(pos_rows), 3) if pos_rows else None),
        "attributed_framing": (round(attributed / len(answered_rows), 3)
                               if answered_rows else None),
        "abstained_at_floor": at_floor,
        "abstained_at_gate": at_gate,
        "llm_calls_saved_by_floor": at_floor,
        "mean_seconds": round(sum(r["seconds"] for r in pos_rows + neg_rows)
                              / max(len(pos_rows) + len(neg_rows), 1), 2),
        "negatives": neg_rows,
        "positives": pos_rows,
    }

    print(f"\n{'='*64}")
    if contaminated:
        print(f"  ❌ CONTAMINATED RUN — {len(errors)}/{len(neg_rows)+len(pos_rows)} "
              f"queries hit an infrastructure failure (confidence 'error').")
        print("     Rates deliberately NOT reported: they would measure quota,")
        print("     not product behaviour. Re-run when the provider recovers.")
        for r in errors[:5]:
            print(f"       {r['company']}: {r['query'][:56]}")
        if len(errors) > 5:
            print(f"       ... and {len(errors)-5} more")
    else:
        print(f"  abstention rate  {abstained}/{len(neg_rows)} "
              f"({result['abstention_rate']:.0%})   — correctly said 'no evidence'")
        print(f"  answer rate      {answered}/{len(pos_rows)} "
              f"({result['answer_rate']:.0%})   — answered when it could")
        print(f"  abstained at floor {at_floor} (free) | at citation gate {at_gate} (1 call each)")
        if answered_rows:
            print(f"  attributed framing {attributed}/{len(answered_rows)} "
                  f"({result['attributed_framing']:.0%})   — cited the source rather "
                  f"than asserting")
    print(f"  mean latency     {result['mean_seconds']}s")
    if false_abstain:
        print(f"\n  ⚠️  {len(false_abstain)} false abstentions (corpus HAS the answer):")
        for r in false_abstain:
            print(f"     [{r['abstained_at']}] {r['company']}: {r['query'][:60]}")
    print(f"{'='*64}")

    os.makedirs("eval/results", exist_ok=True)
    path = (f"eval/results/abstention_eval_{label}_"
            f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"saved -> {path}")
    return result


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else "baseline")
    except QuotaBlocked as e:
        # exit 2, distinct from a crash: nothing is wrong with the code, the
        # provider simply cannot support a trustworthy run right now
        print(f"\n🛑 NOT RUN — {e}", file=sys.stderr)
        sys.exit(2)
