import base64
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select

from app import files, groq_client
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.db import get_session, init_db
from app.models import Chat, Message, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Voice Agent", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------- schemas ----------

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChatOut(BaseModel):
    id: int
    title: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class NewMessageRequest(BaseModel):
    content: str


class VoiceResponse(BaseModel):
    transcript: str
    reply_text: str
    audio_base64: str


# ---------- static ----------

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------- auth ----------

@app.post("/api/auth/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, db: Session = Depends(get_session)):
    existing = db.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user={"id": user.id, "email": user.email, "name": user.name})


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user={"id": user.id, "email": user.email, "name": user.name})


@app.get("/api/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "name": current_user.name}


# ---------- chats ----------

def _get_owned_chat(chat_id: int, db: Session, current_user: User) -> Chat:
    chat = db.get(Chat, chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


def _history_for(chat_id: int, db: Session) -> list[dict]:
    rows = db.exec(select(Message).where(Message.chat_id == chat_id).order_by(Message.id)).all()
    return [{"role": m.role, "content": m.content} for m in rows]


def _maybe_set_title(chat: Chat, content: str, db: Session) -> None:
    if chat.title == "New chat":
        chat.title = (content[:48] + "…") if len(content) > 48 else content
        db.add(chat)


@app.get("/api/chats", response_model=list[ChatOut])
async def list_chats(current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    chats = db.exec(
        select(Chat).where(Chat.user_id == current_user.id).order_by(Chat.updated_at.desc())
    ).all()
    return [ChatOut(id=c.id, title=c.title, updated_at=c.updated_at.isoformat()) for c in chats]


@app.post("/api/chats", response_model=ChatOut)
async def create_chat(current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    chat = Chat(user_id=current_user.id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return ChatOut(id=chat.id, title=chat.title, updated_at=chat.updated_at.isoformat())


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    chat = _get_owned_chat(chat_id, db, current_user)
    for m in db.exec(select(Message).where(Message.chat_id == chat.id)).all():
        db.delete(m)
    db.delete(chat)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/chats/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    _get_owned_chat(chat_id, db, current_user)
    rows = db.exec(select(Message).where(Message.chat_id == chat_id).order_by(Message.id)).all()
    return [MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at.isoformat()) for m in rows]


@app.post("/api/chats/{chat_id}/messages/stream")
async def stream_message(
    chat_id: int,
    body: NewMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    chat = _get_owned_chat(chat_id, db, current_user)

    user_msg = Message(chat_id=chat.id, role="user", content=body.content)
    db.add(user_msg)
    _maybe_set_title(chat, body.content, db)
    db.commit()

    history = _history_for(chat.id, db)

    async def event_stream():
        full_text = ""
        try:
            async for delta in groq_client.chat_reply_stream(history, mode="text"):
                full_text += delta
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except Exception:
            logger.exception("stream failed")
            yield f"data: {json.dumps({'error': 'upstream error'})}\n\n"
            return

        assistant_msg = Message(chat_id=chat.id, role="assistant", content=full_text)
        db.add(assistant_msg)
        chat.updated_at = datetime.now(timezone.utc)
        db.add(chat)
        db.commit()

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/chats/{chat_id}/upload")
async def upload_file(
    chat_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    chat = _get_owned_chat(chat_id, db, current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file upload")

    try:
        text = files.extract_text(file.filename, content)
    except Exception:
        logger.exception("file extraction failed")
        raise HTTPException(status_code=422, detail="Could not read that file")

    message_content = f"Uploaded file: {file.filename}\n\n{text}"
    msg = Message(chat_id=chat.id, role="user", content=message_content)
    db.add(msg)
    _maybe_set_title(chat, f"File: {file.filename}", db)
    db.commit()
    db.refresh(msg)

    return {"message_id": msg.id, "filename": file.filename, "preview": text[:500]}


@app.post("/api/chats/{chat_id}/voice", response_model=VoiceResponse)
async def voice_turn(
    chat_id: int,
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    chat = _get_owned_chat(chat_id, db, current_user)
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    try:
        transcript = await groq_client.transcribe_audio(audio_bytes, audio.filename or "audio.webm")
        if not transcript:
            raise HTTPException(status_code=422, detail="Could not transcribe audio")

        user_msg = Message(chat_id=chat.id, role="user", content=transcript)
        db.add(user_msg)
        _maybe_set_title(chat, transcript, db)
        db.commit()

        history = _history_for(chat.id, db)
        reply_text = await groq_client.chat_reply(history, mode="voice")

        assistant_msg = Message(chat_id=chat.id, role="assistant", content=reply_text)
        db.add(assistant_msg)
        db.commit()

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
