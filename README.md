# AI Voice Agent

A browser-based voice assistant: hold a conversation out loud with an LLM.
Click the mic, speak, and the agent transcribes you, thinks, and talks back —
entirely on one Groq API key.

## Architecture

```
Browser (static HTML/JS)
   │  MediaRecorder captures mic audio (webm)
   ▼
FastAPI (app/main.py) ── in-memory per-session conversation history
   │
   ▼
app/groq_client.py — three Groq REST calls per turn:
   1. audio/transcriptions   (whisper-large-v3-turbo)  → transcript
   2. chat/completions       (llama-3.3-70b-versatile)  → reply text
   3. audio/speech           (canopylabs/orpheus-v1-english) → reply audio (wav)
   │
   ▼
Browser plays back the reply audio and logs the turn
```

One API key drives the whole pipeline — no separate STT/TTS vendor, no
database, no auth. Session history lives in memory, keyed by a UUID the
browser generates and keeps in `localStorage`; it resets on server restart,
which is fine for a demo-scale deployment that free-tier hosts spin down
between visits anyway.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then paste your Groq API key into .env
uvicorn app.main:app --reload
```

Open http://localhost:8000, click the mic, allow microphone access, talk.

## Tests

```bash
pytest
```

## Deploy (Render, free tier)

1. Push this repo to GitHub.
2. In Render, **New → Web Service**, connect the repo. Render picks up
   `render.yaml` automatically (Docker env, free plan).
3. In the service's **Environment** tab, add `GROQ_API_KEY` with your key —
   `render.yaml` deliberately leaves it unset (`sync: false`) so it's never
   committed or auto-filled.
4. Deploy. First load after idle will be slow (free tier sleeps).

## Notes

- Get a free Groq API key at [console.groq.com](https://console.groq.com/keys).
- The TTS model (`canopylabs/orpheus-v1-english`) requires a one-time terms
  acceptance per Groq account: visit
  https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english
  and accept before the `/audio/speech` calls will succeed.
- Audio format: the browser records `audio/webm`, which Groq's Whisper
  endpoint accepts directly — no client-side transcoding needed.
- Not built for multi-user production use — no auth, no rate limiting, no
  persistent storage. It's a portfolio-scale demo of a full voice pipeline.
