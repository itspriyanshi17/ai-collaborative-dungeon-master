import socketio
from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.database.session import AsyncSessionLocal
from app.models.room import Room
from app.models.user import User
from app.schemas.auth import UserRead
from app.schemas.room import RoomPlayerRead
from app.services.room_service import RoomService
from app.utils.auth import decode_access_token

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.allowed_origins,
    logger=False,
    engineio_logger=False,
)


def room_presence_payload(room: Room) -> dict:
    return jsonable_encoder(
        {
            "code": room.code,
            "status": room.status,
            "host": UserRead.model_validate(room.host),
            "players": [RoomPlayerRead.model_validate(player) for player in room.players],
        }
    )


# Sid to user/room session mapping
sid_to_session: dict[str, dict] = {}


async def notify_player_left(code: str, username: str) -> None:
    await sio.emit("room:player_left", {"code": code, "username": username}, room=code)


async def notify_player_ready(code: str, username: str, is_ready: bool) -> None:
    payload = {"code": code, "username": username, "is_ready": is_ready}
    await sio.emit("room:player_ready", payload, room=code)
    await sio.emit("player_ready", payload, room=code)


async def notify_character_created(code: str, username: str, character_data: dict) -> None:
    payload = jsonable_encoder({"code": code, "username": username, "character": character_data})
    await sio.emit("room:character_created", payload, room=code)
    await sio.emit("character_created", payload, room=code)


async def notify_character_updated(code: str, username: str, character_data: dict) -> None:
    payload = jsonable_encoder({"code": code, "username": username, "character": character_data})
    await sio.emit("room:character_updated", payload, room=code)
    await sio.emit("character_updated", payload, room=code)


async def notify_host_changed(code: str, new_host_username: str) -> None:
    await sio.emit("room:host_changed", {"code": code, "new_host_username": new_host_username}, room=code)


async def notify_player_kicked(code: str, username: str) -> None:
    await sio.emit("room:player_kicked", {"code": code, "username": username}, room=code)


async def notify_room_deleted(code: str) -> None:
    await sio.emit("room:room_deleted", {"code": code}, room=code)


async def notify_game_started(code: str) -> None:
    await sio.emit("room:game_started", {"code": code}, room=code)


async def notify_room_updated(room: Room, joined_username: str | None = None) -> None:
    payload = room_presence_payload(room)
    await sio.emit("room:players_updated", payload, room=room.code)
    if joined_username is not None:
        await sio.emit(
            "room:player_joined",
            {"code": room.code, "username": joined_username},
            room=room.code,
        )


async def notify_world_updated(code: str, world_state: dict) -> None:
    await sio.emit("world_updated", jsonable_encoder({"code": code, "world_state": world_state}), room=code)


async def notify_player_action(code: str, action: dict) -> None:
    await sio.emit("player_action", jsonable_encoder({"code": code, "action": action}), room=code)


async def notify_event_created(code: str, event: dict) -> None:
    await sio.emit("event_created", jsonable_encoder({"code": code, "event": event}), room=code)


async def notify_combat_started(code: str, combat: dict) -> None:
    await sio.emit("combat_started", jsonable_encoder({"code": code, "combat": combat}), room=code)


async def notify_inventory_updated(code: str, inventory: dict) -> None:
    await sio.emit("inventory_updated", jsonable_encoder({"code": code, "inventory": inventory}), room=code)


async def notify_quest_updated(code: str, quest: dict) -> None:
    await sio.emit("quest_updated", jsonable_encoder({"code": code, "quest": quest}), room=code)


async def notify_story_generated(code: str, story: str) -> None:
    await sio.emit("story_generated", {"code": code, "story": story}, room=code)


async def notify_npc_dialogue(code: str, dialogue: list[str]) -> None:
    await sio.emit("npc_dialogue", {"code": code, "npc_dialogue": dialogue}, room=code)


async def notify_atmosphere_changed(code: str, atmosphere: str, suggested_music: str) -> None:
    await sio.emit(
        "atmosphere_changed",
        {"code": code, "atmosphere": atmosphere, "suggested_music": suggested_music},
        room=code,
    )


async def notify_player_moved(code: str, move_data: dict) -> None:
    await sio.emit("player_moved", jsonable_encoder({"code": code, "move_data": move_data}), room=code)


async def notify_npc_updated(code: str, npc_data: dict) -> None:
    await sio.emit("npc_updated", jsonable_encoder({"code": code, "npc": npc_data}), room=code)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    await sio.emit("system:connected", {"sid": sid}, to=sid)


@sio.event
async def room_subscribe(sid: str, data: dict | None = None) -> None:
    token = str((data or {}).get("token") or "")
    code = str((data or {}).get("code") or "")
    user_id = decode_access_token(token)
    if user_id is None:
        await sio.emit("room:error", {"message": "Authentication required."}, to=sid)
        return

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            await sio.emit("room:error", {"message": "Invalid or inactive user."}, to=sid)
            return

        try:
            room = await RoomService(session).get_room_by_code(code, user)
        except Exception:
            await sio.emit("room:error", {"message": "Could not subscribe to this room."}, to=sid)
            return

        # Store sid session info
        sid_to_session[sid] = {"user_id": user.id, "room_code": room.code}

        # Update player connection status in DB
        player = None
        for p in room.players:
            if p.user_id == user.id:
                player = p
                break
        if player and not player.is_connected:
            player.is_connected = True
            await session.commit()
            # Broadcast updated presence
            await notify_room_updated(room)

        await sio.enter_room(sid, room.code)
        await sio.emit("room:players_updated", room_presence_payload(room), to=sid)


@sio.event
async def disconnect(sid: str) -> None:
    session_info = sid_to_session.pop(sid, None)
    if session_info:
        user_id = session_info["user_id"]
        room_code = session_info["room_code"]
        async with AsyncSessionLocal() as session:
            try:
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                from app.models.room import RoomPlayer
                
                room = await session.scalar(
                    select(Room)
                    .where(Room.code == room_code)
                    .options(
                        selectinload(Room.host),
                        selectinload(Room.players).selectinload(RoomPlayer.user),
                    )
                )
                if room:
                    player = None
                    for p in room.players:
                        if p.user_id == user_id:
                            player = p
                            break
                    if player:
                        player.is_connected = False
                        await session.commit()
                        await notify_player_left(room.code, player.user.username)
                        await notify_room_updated(room)
            except Exception:
                pass
    return None
