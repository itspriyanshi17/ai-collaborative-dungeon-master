from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database.session import get_session
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, MessageResponse, RegisterRequest, UserRead
from app.services.auth_service import AuthService

router = APIRouter()
REFRESH_COOKIE_NAME = "dm_refresh_token"


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth", samesite="lax")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user, access_token, refresh_token = await AuthService(session).register(payload)
    set_refresh_cookie(response, refresh_token)
    return AuthResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user, access_token, refresh_token = await AuthService(session).login(payload)
    set_refresh_cookie(response, refresh_token)
    return AuthResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user, access_token, refresh_token = await AuthService(session).refresh(
        request.cookies.get(REFRESH_COOKIE_NAME)
    )
    set_refresh_cookie(response, refresh_token)
    return AuthResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    await AuthService(session).logout(
        request.cookies.get(REFRESH_COOKIE_NAME),
        getattr(request.state, "user_id", None),
    )
    clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
