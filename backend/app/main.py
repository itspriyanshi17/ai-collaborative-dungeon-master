from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from socketio import ASGIApp

from app.api.router import api_router
from app.config import settings
from app.middleware import AuthenticationStateMiddleware
from app.socket.server import sio


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(AuthenticationStateMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


fastapi_app = create_app()
socket_app = ASGIApp(sio, other_asgi_app=fastapi_app)
