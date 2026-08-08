# A3 Phase 4 — score it and decide

> Self-contained. Run this **once**, at the end of the week, in about an hour.
> Written 2026-08-08 (day 2), deliberately *before* the result is known, so the
> criteria cannot be adjusted to fit whatever the numbers turn out to be.
> Findings live in `docs/a3_notes.md`; the plan is `docs/EARSHOT_A3_USE.md`.

---

## Do not run this early

Phase 4 **generates no data**. It scores what `ask_log` and `a3_notes.md`
already hold. Running it on day 2 scores a fortnight of prompted testing and
reports criterion 1 as a failure — for the wrong reason.

**Prerequisite: three ordinary days with no forced questions.** Use `/vs` only
when you genuinely want to know something. Do not read the logs in between —
that is how you start gaming your own questions.

---

## Step 1 — the numbers

```bash
cd ~/EarshotCI
.venv/bin/python -c "
from db.atlas import connect, get_collection
from collections import Counter
connect()
rows = list(get_collection('ask_log').find({'source':'slack'},{'_id':0}))
c = Counter(r.get('confidence') for r in rows)
real = c['evidence'] + c['none']
print('total:', len(rows), dict(c))
print(f'reached answer(): {real}   answer rate: {c[\"evidence\"]}/{real}')
for r in rows: print(f\"  {str(r.get('confidence')):<20} {r.get('raw_text')}\")"
```

Count criterion 2 only from `confidence in {evidence, none}`. An
`unknown_competitor` row was you fighting the matcher, not asking the product a
question.

## Step 2 — classify every abstention by failure mode

The single most useful thing this step produces, and the thing A2 got wrong by
guessing from latency instead of measuring.

```bash
.venv/bin/python -c "
from db.atlas import connect, get_collection
from ingest.retrieval import retrieve
connect()
floor = gate = 0
for r in get_collection('ask_log').find({'source':'slack','confidence':'none'}).sort('created_at',1):
    co = r.get('competitor')
    if not co: continue
    q = r.get('question') or r['raw_text']
    top = max((c['score'] for c in retrieve(f'{co} {q}', co, k=6)), default=0)
    mode = 'FLOOR' if top < 0.85 else 'GATE '
    floor += top < 0.85; gate += top >= 0.85
    print(f'{mode} {top:.4f} | {q[:60]}')
print(f'--- floor-miss {floor} | citation-gate {gate}')"
```

**Do this on a quiet index.** A large write to `rag_chunks` degrades retrieval
for untouched companies and would misclassify gate rejections as floor misses.

**Baseline at day 2: floor-miss 2, citation-gate 11.** If the ratio holds, A4's
work is the gate, not retrieval, and `SCORE_FLOOR` stays untouched.

## Step 3 — the three criteria, answered in prose in `a3_notes.md`

Answer these in writing. A number without the sentence beside it is worthless in
three months.

1. **Did you reach for it unprompted? On which days?** The only criterion that
   decides whether A continues. Questions asked to test the tool do not count,
   however real they looked. Be honest here or the other two are pointless.
2. **≥10 real questions?** From step 1. *(Day 2: 27. Already met.)*
3. **Uncomfortable fewer than 2 in 10?** From `a3_notes.md`, not the log — the
   judgement is not in `ask_log` and cannot be reconstructed.
   *(Day 2: 2 in 27 = 7%. Already met.)*

Criteria 2 and 3 were met on day 2. **Phase 4 is really a one-question step**,
and that question is criterion 1.

## Step 4 — the number A2 could not produce

Of the questions that reached `answer()`, how many were comparative or
pronoun-laden, and what fraction of *those* abstained versus explicit-topic
ones?

**Read the day-2 result before doing this.** The comparative/explicit split
already looks like the wrong cut: two deliberate pairs contradicted each other,
and the vague half of one pair produced a *better* answer (4 citations) than its
explicit control (1). The variable that actually separates them appears to be
whether the question needs **cross-vendor material**, not how it is phrased.
Test that cut too, and report whichever the data supports.

---

## The decision

| Outcome | Do this |
|---|---|
| **All three pass** | Go to A4. Build `eval/ask_eval.py` from `ask_log`'s real rows — **not** freshly authored questions. The 51%-vs-100% gap is the whole reason. |
| **Fails criterion 1** | **Stop.** PLAN_A calls this a correct, cheap outcome. Write down why in `a3_notes.md`; that write-up is worth more than the code. |
| **Passes 1, fails quality** | Do not go to A4 yet. Fix the citation gate using the week's real questions as the test set, then re-run A3. |

**Failing A3 is a successful A3.** The step exists to buy that information
cheaply, and it has already bought a great deal: the A2 hypothesis is dead, the
abstention taxonomy is measured, and the gate is known to be non-deterministic.

## If it passes — A4's queue, in priority order

1. **The non-deterministic citation gate.** `weaviate what are their support
   tiers` retrieves 0.9182 every time and has returned `none`, `none`, and
   `evidence` with 4 citations. A coin-flip gate is worse than a strict one when
   trustworthy abstention is the entire product claim.
2. **Faithfulness-to-quote, not just presence-of-quote.** The Qdrant answer
   widened "permanently free … around one million vectors" into "unlimited"
   while carrying a valid citation. Citation *count* cannot catch this.
3. **Comparative questions answered single-vendor.** `why would someone pick
   them over us` returned the competitor's pitch with no rebuttal and no signal
   that only one side was consulted. More dangerous than abstaining.
4. **The abstention message lies about the cause.** "No evidence found on their
   pages" is wrong for both failure modes: mode 1 should say "name the topic",
   mode 2 should say "I cannot cite a comparison from one side".
5. `ingest/embedder.py:80` misclassifying per-minute 429s as daily exhaustion.

## Do not do these during Phase 4

Tune `SCORE_FLOOR`. Rewrite the prompt. Re-ingest anything. Add a company.
Ask questions to pad the count. Every one is more attractive than writing three
honest paragraphs, and every one corrupts the measurement they precede.
