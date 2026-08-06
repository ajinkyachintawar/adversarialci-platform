# EarshotCI — session handoff

> Current state of the world, written 2026-08-06. Read this first in a new
> session, then the plan doc for whatever step you are on. Everything here is
> verifiable from the repo — if it disagrees with the code, the code wins and
> this file is stale.

---

## Where things stand

**A2 is complete and live in Slack.** Phases 0–1 (corpus + `answer()` +
`POST /api/ask`) and A2 (the `/vs` slash command) are done, committed and
measured. **A3 (a week of real use) is the next step, and it is deliberately not
a coding step.**

| Step | State |
|---|---|
| Phase 0 — corpus | done — `docs/EARSHOT_PHASE_0_1.md` |
| Phase 1 — `answer()` + `/api/ask` | done — abstention 95%, answer rate 100% on a 44-query eval |
| **A2 — Slack `/vs`** | **done, live** — `docs/EARSHOT_A2_SLACK.md` |
| **A3 — use it for real** | **NEXT** — `docs/EARSHOT_A3_USE.md` |
| A4 — `eval/ask_eval.py` | blocked on A3 passing |

Commits, newest first: `124a87f` icon · `dfc1039` A2 complete · `ee23927` Phase 5
· `c802787` Phase 4 · `89cc128` Phase 3 · `adb92ee` Phases 1–2.

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
- **`ask_log`** holds 4 real `source: "slack"` rows plus 2 older `source: "api"`.
- **Render is NOT yet deployed for Slack.** The Request URL currently points at
  an ngrok tunnel, which dies with the terminal. A3 Phase 2 moves it to a paid
  Starter instance — that is a prerequisite for A3, not an optimisation.

**Corpus** (`rag_chunks`, 1,671 chunks / 18 companies). Answerable, i.e. measured:
**MongoDB 445, Pinecone 207, Weaviate 169** — and `ANSWERABLE` in `slack/app.py`
lists exactly those three. Qdrant (115) is the intended fourth. Vald has 9 chunks
and would abstain always.

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

This is not theory. The same shape has now been found **eight times** across
Phase 0 and A2 — a falsy return or a degraded path conflating "failed" with
"found nothing": an 87% SEO corpus, Firecrawl 429s, Gemini quota, Groq keys, an
empty corpus∩ANSWERABLE reported as "I don't recognize that competitor", a DB
blip reported as "nobody told me which company we are", a self-check claiming
"offline" while connected, and `busy` charging quota it never spent. **When
reviewing anything here, look for it first.**

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

- **The comparative-question gap** — the A2 finding, and A3's main question.
  Pronoun-laden questions abstain; explicit-topic ones answer. Retrieval, not
  the model (every abstention fired in <2s, before any LLM call). **Do not tune
  `SCORE_FLOOR` off n=2.**
- **PLAN_A's "under 10 seconds" A2 criterion is not achievable** on a free Groq
  key — measured median is 13–20s. The spec is wrong, not the measurement; the
  ack copy promises 20–30s.
- **`call_llm` is `@lru_cache`d** — identical questions return instantly and free.
  Verify no socket growth in the long-lived server process.
- **A redeploy kills in-flight answers**: rep sees "Checking…" then nothing.
  Accepted for A2's ~30s window; do not deploy during a demo.
