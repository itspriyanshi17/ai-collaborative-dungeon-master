from fastapi import APIRouter

from app.api.routes import auth, health, rooms, game, story, world_routes, npc_routes

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(game.router, prefix="/game", tags=["game"])
api_router.include_router(story.router, prefix="/story", tags=["story"])
api_router.include_router(world_routes.router, tags=["world"])
api_router.include_router(npc_routes.router, tags=["npc"])
