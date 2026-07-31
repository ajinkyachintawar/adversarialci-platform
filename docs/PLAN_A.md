# Plan A — Real-time competitive answers for sales reps

One sentence: **a rep asks what a competitor claimed, and gets back what that
competitor's own pages actually say — quoted, linked, dated — in under 10
seconds, in Slack.**

## The principle everything follows from

**We surface evidence. We do not assert facts.**

The answer is a quote plus a link plus a date, with one line of framing. Not
"Weaviate is cheaper" but "Weaviate's pricing page (18 Jul 2026) lists $45/mo
for Serverless; the free tier is the open-source build."

This is the design decision that makes A both simpler and more trustworthy
than B:

- No dimension taxonomy, no scoring, no winner, no debate, no verdict schema.
- The truth problem stops being ours. A rep who sees the source judges it
  themselves — and forwards the link, which is what they'd do anyway.
- "No evidence found" is a valid, useful answer. B could never say this;
  A must be able to, every time.

## What A is not

Explicitly out of scope. Adding any of these before step A3 is scope creep:

- No web UI, no wizard, no report page
- No CRM integration
- No buyer/analyst modes, no dimensions, no battlecard generation
- No multi-tenant billing, no accounts system
- No new scraping — we use the corpus that already exists

---

## What we reuse vs. build

**Reuse unchanged** (this is why A is not a rewrite):

| Piece | What it gives us |
|---|---|
| `ingest/retrieval.py::retrieve(query, company, k)` | top-k chunks, hard company filter, returns `{text, source_url, source_type, score}` |
| `ingest/pipeline.py` + `store.py` + `embedder.py` | onboarding a new company's corpus |
| `rag_chunks` in Atlas | ~800 chunks across 18 companies, already there |
| `heads/llm.py::call_llm` | Groq calls with key rotation + pre-flight size guard |
| `server.py` | FastAPI app, auth middleware, Atlas connection |

**Build new** (small, and all of it is the actual product):

- `ask/` — one package: answer a question from retrieved evidence
- `/api/ask` — one endpoint
- `slack/` — signature verification, slash command, async reply
- `eval/ask_eval.py` — a golden set of real objections

**Touch nothing in** `court/`, `heads/buyer.py`, `heads/analyst.py`,
`claims/`, `ui/`. B stays frozen where it is.

---

## Step A0 — The answer function

The whole product, minus Slack. Testable from a terminal.

**Build:** `ask/answer.py`

```
answer(question: str, competitor: str, my_company: str | None = None) -> dict
```

Returns:

```json
{
  "answer": "one short paragraph, plain language",
  "citations": [{"quote": "...", "source_url": "...", "captured_at": "..."}],
  "confidence": "evidence" | "none",
  "seconds": 4.2
}
```

How it works:

1. `retrieve(question, competitor, k=6)` — and if `my_company` is given, a
   second `retrieve` for our side, so the answer can compare.
2. One `call_llm` with the chunks, labelled `E1..En` (reuse the E-label
   pattern from `claims/extractor.py` — the model cannot copy hashes).
3. Model returns `{answer, evidence_ids}`. Resolve labels → `source_url` +
   text deterministically, same as `heads/citations.py` does today.
4. **If retrieval returns nothing above a score floor, return
   `confidence: "none"` and do not call the LLM at all.** This is the
   abstention path and it is not optional.

**Acceptance:**
- `.venv/bin/python -m ask.answer "are they cheaper than us" Weaviate Pinecone`
  prints an answer with at least one working URL, in under 10 seconds
- asking about something absent from the corpus returns `confidence: "none"`,
  makes zero LLM calls, and says so in plain words
- every quote in `citations` appears verbatim in a real chunk (assert this in
  the self-check — it is the anti-hallucination guard)

**Self-check:** `.venv/bin/python -m ask.answer` with no args runs asserts on
a stubbed retrieve (no network), covering: normal answer, empty retrieval,
invalid evidence label dropped.

*Roughly one evening.*

---

## Step A1 — The endpoint

**Build:** `POST /api/ask` in `server.py`

```json
{"question": "...", "competitor": "Weaviate", "my_company": "Pinecone"}
```

- Runs `answer()` in a thread (`asyncio.to_thread`, same as existing endpoints)
- Hard timeout of 20s, returns a clean error rather than hanging
- Logs every request to an `ask_log` collection: question, competitor,
  answer, citations, seconds, timestamp

**Why the log matters:** it becomes the golden set in A4. Real questions beat
invented ones, and you cannot get them retroactively.

**Acceptance:** `curl` returns a cited answer in under 10s; a nonsense
competitor returns 400, not a stack trace.

*Half an evening.*

---

## Step A2 — Slack

The only genuinely new engineering. Do it properly — this is the part that
faces the outside world.

**Build:** `slack/app.py`

- Slash command `/vs <competitor> <what they said>`
  Example: `/vs weaviate they said they're cheaper than us`
- **Verify Slack's signature on every request** (`X-Slack-Signature`,
  `X-Slack-Request-Timestamp`, HMAC-SHA256 with the signing secret, reject if
  the timestamp is older than 5 minutes). Non-negotiable — without it anyone
  can POST to your endpoint.
- **Slack requires a response within 3 seconds.** Ack immediately with
  "Looking…", then POST the real answer to `response_url` when ready. Never
  try to answer inside the 3s window.
- Answer posted as a Slack message: one paragraph, then each citation as a
  quoted line with its link and date.
- Workspace config in a `slack_workspaces` collection:
  `{team_id, my_company, competitors[]}` — so `/vs` knows who "us" is.

**Environment:** `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN`. Add both to
`render.yaml` as `sync: false`.

**Acceptance:**
- `/vs weaviate they said they're cheaper` returns a cited answer in your own
  Slack in under 10 seconds
- a request with a bad signature is rejected with 401
- a replayed request older than 5 minutes is rejected
- an unknown competitor replies "I don't have a corpus for that yet" rather
  than failing

*Two evenings, most of it Slack setup rather than code.*

---

## Step A3 — Use it for real

No new code. This is the step that decides whether A continues.

- Pick one real company you can plausibly sell for (devtools/infra — public
  docs, public pricing, the corpus you already have)
- Ingest them + their three main competitors via the existing pipeline
- Use `/vs` for a week on real questions

**Acceptance — be honest about this one:**
- you reach for it without reminding yourself to
- at least 10 real questions logged
- you would be uncomfortable showing a rep the answer fewer than 2 times in 10

If it fails this, stop. That is a cheap, correct outcome, and far better than
finding out after building CRM integration.

---

## Step A4 — Prove it, then extend

Only after A3 passes.

**`eval/ask_eval.py`** — take 20 real questions from `ask_log`, mark each
answer by hand as correct / wrong / should-have-abstained. Report three
numbers:

- **answer accuracy** — is the claim in the answer actually supported?
- **citation accuracy** — does the quoted text really appear at that URL?
- **abstention rate** — how often it correctly said "no evidence"

This is the number that tells you whether there is a business here, and it is
the strongest thing you will have to show an interviewer. It is also the
honest version of the eval B never had: B measured that citations *resolved*,
which was true by construction. This measures whether they are *right*.

**Then, and only then:** weekly change alerts (a competitor's pricing page
moved → post the diff to the channel). It reuses the staleness marking
`ingest/store.py` already does, and it is the feature that makes the Slack app
worth keeping installed between deals.

---

## Guardrails, applied from step A0

These are the things that make it bullet-proof rather than a demo:

1. **Abstain by default.** No evidence above the score floor → say so. Never
   let the model answer from prior knowledge. The prompt says "only from the
   evidence blocks"; the code enforces it by not calling the model at all.
2. **Every quote is verified verbatim** against the chunk it claims to come
   from, in code, before the answer is returned. A quote that does not match
   is dropped.
3. **Every citation carries a date.** Competitive claims go stale; an undated
   claim is a liability.
4. **Hard timeout.** Slow is a failure, not a delay. Better to return "still
   looking, try again" than to hang.
5. **Log everything.** Every question and answer, from day one.
6. **One LLM call per question.** If it ever needs two, question the design.

## Sequencing rule

Do not start a step until the previous one's acceptance criteria pass. Each
step is independently useful, and each one is small enough to finish in an
evening or two — which is the actual constraint.
