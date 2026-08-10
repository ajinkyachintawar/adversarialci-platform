# EarshotCI — session handoff

> Current state of the world. Written 2026-08-06, updated 2026-08-10 (A3 closed).
> Read this first in a new
> session, then the plan doc for whatever step you are on. Everything here is
> verifiable from the repo — if it disagrees with the code, the code wins and
> this file is stale.

---

## Where things stand

**Phases 0–1, A2 and A3 are done. A4 is next: read `docs/EARSHOT_A4.md`.**

A3 was a week of real use, not a coding step, and it earned its keep by
disproving the hypothesis this project carried into it. Nothing was fixed during
it, by design. **The single most important number it produced: the answer rate
on real questions is 51%, against 100% on Phase 1's authored 44-query eval.**
The eval was not wrong — it was shaped unlike the questions people type. That
gap is why A4 builds its eval out of `ask_log` rather than authoring new
questions.

**The one question that closed A3**, asked unprompted two days after the last
prompted batch, in a rep's own words — and it abstained:

> `weaviate one of our tobe customer is asking is it easy to migrate to MongoDB than weaviate`

Raw, it retrieves 0.8508 from Weaviate and 0.8543 from MongoDB and the gate
rejects it. Decomposed into "how do you migrate data out of weaviate" (0.8726)
and "migrate to Atlas from another vector database" (0.8791) it retrieves well
from both. **The evidence exists; the system never asks for it properly.** That
is A4's justification in one line.

| Step | State |
|---|---|
| Phase 0 — corpus | done — `docs/EARSHOT_PHASE_0_1.md` |
| Phase 1 — `answer()` + `/api/ask` | done — abstention 95%, answer rate 100% on a 44-query eval |
| **A2 — Slack `/vs`** | **done, live** — `docs/EARSHOT_A2_SLACK.md` |
| **A3 — use it for real** | **DONE 2026-08-10 — passed, but weakly.** Criterion 2: 28 real questions vs 10 needed. Criterion 3: 2 uncomfortable in 28 (7%) vs <20% allowed. **Criterion 1 passed on n=1** — one genuine unprompted question, two days after the last prompted batch. Thin, and recorded as thin. Findings `docs/a3_notes.md` · plan `docs/EARSHOT_A3_USE.md` · scoring `docs/EARSHOT_A3_PHASE4.md`. |
| **A4 — eval, then query planning** | **NEXT — `docs/EARSHOT_A4.md`.** Start here. |

Commits, newest first: `e6ac04e` A4 written · `189afb6` handoff + Phase 4 runbook
· `7ae3183` all abstentions classified · `10e1c68` two failure modes ·
`c5643b9` A2 hypothesis disproved · `481f9d2` Qdrant rebuilt · `dfc1039` A2 complete.

---

## Environment — the part that surprises people

- **Working dir `~/EarshotCI`, branch `earshot`.** It is a git worktree of
  `~/ad-ci`, pushed to `origin/earshot`.
- **`.venv` is a symlink to `~/ad-ci/.venv`.** Always invoke `.venv/bin/python`,
  never a bare `python`.
- **`config.py` hardcodes `DB_NAME = "war_room"`, so `~/EarshotCI` and `~/ad-ci`
  share ONE live Atlas database.** The worktree isolates code, never data. Any
  write you make in a test is a real write — clean up after yourself.
- **System `python3` has Pillow; the venv does not.** `design/slack_icon.py`
  runs under system `python3`. There is no SVG rasterizer on this machine.
- A `pyenv: code-review-graph: command not found` line prints on every `git
  commit`. It is a stray hook, it is harmless, and the commit succeeds.

## Secrets

Nothing secret is in the repo. `render.yaml` declares env vars as `sync: false`
— names in git, values only in the Render dashboard.

- `SLACK_SIGNING_SECRET` — Slack app → Basic Information → App Credentials.
  **Was rotated once on 2026-08-05** after being pasted into a chat. Never paste
  it into a transcript; it goes browser → terminal directly.
- `DEFAULT_MY_COMPANY` — optional fallback for "us".
- Groq (3 keys), Gemini (2 keys), Firecrawl, Tavily, Mongo URI — all in `.env`.

**No `SLACK_BOT_TOKEN` and no bot token anywhere, by design.** Replies go to the
`response_url` Slack sends with each command. The bot/app tokens Slack's UI
offers during setup are not used and should not be added.

---

## What is live

- **Slack app `EarshotCI`**, workspace `T0BND8Z5BCZ`, command `/vs`, icon set.
- **`slack_workspaces`** holds `{team_id: "T0BND8Z5BCZ", my_company: "MongoDB"}`.
- **`ask_log`** holds 30 real `source: "slack"` rows plus 2 older `source:
  "api"` (2026-08-10). 28 reached `answer()`: 14 `evidence`, 14 `none` — a **~50%
  answer rate on real questions, against 100% on Phase 1's 44-query eval.**
  **This collection is A4's test set. Do not clear it.**
- **Render IS deployed, on the existing `adversarialci-api` Starter service**
  (2026-08-06, A3 Phase 2). ngrok is gone. Request URL is
  `https://adversarialci-api.onrender.com/slack/vs`.

  **There is no separate Earshot service.** The one service now deploys branch
  `earshot` instead of `main`, which works because `earshot` is a strict
  superset — `git log earshot..main` is empty, and `server.py` adds `/api/ask`
  with zero deletions. Two consequences: a redeploy restarts AdversarialCI too,
  and `call_llm`'s `@lru_cache` now applies to AdversarialCI's agent layer.

  **A3 has now passed, so the "revert if A3 says stop" reason is spent — but do
  not merge `earshot` into `main` yet.** Merge when A4 ships something worth
  merging. The branch switch is still one dropdown to revert; a merge is not.

**Corpus.** Answerable, i.e. in `ANSWERABLE` in `slack/app.py`, all 100%
first-party: **MongoDB 445 (us), Qdrant 344, Pinecone 207, Weaviate 169.**

Qdrant was rebuilt 2026-08-06/07. Its previous 115 chunks were **96%
third-party** — `cohorte.co`, Medium, `towardsai` — because it predates Task
0.3b's vendor-domain enforcement and was never in the purge list. 111 were
purged, then 29 Deep Research seed URLs re-ingested: 397 chunks, 53
near-duplicates removed, 344 remaining. **The other 14 companies still carry
un-purged third-party chunks; do not add one to `ANSWERABLE` without purging
and re-ingesting it first.** Vald has 9 chunks and would abstain always.

---

## Running it

```bash
cd ~/EarshotCI
.venv/bin/python -m slack.app          # offline self-check, no network, no DB
.venv/bin/python -m earshot.answer     # offline self-check
.venv/bin/python -m heads.llm          # offline self-check
SLACK_SIGNING_SECRET=<secret> .venv/bin/uvicorn server:app --port 8000
```

All three self-checks must pass offline with the network unplugged. If
`slack.app` ever prints `✅ Atlas connected`, something has reintroduced a DB
call into the pure layer — that exact regression happened once and was caught
because the pass line claimed "offline" while opening a socket.

`PYTHONUNBUFFERED=1` when redirecting server output to a file, or prints are
block-buffered and you will think nothing happened.

---

## Architecture, in one screen

`slack/app.py` is the whole feature, structured **pure functions above, I/O
below**. That split is what keeps `_self_check()` runnable with no Mongo, no
Groq and no network.

- `POST /slack/vs` needs **no middleware change**: `auth_middleware.py` returns
  `call_next()` for any path not starting with `/api/`. Do **not** add it to
  `_PUBLIC_PATHS` — that set is exact-match and only consulted for `/api/`
  paths, so it would be dead config that reads as security.
- Slack demands a reply in 3s; real answers take 13–20s. So: verify signature →
  ack immediately → answer in a background task → post to `response_url`.
- Three separate mechanisms for three separate risks, and **conflating them is
  where this goes wrong**: a `threading.Lock` acquired *inside the worker thread*
  (serialises Groq, because `heads/llm.py` keeps unsynchronised module globals);
  a 90s `wait_for` backstop (bounds how long a *rep* waits — it cancels the
  coroutine, **not** the OS thread, so an orphan keeps burning quota); and a
  daily cap (a free-tier dev guard).
- `_TASKS` holds strong references to background tasks. `asyncio.create_task`
  only holds a weak one, so without it a task can be garbage-collected mid-flight
  and the rep gets silence forever. **`server.py:349` still has that bug** in the
  court path — do not copy that shape.

---

## The rule everything is built around

**Never let a tool failure read as an answer.** `error`, `timeout`, `busy` and
`cap` must never say "no evidence" — a quota outage reported as an abstention
lies to the rep about the corpus and corrupts the only claim this product makes.
`_self_check()` asserts this for all four, and `_NOT_ABSTENTION` is the shared
string that carries it.

This is not theory. The same shape has now been found **eleven times** across
Phase 0, A2 and A3 — a falsy return or a degraded path conflating "failed" with
"found nothing": an 87% SEO corpus, Firecrawl 429s, Gemini quota, Groq keys, an
empty corpus∩ANSWERABLE reported as "I don't recognize that competitor", a DB
blip reported as "nobody told me which company we are", a self-check claiming
"offline" while connected, `busy` charging quota it never spent, and three found
during A3:

- a **per-minute** Gemini 429 reported as "all API keys exhausted for today",
  aborting a resumable run (`ingest/embedder.py:80`)
- an **Atlas index rebuild** during a large write degrading retrieval for
  untouched companies, surfacing as `confidence: none`
- the abstention message itself: **"no evidence found on their pages" is the
  wrong cause** for both measured failure modes — one needs a topic noun, the
  other needs a second corpus

**When reviewing anything here, look for it first.**

---

## Working agreement that produced this code

Every phase was: a Sonnet worker implements from the plan → the orchestrator
audits with an **independent probe the worker never saw** → defects fixed → real
output pasted, never a summary of intent. That split found the majority of the
defects, because a self-check written by the implementer tests the shapes they
already had in mind. Worth keeping.

Two more habits that earned their place:

- **Correct the plan when it is wrong**, in the plan file. A2's Phase 3 accept
  criteria specified an `error` test that did not exercise the error path; the
  doc now says so and gives the right method.
- **No `Co-Authored-By` / "Generated with" trailers** in commits or PRs.

---

## Open items, none blocking

- ~~**The comparative-question gap** — pronoun-laden questions abstain;
  retrieval, not the model.~~ **DEAD. Disproved 2026-08-08 by A3.** Left visible
  because it was wrong in an instructive way.

  All 13 abstentions in `ask_log` were re-scored against a quiet index:
  **11 of 13 retrieve evidence ABOVE `SCORE_FLOOR` and are rejected after the
  LLM, at the citation gate.** Only 2 are genuine floor misses. The A2 rows that
  produced the hypothesis score 0.8866 and 0.8654 — both above the floor. A2
  inferred "before any LLM call" from sub-2s latency; that inference was wrong,
  and latency is a useless proxy for which gate fired, because Groq queueing
  spans 0.38s–60.57s on identical inputs.

  **Do not tune `SCORE_FLOOR`.** Not because n is small — because it is the
  wrong layer entirely.

  Two failure modes, wanting different fixes:
  1. **Floor miss (2/13)** — question has no concrete topic noun ("does it get
     expensive once you actually grow"). Rephrasing fixes it: 0.8327 → 0.8991.
  2. **Citation gate (11/13)** — evidence retrieved, nothing citable.
     Rephrasing does *not* fix it. Mostly questions needing cross-vendor
     material, which no single vendor page can support.

- **THE CITATION GATE IS NON-DETERMINISTIC — start A4 here.**
  `weaviate what are their support tiers` retrieves 0.9182 every time and has
  returned `none` (2.4s), `none` (2.83s), and `evidence` with 4 citations. Same
  question, same corpus, same score. `call_llm` is temperature 0.1 — low, not
  zero. For a product whose only claim is trustworthy abstention, a coin-flip
  gate is worse than a strict one: "no evidence on their pages" is a factual
  assertion about the corpus, and it was false on a third of identical attempts.

- **Real-question answer rate is 51%, against 100% on Phase 1's 44-query eval.**
  The eval was not wrong; it was shaped unlike questions people type. This is
  the argument for building `eval/ask_eval.py` out of `ask_log`'s real rows
  rather than authoring fresh ones.

- **`embed_missing_chunks` misreports transient rate limits as "all API keys
  exhausted for today"** (`ingest/embedder.py:80` treats `"plan and billing"` as
  a daily-quota signal, but per-minute 429s carry it too). It burns a key
  rotation then aborts, skipping the `[5, 15, 45]` backoff. Workaround: run it
  again, it is resumable. The docs' "~1K embeds/day/key" was never the binding
  constraint.

- **A large write to `rag_chunks` degrades retrieval for untouched companies**
  while the shared Atlas index settles, and it surfaces as `confidence: none` —
  an abstention that lies about the corpus. Confirmed twice. **Never ask
  questions during an ingest and count the answers.**
- **PLAN_A's "under 10 seconds" A2 criterion is not achievable** on a free Groq
  key — measured median is 13–20s. The spec is wrong, not the measurement; the
  ack copy promises 20–30s. A3 widened the observed range to **0.38s–60.57s**,
  including 2.95s and 60.57s for the *same* question. Never read a single
  timing as signal.
- **`call_llm` is `@lru_cache`d** — identical questions return instantly and free.
  Verify no socket growth in the long-lived server process.
- **A redeploy kills in-flight answers**: rep sees "Checking…" then nothing.
  Accepted for A2's ~30s window; do not deploy during a demo.
