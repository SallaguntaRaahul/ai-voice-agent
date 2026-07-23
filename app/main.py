import base64
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from app import groq_client, session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI Voice Agent")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class VoiceResponse(BaseModel):
    transcript: str
    reply_text: str
    audio_base64: str


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/session")
async def new_session():
    return {"session_id": str(uuid.uuid4())}


@app.post("/api/voice", response_model=VoiceResponse)
async def voice_turn(session_id: str = Form(...), audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    try:
        transcript = await groq_client.transcribe_audio(audio_bytes, audio.filename or "audio.webm")
        if not transcript:
            raise HTTPException(status_code=422, detail="Could not transcribe audio")

        session.append_turn(session_id, "user", transcript)
        history = session.get_history(session_id)

        reply_text = await groq_client.chat_reply(history)
        session.append_turn(session_id, "assistant", reply_text)

        audio_reply = await groq_client.synthesize_speech(reply_text)
    except HTTPException:
        raise
    except Exception:
        logger.exception("voice turn failed")
        raise HTTPException(status_code=502, detail="Upstream voice pipeline error")

    return VoiceResponse(
        transcript=transcript,
        reply_text=reply_text,
        audio_base64=base64.b64encode(audio_reply).decode("ascii"),
    )


@app.post("/api/reset")
async def reset_session(session_id: str = Form(...)):
    session.reset(session_id)
    return {"status": "reset"}
