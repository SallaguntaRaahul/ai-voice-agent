from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    password_hash: str
    created_at: datetime = Field(default_factory=_now)


class Chat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = "New chat"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id", index=True)
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=_now)
