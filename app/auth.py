import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import User

JWT_ALGORITHM = "HS256"
JWT_EXPIRES_DAYS = 30


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRES_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_session)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.exec(select(User).where(User.id == int(payload["sub"]))).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
