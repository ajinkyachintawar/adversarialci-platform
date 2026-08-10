# A4 — measure it, then make it understand the question

> Self-contained; assumes no memory of the session that produced it. Written
> 2026-08-10, the day A3 closed. A3's findings are in `docs/a3_notes.md` and are
> authoritative — every number below comes from there, not from intuition.

---

## What A4 is

A3 proved the tool works and measured how badly. **A4 makes it understand the
question.** Two pieces, in this order and not the other:

1. **`eval/ask_eval.py`** — a scored test set built from the 28 real questions
   in `ask_log`. Without it every fix below is guesswork.
2. **A query planner** — an LLM step that reads the question, works out what is
   actually being asked, and decides what to retrieve, instead of embedding the
   rep's raw sentence and hoping.

**The eval comes first.** A2 tuned on a hunch and got the layer wrong; the only
reason anyone knows that is A3's measurement. Build the planner first and you
will have no way to tell whether it helped.

---

## What A3 established (do not re-derive this)

| Fact | Number |
|---|---|
| Answer rate on real questions | **51%** (14 evidence / 27 reached `answer()`) |
| Answer rate on Phase 1's authored eval | 100% on 44 queries |
| Abstentions at the **post-LLM citation gate** | **11 of 13** |
| Abstentions at the retrieval floor | 2 of 13 |

**The A2 hypothesis is dead.** It held that pronoun-laden questions abstain
because of retrieval. Re-scoring every abstention against a quiet index shows 11
of 13 retrieve evidence *above* `SCORE_FLOOR` and are rejected after the LLM.
A2's own two rows score 0.8866 and 0.8654 — both above the floor. It inferred
"before any LLM call" from sub-2s latency, and latency is useless as a proxy
because Groq queueing spans 0.38s–60.57s on identical input.

**Do not tune `SCORE_FLOOR`. It is the wrong layer.**

### The two failure modes

**Mode 1 — floor miss (2 of 13).** No concrete topic noun. "does it get
expensive once you actually grow" scores 0.8327; "how do read and write units
get billed" scores 0.8991. *Rephrasing fixes it.* "Expensive" and "grow" are not
words on a pricing page.

**Mode 2 — citation gate (11 of 13).** Evidence retrieved, nothing citable.
*Rephrasing does not fix it.* Mostly questions needing cross-vendor material,
which no single vendor page can support.

### The question that closed A3

```
weaviate one of our tobe customer is asking is it easy to migrate to MongoDB than weaviate
```

Real, unprompted, in a rep's own words — and it abstained. It is the product's
own pitch failing. Measured:

```
raw question      → Weaviate 0.8508 · MongoDB 0.8543   (barely over floor, gate rejects)
decomposed        → Weaviate 0.8726  "how do you migrate data out of weaviate"
                  → MongoDB  0.8791  "migrate to Atlas from another vector database"
```

**The evidence exists on both sides. The system never asks for it properly.**
That single comparison is A4's whole justification.

---

## Task 1 — `eval/ask_eval.py` (do this first)

**Build it from `ask_log`, not from imagination.** The 51%-vs-100% gap exists
because Phase 1's eval was authored, and authored questions are shaped unlike
the ones people type. Anyone who writes fresh questions here will reproduce that
mistake exactly.

```bash
.venv/bin/python -c "
from db.atlas import connect, get_collection
connect()
for r in get_collection('ask_log').find({'source':'slack','confidence':{'\$in':['evidence','none']}}).sort('created_at',1):
    print(r.get('confidence'), '|', r.get('competitor'), '|', r.get('question') or r['raw_text'])"
```

Hand-mark each row on three axes, kept **separate** — A3 showed they fail
independently:

- **answer accuracy** — is the claim true against the cited page?
- **citation faithfulness** — does the quote *support* the claim? Not "is a
  citation present." The Qdrant answer widened *"a permanently free cluster …
  around one million 768-dimension vectors"* into **"unlimited"** while carrying
  a valid citation. Citation count cannot catch that.
- **abstention correctness** — was "no evidence" true? For 11 of 13 rows it was
  not: the evidence was above the floor.

Also tag each row `single-vendor` or `cross-vendor`. That is the cut A3 found;
"vague vs explicit" is *not* — two deliberate pairs contradicted each other, and
one vague question produced a better answer (4 citations) than its explicit
control (1).

**Baseline to beat: 51% answer rate, 11/13 abstentions wrong.**

**Accept:** re-running the eval on unchanged code reproduces the baseline.

### Measure the gate's non-determinism here

`weaviate what are their support tiers` retrieves **0.9182 every time** and has
returned `none` (2.4s), `none` (2.83s), and `evidence` with 4 citations. Same
question, same corpus, same score. `call_llm` runs at temperature 0.1 — low, not
zero.

Run one question 20 times and report the spread. **For a product whose entire
claim is trustworthy abstention, a coin-flip gate is worse than a strict one:
"no evidence found on their pages" is a factual assertion about the corpus, and
it was false on a third of identical attempts.** This may be the highest-value
fix in A4 and it is invisible without repetition.

---

## Task 2 — the abstention message is a truth bug (cheap, do it early)

Today every abstention says the same thing:

> *"No evidence found on Pinecone's own pages for that question."*

That is **the wrong cause for both modes** and a member of the failure family
this project has now hit eleven times — a failure reported as a fact about the
corpus:

- Mode 1 should say the topic could not be located — try naming it.
- Mode 2 should say a comparison cannot be cited from one vendor's pages alone.

No architecture required. It needs `answer()` to return *which* gate rejected,
and the renderer to say so. `_NOT_ABSTENTION` already exists for exactly this
distinction on tool failures; extend the idea rather than inventing a mechanism.

---

## Task 3 — the query planner ("think like Claude")

The core of A4. Today `answer()` embeds `f"{competitor} {question}"` and
retrieves once. That is why a two-sided question retrieves 0.8508 from one side
and nothing from the other.

**Add a planning step before retrieval** that decides:

1. **What is actually being asked?** "is it easy to migrate to MongoDB than
   weaviate" is a migration-difficulty question, not a sentence to embed.
2. **Is this single-vendor or cross-vendor?** If cross-vendor, it needs both
   corpora and the answer must cite both.
3. **What should be retrieved?** Emit one or more concrete sub-queries, each
   with its company filter. This is what turns 0.8508 into 0.8726 + 0.8791.

Then retrieve per sub-query, and synthesise with citations attributed to the
right vendor.

**Constraints that matter:**

- **Keep the abstention guarantee.** A planner that answers everything destroys
  the only claim the product makes. If a side has no evidence, say which side.
- **It costs an extra LLM call.** Groq free tier is the binding constraint, and
  A3 saw 0.38s–60.57s latency already. Measure before assuming it is affordable.
- **`heads/llm.py` keeps unsynchronised module globals** and `call_llm` is
  `@lru_cache`d. A second call site needs the same lock discipline
  `slack/app.py` already applies.
- **Measure against Task 1's eval after every change.** That is the whole point
  of building it first.

---

## Task 4 — third-party sources with provenance badging (LAST, and only if needed)

The user proposal is: allow non-vendor sources, badge each citation with where
it came from.

**Do not start here, and do not bundle it with Task 3.**

A3 spent two days purging 111 third-party chunks from Qdrant — 96% of its
corpus — because `answer()` does not filter by domain and would have shown a rep
a Medium listicle as evidence. Adding web results back reintroduces exactly that
risk, and badging only mitigates it if the badge survives every path to the rep.

More importantly: **you do not yet know how much web content is actually
needed**, because the system has never queried the corpus competently. Many
mode-2 failures are likely answerable from two first-party corpora once Task 3
lands.

**Gate it on measurement.** After Task 3, re-run the eval and list the questions
still unanswerable. If that list is substantial and genuinely needs third-party
material, build this with the badge enforced end-to-end and the first-party/
third-party distinction visible in the reply. If the list is short, do not build
it at all.

---

## Order, and why

1. **Eval** — otherwise every later change is unmeasurable.
2. **Abstention message** — cheap, truthful, independent of everything else.
3. **Gate non-determinism** — likely the single biggest trust win.
4. **Query planner** — the real work, measured against 1.
5. **Third-party + badging** — only if 4 leaves a real gap.

## Do not do these during A4

Tune `SCORE_FLOOR` (wrong layer, measured). Re-ingest anything. Add companies to
`ANSWERABLE` without purging them first — **the other 14 still carry un-purged
third-party chunks.** Merge `earshot` into `main` before A4 ships something
worth merging. Chase the Slack ephemeral rendering — it is cosmetic and Slack's,
not ours.
