"""In-memory conversation history, keyed by client-generated session id.

A demo-scale voice agent doesn't need a database for this — history resets
on server restart, which is fine since the free-tier host sleeps and wakes
between visits anyway.
"""
import threading

MAX_TURNS = 20

_lock = threading.Lock()
_sessions: dict[str, list[dict]] = {}


def get_history(session_id: str) -> list[dict]:
    with _lock:
        return list(_sessions.get(session_id, []))


def append_turn(session_id: str, role: str, content: str) -> None:
    with _lock:
        history = _sessions.setdefault(session_id, [])
        history.append({"role": role, "content": content})
        del history[:-MAX_TURNS]


def reset(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
