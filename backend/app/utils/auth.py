from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    password_digest = sha256(password.encode("utf-8")).digest()
    return bcrypt.hashpw(password_digest, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_digest = sha256(password.encode("utf-8")).digest()
    return bcrypt.checkpw(password_digest, password_hash.encode("utf-8"))


def create_access_token(user_id: UUID) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "type": "access", "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

    if payload.get("type") != "access" or not payload.get("sub"):
        return None

    try:
        return UUID(str(payload["sub"]))
    except ValueError:
        return None


def generate_refresh_token() -> str:
    return token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
