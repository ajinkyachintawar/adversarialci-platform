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
| Qdrant | 344 | 100% |

Qdrant was rebuilt on 2026-08-06: its previous 115 chunks were 96% third-party
and were purged, then re-ingested from 29 vendor seed URLs. It is the *newest*
corpus, not a weaker one — but it is also the only one whose retrieval quality
has never been measured, so treat Qdrant abstentions as unexplained until
proven otherwise.

Phase 1 closed 2026-08-07:

- [x] **Qdrant final: 344 chunks, 344 embedded (100%), 31 source URLs, 100%
  first-party.** 397 ingested, 53 near-duplicates removed. Second-largest
  corpus after MongoDB — it is not the thin one. Completed 2026-08-07 07:4x UTC.

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

- 2026-08-06 · `/vs pinecone what does their cloud cost` · answer asserted ~8
  distinct prices ($20/mo, $50 min, $500, $0.33/GB, write and read unit rates)
  behind **one** citation, and the quoted line supported the least load-bearing
  of them. Compare the Weaviate pricing answer: 3 tiers, 3 citations, reads as
  trustworthy. "Citations vs claims" is a concrete thing for A4 to score.

- 2026-08-07 · `/vs qdrant what does their cloud cost` · **said the free tier is
  "unlimited for testing". It is not.** The corpus contains zero occurrences of
  "unlimited"; `qdrant.tech/cloud/` says *"a permanently free cluster … around
  one million 768-dimension vectors"*. **Permanently free** (unbounded in time)
  was compressed into **unlimited** (unbounded in capacity) — a different and
  false claim, on the single most quotable line in the answer. A rep repeating
  it gets corrected by the buyer.

  Note what did NOT go wrong: the same answer's "no surprise overage fees" and
  "changes need authorization" are near-verbatim from that page's FAQ, and a
  citation for the free tier *was* present. **Citation count would not have
  caught this.** The failure is a bounded claim widened into an unbounded one
  while staying inside the cited source — which needs A4 to score
  faithfulness-to-quote, not just presence-of-quote.

## Setup-day observations (before the week — not counted as week data)

- **Same question, opposite outcomes, one minute apart.** `pinecone what does
  their cloud cost` returned `none` (2.84s) then `evidence` (4.35s). Retrieval
  is deterministic when checked directly — 0.8848 every run with the company
  prefix `answer()` adds, comfortably over `SCORE_FLOOR` 0.85 — so it should
  never have abstained.

  **Hypothesis, not a finding (n=1):** the abstention landed minutes after the
  Qdrant ingest wrote 397 chunks + 124 embeddings into `rag_chunks`, and cleared
  once that settled. A shared-index rebuild degrading retrieval for an untouched
  company would present exactly this way — and `RetrievalUnavailable` cannot
  catch it, because `embed_query` succeeds and Atlas returns results, just
  weaker ones. That would make it the ninth instance of the house bug: an
  infrastructure condition reported to the rep as "no evidence".

  **Consequence for the week:** finish Qdrant embed + dedup BEFORE Phase 3
  starts. Questions asked during a large write may abstain for reasons that have
  nothing to do with the corpus, and would pollute the only measurement A3 makes.

- **`weaviate what are their support tiers` → `none` (2.4s).** Weaviate's seed
  URLs include `/sla` and `/support-plans`, so the topic IS in the corpus.
  Asked during the same write window.

  **RESOLVED 2026-08-07, and it confirms the hypothesis above.** Re-scored on a
  quiet index: **0.9182**, far above the 0.85 floor. Pinecone's same query is
  unchanged at 0.8848, so the effect is transient, not a shift. That is n=2 for
  "a large write to `rag_chunks` degrades retrieval for untouched companies and
  surfaces as an abstention." Not a retrieval miss — corpus and gate are both
  fine. **Never ask questions during an ingest and count the answers.**

- **`embed_missing_chunks` reports transient rate limits as "all API keys
  exhausted for today."** [embedder.py:80](../ingest/embedder.py:80) classifies a
  429 as daily-quota if the body contains `"PerDay"` **or** `"plan and billing"`
  — but Gemini's per-minute 429s also carry "plan and billing". So an RPM limit
  burns a key rotation, then aborts the whole run, skipping the
  `backoffs = [5, 15, 45]` path that would have waited 15s and continued.

  Proof: the run that declared both keys spent was followed immediately by a
  direct probe returning **HTTP 200 on both keys**, and a re-run that did
  `140/140 embedded, 0 failed`. The "~1K embeds/day/key" figure in the plan docs
  was never the binding constraint — this was.

  **Not fixed.** Ingest is done, the workaround is "run it again" (it is
  resumable), and changing embedding classification the day the week starts is
  the trap this step is built around. Same failure family as the other nine:
  a transient condition reported as a terminal one. Fix in A4.

- **`evidence` answers render ephemeral despite `response_type: in_channel`.**
  Code is correct ([slack/app.py:444](../slack/app.py:444)); Render logs show the
  `response_url` POST accepted with no delivery warning, and inviting the app to
  the channel did not change it. Slack-side rendering of delayed slash-command
  responses. Cosmetic — no acceptance criterion depends on it. Not chased.

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
