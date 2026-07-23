from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_new_session_returns_uuid():
    res = client.post("/api/session")
    assert res.status_code == 200
    assert "session_id" in res.json()


def test_voice_turn_round_trip():
    with patch("app.main.groq_client.transcribe_audio", new=AsyncMock(return_value="hello there")), \
         patch("app.main.groq_client.chat_reply", new=AsyncMock(return_value="hi, how can I help?")), \
         patch("app.main.groq_client.synthesize_speech", new=AsyncMock(return_value=b"RIFF....WAVEfmt ")):
        res = client.post(
            "/api/voice",
            data={"session_id": "test-session"},
            files={"audio": ("turn.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "hello there"
    assert body["reply_text"] == "hi, how can I help?"
    assert body["audio_base64"]


def test_voice_turn_rejects_empty_audio():
    res = client.post(
        "/api/voice",
        data={"session_id": "test-session"},
        files={"audio": ("turn.webm", b"", "audio/webm")},
    )
    assert res.status_code == 400


def test_reset_session():
    res = client.post("/api/reset", data={"session_id": "test-session"})
    assert res.status_code == 200
