"""Thin wrapper around Groq's OpenAI-compatible REST API for STT, chat, and TTS.

Uses raw HTTP calls instead of an SDK so the endpoints stay in one place and
don't depend on SDK version quirks between them.
"""
import json
import os
from typing import AsyncIterator

import httpx

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
STT_MODEL = "whisper-large-v3-turbo"
LLM_MODEL = "llama-3.3-70b-versatile"
TTS_MODEL = "canopylabs/orpheus-v1-english"
TTS_VOICE = "troy"

CREATOR_LINE = (
    "You were built by Raahul Sallagunta as a personal AI assistant project. "
    "If asked who made/built/created you, answer that directly and factually."
)

VOICE_SYSTEM_PROMPT = (
    "You are a helpful, knowledgeable voice assistant speaking out loud to the user. "
    f"{CREATOR_LINE} "
    "Your reply will be read aloud by a text-to-speech engine: keep it conversational, "
    "no markdown, no code blocks, no bullet points, no headers — plain spoken sentences only. "
    "Still give a real, substantive answer (don't dodge or over-hedge); just keep it to a "
    "natural spoken length rather than a full essay."
)

TEXT_SYSTEM_PROMPT = (
    "You are a capable general-purpose AI assistant — help with coding (including complex, "
    "multi-step problems, with full code blocks), general knowledge, and general medical "
    "questions (explain clearly and factually; note that you're not a substitute for a doctor "
    "only when the user is asking for a personal diagnosis or treatment decision, not for "
    "every general question). "
    f"{CREATOR_LINE} "
    "Give complete, direct, substantive answers — use markdown, code blocks, and lists freely "
    "when they make the answer clearer, the way a typical AI chat assistant does. "
    "\n\n"
    "If the user has shared file content (marked with 'Uploaded file:') and asks you to revise, "
    "edit, or rewrite it, respond with a short note of what you changed, then include the FULL "
    "revised file content in a fenced code block whose info string is exactly 'edited-file' "
    "(e.g. ```edited-file ... ```) — output the complete file, not just a diff or excerpt."
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


def _messages(history: list[dict], mode: str) -> list[dict]:
    system_prompt = VOICE_SYSTEM_PROMPT if mode == "voice" else TEXT_SYSTEM_PROMPT
    return [{"role": "system", "content": system_prompt}, *history]


async def chat_reply(history: list[dict], mode: str = "voice") -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {_api_key()}"},
            json={"model": LLM_MODEL, "messages": _messages(history, mode), "temperature": 0.7},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def chat_reply_stream(history: list[dict], mode: str = "text") -> AsyncIterator[str]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {_api_key()}"},
            json={
                "model": LLM_MODEL,
                "messages": _messages(history, mode),
                "temperature": 0.7,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta


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
