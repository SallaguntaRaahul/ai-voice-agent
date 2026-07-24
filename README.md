# AI Voice Agent

A ChatGPT-style assistant you can talk to, type to, hand a file to, or all
three in the same conversation — built end-to-end on one Groq API key, with
its own accounts and persistent chat history.

Live Site: https://ai-voice-agent-d9fu.onrender.com

## Features

- **Voice mode** — click the mic, talk, get a spoken reply. Clicking the mic
  again immediately interrupts the agent's speech (barge-in) so you don't
  have to wait it out.
- **Text mode** — type instead, with real-time streaming responses (tokens
  appear as they're generated) and full markdown/code-block rendering.
- **File upload** — drop in a PDF, DOCX, or text/code file and ask questions
  about it, or ask the agent to revise it; a "download revised file" button
  appears whenever it returns edited content.
- **Accounts + chat history** — email/password signup, chats persist per
  account (SQLite), sidebar to switch between or delete past conversations —
  same shape as ChatGPT's history.
- **Matrix-styled UI** — animated code-rain background, glass panels, subtle
  3D depth.

## Architecture

```
Browser (static HTML/JS, ES modules)
   │  MediaRecorder (mic) · fetch+SSE (streaming text) · file upload
   ▼
FastAPI (app/main.py)
   │  JWT auth (app/auth.py) · SQLite via SQLModel (app/db.py, app/models.py)
   │  User → Chat → Message, all scoped to the authenticated user
   ▼
app/groq_client.py — Groq REST calls, one API key for everything:
   1. audio/transcriptions   (whisper-large-v3-turbo)      → transcript
   2. chat/completions       (llama-3.3-70b-versatile)      → reply text
      (streamed via SSE for text mode, single-shot for voice mode)
   3. audio/speech           (canopylabs/orpheus-v1-english) → reply audio (wav)
   │
app/files.py — extracts text from uploaded PDF/DOCX/plain-text files
```

Two system prompts (`app/groq_client.py`) — a concise, spoken-style one for
voice turns (no markdown, since it gets read aloud by TTS) and a full
ChatGPT-style one for text turns (code blocks, detailed answers, medical
questions answered directly with appropriate care, and the file-revision
convention: full edited content in a fenced ` ```edited-file ` block, which
the frontend detects and turns into a download button).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# then edit .env: set GROQ_API_KEY, and generate a JWT_SECRET with:
python3 -c "import secrets; print(secrets.token_hex(32))"
uvicorn app.main:app --reload
```

Open http://localhost:8000, sign up, and start talking or typing.

## Tests

```bash
pytest
```

## Deploy (Render, free tier)

1. Push this repo to GitHub.
2. In Render, **New → Web Service**, connect the repo. Render picks up
   `render.yaml` automatically (Docker env, free plan, and it auto-generates
   `JWT_SECRET` for you).
3. In the service's **Environment** tab, add `GROQ_API_KEY` with your key —
   left unset in `render.yaml` (`sync: false`) so it's never committed.
4. Deploy. First load after idle will be slow (free tier sleeps).

**Free-tier caveat:** Render's free web services use an ephemeral
filesystem — the SQLite database (accounts, chat history) survives while
the instance stays up, but is wiped on redeploy or a cold restart after the
service sleeps. Fine for a demo; for durable history across restarts, swap
in a free hosted Postgres (e.g. Neon, Supabase) and point `DB_PATH`'s
connection string there instead.

## Notes

- Get a free Groq API key at [console.groq.com](https://console.groq.com/keys).
- The TTS model (`canopylabs/orpheus-v1-english`) requires a one-time terms
  acceptance per Groq account: visit
  https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english
  and accept before `/audio/speech` calls will succeed.
- File uploads are capped at 20k characters of extracted text (truncated
  beyond that) to keep requests within model context limits.
- Not built for large-scale production use — no rate limiting, no email
  verification, no password reset flow. It's a portfolio-scale demo of a
  full voice + chat + file pipeline with real accounts.
