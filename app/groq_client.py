"""Thin wrapper around Groq's OpenAI-compatible REST API for STT, chat, and TTS.

Uses raw HTTP calls instead of an SDK so the three endpoints (transcription,
chat completions, speech) stay in one place and don't depend on SDK version
quirks between them.
"""
import os

import httpx

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
STT_MODEL = "whisper-large-v3-turbo"
LLM_MODEL = "llama-3.3-70b-versatile"
TTS_MODEL = "canopylabs/orpheus-v1-english"
TTS_VOICE = "troy"

SYSTEM_PROMPT = (
    "You are a helpful, friendly voice assistant. The user is speaking to you "
    "out loud and your reply will be read aloud by a text-to-speech engine, so "
    "keep responses conversational and concise — a few sentences at most, no "
    "markdown, no bullet points, no code blocks."
)


def _api_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return key


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/audio/transcriptions",
            headers={"Authorization": f"Bearer {_api_key()}"},
            data={"model": STT_MODEL},
            files={"file": (filename, audio_bytes, "application/octet-stream")},
        )
        response.raise_for_status()
        return response.json()["text"].strip()


async def chat_reply(history: list[dict]) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {_api_key()}"},
            json={"model": LLM_MODEL, "messages": messages, "temperature": 0.7},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def synthesize_speech(text: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/audio/speech",
            headers={"Authorization": f"Bearer {_api_key()}"},
            json={
                "model": TTS_MODEL,
                "voice": TTS_VOICE,
                "input": text,
                "response_format": "wav",
            },
        )
        response.raise_for_status()
        return response.content
