import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DB_PATH", "/tmp/ai-voice-agent-test.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

init_db()
client = TestClient(app)


def _signup(email="user@example.com", password="password123", name="Test User"):
    res = client.post("/api/auth/signup", json={"email": email, "password": password, "name": name})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_signup_and_login():
    token = _signup(email="signup@example.com")
    assert token

    res = client.post("/api/auth/login", json={"email": "signup@example.com", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password_rejected():
    _signup(email="wrongpw@example.com")
    res = client.post("/api/auth/login", json={"email": "wrongpw@example.com", "password": "nope12345"})
    assert res.status_code == 401


def test_duplicate_signup_rejected():
    _signup(email="dup@example.com")
    res = client.post("/api/auth/signup", json={"email": "dup@example.com", "password": "password123", "name": "Dup"})
    assert res.status_code == 409


def test_chats_require_auth():
    res = client.get("/api/chats")
    assert res.status_code == 401


def test_create_list_and_delete_chat():
    token = _signup(email="chats@example.com")
    headers = _auth_headers(token)

    res = client.post("/api/chats", headers=headers)
    assert res.status_code == 200
    chat_id = res.json()["id"]

    res = client.get("/api/chats", headers=headers)
    assert res.status_code == 200
    assert any(c["id"] == chat_id for c in res.json())

    res = client.delete(f"/api/chats/{chat_id}", headers=headers)
    assert res.status_code == 200


def test_cannot_access_another_users_chat():
    token_a = _signup(email="ownera@example.com")
    token_b = _signup(email="ownerb@example.com")

    chat = client.post("/api/chats", headers=_auth_headers(token_a)).json()
    res = client.get(f"/api/chats/{chat['id']}/messages", headers=_auth_headers(token_b))
    assert res.status_code == 404


def test_streaming_message_persists_history():
    token = _signup(email="stream@example.com")
    headers = _auth_headers(token)
    chat_id = client.post("/api/chats", headers=headers).json()["id"]

    async def fake_stream(history, mode="text"):
        for chunk in ["Hel", "lo!"]:
            yield chunk

    with patch("app.main.groq_client.chat_reply_stream", new=fake_stream):
        res = client.post(
            f"/api/chats/{chat_id}/messages/stream",
            json={"content": "hi there"},
            headers=headers,
        )
    assert res.status_code == 200
    assert "Hel" in res.text and "lo!" in res.text

    messages = client.get(f"/api/chats/{chat_id}/messages", headers=headers).json()
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant"]
    assert messages[1]["content"] == "Hello!"


def test_upload_file_extracts_text():
    token = _signup(email="upload@example.com")
    headers = _auth_headers(token)
    chat_id = client.post("/api/chats", headers=headers).json()["id"]

    res = client.post(
        f"/api/chats/{chat_id}/upload",
        headers=headers,
        files={"file": ("notes.txt", b"hello from a test file", "text/plain")},
    )
    assert res.status_code == 200
    assert "hello from a test file" in res.json()["preview"]


def test_voice_turn_round_trip():
    token = _signup(email="voice@example.com")
    headers = _auth_headers(token)
    chat_id = client.post("/api/chats", headers=headers).json()["id"]

    with patch("app.main.groq_client.transcribe_audio", new=AsyncMock(return_value="hello there")), \
         patch("app.main.groq_client.chat_reply", new=AsyncMock(return_value="hi, how can I help?")), \
         patch("app.main.groq_client.synthesize_speech", new=AsyncMock(return_value=b"RIFF....WAVEfmt ")):
        res = client.post(
            f"/api/chats/{chat_id}/voice",
            headers=headers,
            files={"audio": ("turn.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "hello there"
    assert body["reply_text"] == "hi, how can I help?"
    assert body["audio_base64"]


def test_voice_turn_rejects_empty_audio():
    token = _signup(email="voiceempty@example.com")
    headers = _auth_headers(token)
    chat_id = client.post("/api/chats", headers=headers).json()["id"]

    res = client.post(
        f"/api/chats/{chat_id}/voice",
        headers=headers,
        files={"audio": ("turn.webm", b"", "audio/webm")},
    )
    assert res.status_code == 400
