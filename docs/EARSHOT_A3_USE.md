# A3 — Use it for real (EarshotCI)

> **Handoff note.** Self-contained; assumes no memory of the session that
> produced it. A2's narrative is in `docs/EARSHOT_A2_SLACK.md`, Phase 0–1's in
> `docs/EARSHOT_PHASE_0_1.md`, both in-repo and authoritative. Written
> 2026-08-06, the day A2 went live.

---

## What A3 is, and why it is not a coding step

`docs/PLAN_A.md` step A3 says, in full: **"No new code. This is the step that
decides whether A continues."**

That sentence is the whole design. A2 built a thing that works; A3 asks whether
it is *worth* anything, and the honest answer might be no. PLAN_A's acceptance
is deliberately uncomfortable:

- you reach for it **without reminding yourself to**
- **at least 10 real questions** logged
- you would be uncomfortable showing a rep the answer **fewer than 2 times in 10**

> *"If it fails this, stop. That is a cheap, correct outcome, and far better
> than finding out after building CRM integration."*

The failure mode this step exists to prevent is building A4's eval, then change
alerts, then a CRM integration, on top of a tool nobody reaches for. **The
temptation during A3 will be to fix things instead of using them.** Resist it:
a fix mid-week invalidates the week. Log the problem, keep using it, fix after.

---

## The one thing A2 already told us

A2's first four real questions, from `ask_log`:

```
"weaviate they said they're cheaper"                     -> none      1.17s
"weaviate what does their serverless cloud pricing cost" -> evidence  2.40s
"pinecone how do they price compared to us"              -> none      1.84s
"notacompany what do they charge"          -> unknown_competitor
```

Both **comparative, pronoun-laden** questions abstained. Only the explicit-topic
one answered. That is the product's own pitch failing — the story is *the rep
types what the buyer just said*, and that is exactly the shape that abstains.

Every abstention fired the retrieval gate in **under 2s, before any LLM call**,
so it is retrieval, not the model. And `earshot/answer.py:276` decides abstention
on the **competitor's** chunks *before* `my_company` is retrieved at all — so
configuring "us" cannot rescue a comparative question.

**n=2 is not a measurement.** A3's real job is turning that hunch into a number.
**Do not tune `SCORE_FLOOR` before A3 has data** — that is fitting to two points.

---

## Phase 0 — Pick the company (30 min, do this first)

PLAN_A: *"Pick one real company you can plausibly sell for (devtools/infra —
public docs, public pricing, the corpus you already have)."*

The corpus today (`rag_chunks`, 1,671 chunks over 18 companies):

| Tier | Companies |
|---|---|
| **Measured, answerable** | MongoDB 445, Pinecone 207, Weaviate 169 |
| Ingested, unmeasured | Salesforce 156, Google Cloud 120, Qdrant 115, Cassandra 61, Azure 53, Milvus 47 |
| Too thin to answer | Dynamics 45, AWS 44, Zoho 38, Oracle 37, DigitalOcean 37, DocumentDB 35, HubSpot 34, ChromaDB 19, **Vald 9** |

**Recommendation: sell as MongoDB, against Pinecone / Weaviate / Qdrant.**
Reasons, in order: MongoDB has the deepest corpus (445) so "us" comparisons have
material; Pinecone and Weaviate are the only other measured companies; and
Qdrant at 115 chunks is one ingest away from being the third competitor, in the
same vector-DB conversation. The Slack workspace is already configured this way
(`slack_workspaces`: `{team_id: "T0BND8Z5BCZ", my_company: "MongoDB"}`).

**Deliverable:** write your choice down before ingesting. Changing "us"
mid-week invalidates the week, because half the questions are comparative.

---

## Phase 1 — Ingest the third competitor (1 evening, quota-bound)

Qdrant is at 115 chunks; Pinecone answers well at 207. Top it up, and add a
fourth only if the week shows you reaching for one.

```bash
cd ~/EarshotCI
.venv/bin/python -m ingest.pipeline Qdrant database --dry-run   # inspect first
.venv/bin/python -m ingest.pipeline Qdrant database
```

Seed URLs come from `ingest/seed_urls.json` if the company has an entry — add
vendor-owned URLs there rather than passing them another way. Pricing page comes
from `vendor_registry`.

**Then add it to the answerable list** — this is a *data* change by design:

```python
# slack/app.py
ANSWERABLE = ["MongoDB", "Pinecone", "Weaviate", "Qdrant"]
```

`_known_companies()` intersects that list with what the corpus actually holds, so
a name added here with no chunks behind it simply never appears.

**Watch during ingest:** Gemini free tier is ~1K embeds/day/key and you have 2
keys; Firecrawl 429s were one of the four silent-failure bugs in Phase 0. The
pipeline prints credits used — if a run reports suspiciously few chunks, check
the log before trusting it.

**Accept:** `/vs qdrant what does their cloud cost` returns a cited answer, and
`rag_chunks.distinct("company")` includes Qdrant.

---

## Phase 2 — Make it reachable (before the week starts)

A3 measures whether you *reach for it*. Anything that adds friction to reaching
for it corrupts the measurement.

1. **Deploy to Render on the paid Starter instance.** Risk 1 in
   `docs/EARSHOT_A2_SLACK.md` is resolved by decision but not yet by deploy. On
   the free tier the first `/vs` after any idle period fails Slack's 3s timeout
   during a 30s+ cold start — you would be measuring Render, not the product.
   - set `SLACK_SIGNING_SECRET` and `DEFAULT_MY_COMPANY` in the dashboard
     (both are `sync: false` in `render.yaml` — declared there, valued here)
   - switch the service to Starter
   - repoint the Slack Request URL at `https://<service>.onrender.com/slack/vs`
2. **Stop using ngrok.** A tunnel that dies when you close a laptop lid
   guarantees you stop reaching for the tool.
3. **Put `/vs` where the work is** — the channel you actually sit in, not a test
   channel. `evidence` answers post `in_channel`; everything else is ephemeral.

**Accept:** a `/vs` from your phone, on a day you did not start the server,
returns an answer.

---

## Phase 3 — The week (the actual step)

Use it. Do not read the logs daily — you will start gaming your own questions.

**Rules that keep the week honest:**

- **Ask the question you actually have**, in the words you would actually use.
  If it abstains, that is data, not a bug to work around by rephrasing. Ask the
  rephrased version *too*, so the pair is logged — that pair is the single most
  valuable thing A3 can produce.
- **No code changes** unless the tool is fully broken (500s, silence, no reply).
  Aliases are the one exception (below) because they cost nothing and unblock use.
- **Keep a one-line note per uncomfortable answer.** "Would I show this to a
  rep?" is the acceptance criterion and it is *not* in `ask_log`. A plain text
  file is enough — `docs/a3_notes.md`, one line per incident, date and what was
  wrong.

**The alias exception.** Query the misses and add what you see:

```bash
.venv/bin/python -c "
from db.atlas import get_collection
for d in get_collection('ask_log').find({'source':'slack','confidence':'unknown_competitor'},{'_id':0,'raw_text':1}):
    print(d['raw_text'])"
```

Every row is a name a real person typed that the matcher missed. Add it to
`ALIASES` in `slack/app.py` (keep it tiny — an alias may never resolve to a
company absent from `known`, and `_self_check()` asserts that).

**Mid-week check, once, on day 4:** are there ≥5 rows? If not, the honest read
is that you are not reaching for it, and that is the acceptance criterion
answering itself early. Do not manufacture questions to hit the number.

---

## Phase 4 — Score it (1 hour, end of week)

```bash
.venv/bin/python -c "
from db.atlas import get_collection
from collections import Counter
rows = list(get_collection('ask_log').find({'source':'slack'},{'_id':0}))
print('total:', len(rows))
print(Counter(r.get('confidence') for r in rows).most_common())
answered = [r for r in rows if r.get('confidence') in ('evidence','none')]
print('reached answer():', len(answered))
ev = [r for r in answered if r['confidence']=='evidence']
print('answer rate:', f'{len(ev)}/{len(answered)}' if answered else 'n/a')
for r in rows: print(f\"  {r.get('confidence'):<20} {r.get('raw_text')}\")"
```

Then the three PLAN_A questions, answered in prose in `docs/a3_notes.md`:

1. **Did you reach for it unprompted?** Yes/no, and on which days.
2. **≥10 real questions?** Count only rows where `confidence in
   {"evidence","none"}` — resolution failures were you fighting the matcher, not
   asking the product a question.
3. **Uncomfortable fewer than 2 times in 10?** From your notes, not the log.

**Also produce the number A2 could not:** of the questions that reached
`answer()`, how many were **comparative/pronoun-laden**, and what fraction of
*those* abstained versus explicit-topic ones? That is the A2 finding turned into
evidence, and it is what tells A4 whether the work is retrieval or prompt.

---

## Decision gate

| Outcome | Do this |
|---|---|
| **Passes all three** | Go to A4: `eval/ask_eval.py`, 20 real questions hand-marked for answer accuracy / citation accuracy / abstention rate. Then change alerts. |
| **Fails "reach for it"** | **Stop.** PLAN_A is explicit that this is a correct, cheap outcome. Write down why in `docs/a3_notes.md` — that write-up is worth more than the code. |
| **Passes reach, fails quality** | Do not go to A4. The comparative-question gap is the first suspect; fix retrieval with the week's real questions as the test set, then re-run A3. |

**Failing A3 is a successful A3.** The step exists to buy that information
cheaply.

---

## Do not do these during A3

Change alerts; CRM; the other 14 companies; a `/vs-setup` command; multi-tenancy;
MCP exposure; tuning `SCORE_FLOOR`; rewriting the prompt; a web UI. All of it is
A4-or-later, and every one of them is more attractive than the boring work of
using the tool for a week. That attraction is the trap this step is built around.

---

## Known state, carried in

- **`ask_log` already holds 4 real Slack rows** from A2's install (`team_id
  T0BND8Z5BCZ`) plus 2 older `source: "api"` rows. Filter `source: "slack"`.
  Decide whether the 4 A2 rows count toward the 10; they were real questions, so
  they probably do — just say which way you chose.
- **The daily cap is 40** (`SLACK_DAILY_ANSWER_CAP`), a free-tier dev guard, not
  a product limit. `busy` outcomes are deliberately not charged against it.
- **`call_llm` is `@lru_cache`d**, so re-asking an identical question returns
  instantly and costs no quota. Good for demos, misleading for latency readings —
  A2 saw a 2.4s "answer" that was a cache hit against a real 13–20s median.
- **Groq free tier is ~16–40 LLM-reaching answers/day/model/key** across 3 keys.
  A week of genuine use is quota-limited before it is anything-else-limited.
- **`ingest/embedder.py:_require_key()`** was wired up during A2 (it had been
  dead code). A missing Gemini key now raises a readable error instead of a bare
  `IndexError`. `retrieve()` still lets that propagate rather than converting it
  to `RetrievalUnavailable` — deliberate: a missing key is a deploy mistake that
  should fail loudly, not a transient outage a rep is invited to retry.
