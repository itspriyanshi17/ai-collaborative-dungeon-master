from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.utils.auth import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, payload: RegisterRequest) -> tuple[User, str, str]:
        normalized_email = payload.email.lower()
        normalized_username = payload.username.strip()
        existing = await self.session.scalar(
            select(User).where(
                or_(User.email == normalized_email, User.username == normalized_username)
            )
        )
        if existing:
            if existing.email == normalized_email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already taken.",
            )

        user = User(
            email=normalized_email,
            username=normalized_username,
            hashed_password=hash_password(payload.password),
        )
        self.session.add(user)
        await self.session.flush()
        access_token, refresh_token = await self._issue_tokens(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, access_token, refresh_token

    async def login(self, payload: LoginRequest) -> tuple[User, str, str]:
        user = await self.session.scalar(select(User).where(User.email == payload.email.lower()))
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been disabled.",
            )

        await self._revoke_user_tokens(user.id)
        access_token, refresh_token = await self._issue_tokens(user)
        await self.session.commit()
        return user, access_token, refresh_token

    async def refresh(self, refresh_token: str | None) -> tuple[User, str, str]:
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_hash = hash_refresh_token(refresh_token)
        stored_token = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        if not stored_token or not stored_token.is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await self.session.get(User, stored_token.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        stored_token.revoked_at = datetime.now(UTC)
        access_token, new_refresh_token = await self._issue_tokens(user)
        await self.session.commit()
        return user, access_token, new_refresh_token

    async def logout(self, refresh_token: str | None, user_id: UUID | None = None) -> None:
        if refresh_token:
            stored_token = await self.session.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
            )
            if stored_token and stored_token.revoked_at is None:
                stored_token.revoked_at = datetime.now(UTC)
        if user_id:
            await self._revoke_user_tokens(user_id)
        await self.session.commit()

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        refresh_token = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=expires_at,
            )
        )
        return create_access_token(user.id), refresh_token

    async def _revoke_user_tokens(self, user_id: UUID) -> None:
        tokens = await self.session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        now = datetime.now(UTC)
        for token in tokens:
            token.revoked_at = now
