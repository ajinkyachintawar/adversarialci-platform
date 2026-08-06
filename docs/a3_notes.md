# A3 notes

One line per uncomfortable answer, plus the state the week started in. The
"would I show this to a rep?" criterion is not in `ask_log` and cannot be
reconstructed later — write it down the day it happens.

---

## Phase 0 — the company (decided 2026-08-06)

**We sell as MongoDB.** Competitors: Pinecone, Weaviate, Qdrant. This does not
change mid-week; half the questions are comparative, so changing "us" would
invalidate every one of them.

## Corpus baseline at the start of the week

Record this before Phase 3 so Phase 4 can tell a *retrieval* problem apart from
a *thin corpus* problem. A company with fewer chunks abstains more for reasons
that have nothing to do with the comparative-question gap.

| Company | Chunks | First-party |
|---|---|---|
| MongoDB (us) | 445 | 100% |
| Pinecone | 207 | 100% |
| Weaviate | 169 | 100% |
| Qdrant | 397 | 100% |

Qdrant was rebuilt on 2026-08-06: its previous 115 chunks were 96% third-party
and were purged, then re-ingested from 29 vendor seed URLs. It is the *newest*
corpus, not a weaker one — but it is also the only one whose retrieval quality
has never been measured, so treat Qdrant abstentions as unexplained until
proven otherwise.

**Open at time of writing:** Qdrant is 124/397 embedded (Gemini daily cap).
`remove_near_duplicates` has not been run. Both must complete before the week
starts, or Qdrant answers out of 31% of its corpus and the number above is a
lie. Final post-dedup count goes here when it lands:

- [ ] Qdrant final chunk count after embed + dedup: ______

## Infrastructure at the start of the week

Slack `/vs` → `https://adversarialci-api.onrender.com/slack/vs`, the existing
`adversarialci-api` Starter service on branch `earshot`. ngrok is gone. Verified
2026-08-06 15:09 UTC with a cold `/vs weaviate what does their cloud cost` —
ack inside 3s, cited answer, `confidence: evidence`.

Caveat for latency readings: `call_llm` is `@lru_cache`d, so an identical
repeated question returns instantly off cache. Real median is 13–20s.

---

## Uncomfortable answers

Date · what was asked · what was wrong with the answer.

<!-- one line each, added as they happen -->

---

## Question pairs (the most valuable thing this week produces)

When a question abstains and a rephrase answers, log BOTH. That pair is the
direct evidence for whether the gap is retrieval or prompt.

| Date | Asked (abstained) | Rephrased (answered) |
|---|---|---|

---

## Phase 4 — scoring

1. Did you reach for it unprompted? Which days?
2. ≥10 real questions? Count only `confidence in {evidence, none}`.
3. Uncomfortable fewer than 2 in 10? From the notes above, not the log.
4. Of questions that reached `answer()`, what fraction were comparative /
   pronoun-laden, and what fraction of *those* abstained versus explicit-topic?

**Carried in:** `ask_log` already holds 5 `source: "slack"` rows — 4 from A2's
install plus the Phase 2 verification above. They were real questions asked in
earnest, so they count toward the 10. Stated here so the choice is on record.
