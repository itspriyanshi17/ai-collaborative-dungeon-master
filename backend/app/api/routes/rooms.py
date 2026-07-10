from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database.session import get_session
from app.models.room import Room
from app.models.user import User
from app.schemas.auth import UserRead
from sqlalchemy import select
from app.schemas.room import JoinRoomRequest, RoomPlayerRead, RoomRead, KickPlayerRequest, TransferHostRequest
from app.schemas.character import CharacterCreate, CharacterRead
from app.models.character import Character
from app.services.room_service import RoomService
from app.socket.server import (
    notify_room_updated,
    notify_player_left,
    notify_player_ready,
    notify_host_changed,
    notify_player_kicked,
    notify_room_deleted,
    notify_game_started,
    notify_character_created,
)

router = APIRouter()


def serialize_room(room: Room, current_user: User, service: RoomService) -> RoomRead:
    role = service.get_current_user_role(room, current_user)
    return RoomRead(
        id=room.id,
        code=room.code,
        status=room.status,
        host=UserRead.model_validate(room.host),
        players=[RoomPlayerRead.model_validate(player) for player in room.players],
        current_user_role=role or "PLAYER",
        created_at=room.created_at,
    )


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
async def create_room(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room = await service.create_room(current_user)
    return serialize_room(room, current_user, service)


@router.post("/join", response_model=RoomRead)
async def join_room(
    payload: JoinRoomRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room = await service.join_room(payload.code, current_user)
    await notify_room_updated(room, current_user.username)
    return serialize_room(room, current_user, service)


@router.get("/{code}", response_model=RoomRead)
async def get_room(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room = await service.get_room_by_code(code, current_user)
    return serialize_room(room, current_user, service)


@router.post("/{code}/ready", response_model=RoomRead)
async def toggle_ready(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room = await service.toggle_ready(code, current_user)
    player = service._get_room_player(room, current_user)
    if player:
        await notify_player_ready(room.code, current_user.username, player.is_ready)
    await notify_room_updated(room)
    return serialize_room(room, current_user, service)


@router.post("/{code}/start", response_model=RoomRead)
async def start_game(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room = await service.start_game(code, current_user)
    await notify_game_started(room.code)
    await notify_room_updated(room)
    return serialize_room(room, current_user, service)


@router.post("/{code}/kick", response_model=RoomRead)
async def kick_player(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    payload: KickPlayerRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room, kicked_username = await service.kick_player(code, current_user, payload.username)
    await notify_player_kicked(room.code, kicked_username)
    await notify_room_updated(room)
    return serialize_room(room, current_user, service)


@router.post("/{code}/transfer-host", response_model=RoomRead)
async def transfer_host(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    payload: TransferHostRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RoomRead:
    service = RoomService(session)
    room = await service.transfer_host(code, current_user, payload.username)
    await notify_host_changed(room.code, payload.username)
    await notify_room_updated(room)
    return serialize_room(room, current_user, service)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = RoomService(session)
    await service.delete_room(code, current_user)
    await notify_room_deleted(code)


@router.post("/{code}/leave")
async def leave_room(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = RoomService(session)
    room, is_deleted = await service.leave_room(code, current_user)
    if is_deleted:
        await notify_room_deleted(code)
        return {"message": "Room deleted because host left."}
    else:
        await notify_player_left(code, current_user.username)
        if room:
            await notify_room_updated(room)
        return {"message": "Successfully left room."}


CLASS_STARTING_STATS = {
    "Warrior": {
        "health": 140,
        "mana": 20,
        "strength": 16,
        "intelligence": 6,
        "agility": 8,
        "defense": 12,
        "luck": 8,
        "gold": 100,
    },
    "Mage": {
        "health": 80,
        "mana": 150,
        "strength": 6,
        "intelligence": 18,
        "agility": 9,
        "defense": 6,
        "luck": 10,
        "gold": 120,
    },
    "Archer": {
        "health": 100,
        "mana": 40,
        "strength": 10,
        "intelligence": 10,
        "agility": 16,
        "defense": 8,
        "luck": 14,
        "gold": 90,
    },
    "Rogue": {
        "health": 90,
        "mana": 30,
        "strength": 9,
        "intelligence": 8,
        "agility": 18,
        "defense": 7,
        "luck": 16,
        "gold": 150,
    },
    "Healer": {
        "health": 110,
        "mana": 100,
        "strength": 8,
        "intelligence": 12,
        "agility": 10,
        "defense": 9,
        "luck": 14,
        "gold": 110,
    },
}


@router.post("/{code}/character", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
async def create_character(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    payload: CharacterCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CharacterRead:
    from fastapi import HTTPException
    
    # 1. Resolve room
    service = RoomService(session)
    room = await service.get_room_by_code(code, current_user)
    
    # 2. Check if player has already created a character in this room
    existing_char = await session.scalar(
        select(Character).where(Character.room_id == room.id, Character.user_id == current_user.id)
    )
    if existing_char:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already created a character in this room.",
        )
        
    # 3. Check if name is unique per room
    cleaned_name = payload.character_name.strip()
    if not cleaned_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character name is required.",
        )
    name_taken = await session.scalar(
        select(Character).where(Character.room_id == room.id, Character.character_name == cleaned_name)
    )
    if name_taken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character name is already taken in this room.",
        )
        
    # 4. Resolve stats based on class
    stats = CLASS_STARTING_STATS.get(payload.character_class)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid class: {payload.character_class}",
        )
        
    # 5. Create character
    new_char = Character(
        user_id=current_user.id,
        room_id=room.id,
        character_name=cleaned_name,
        character_class=payload.character_class,
        avatar=payload.avatar,
        health=stats["health"],
        mana=stats["mana"],
        strength=stats["strength"],
        intelligence=stats["intelligence"],
        agility=stats["agility"],
        defense=stats["defense"],
        luck=stats["luck"],
        current_health=stats["health"],
        current_mana=stats["mana"],
        gold=stats["gold"],
        ready_for_game=False,
    )
    session.add(new_char)
    await session.commit()
    await session.refresh(new_char)
    
    # Load character relationship to players in room for the update
    # Trigger refresh on room to serialize character info
    refreshed_room = await service.get_room_by_code(code, current_user)
    
    # 6. Socket broadcasts
    char_data = CharacterRead.model_validate(new_char)
    await notify_character_created(room.code, current_user.username, char_data.model_dump(by_alias=True))
    await notify_room_updated(refreshed_room)
    
    return char_data


@router.get("/{code}/character", response_model=CharacterRead)
async def get_character(
    code: Annotated[str, Path(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CharacterRead:
    from fastapi import HTTPException
    
    service = RoomService(session)
    room = await service.get_room_by_code(code, current_user)
    
    char = await session.scalar(
        select(Character).where(Character.room_id == room.id, Character.user_id == current_user.id)
    )
    if not char:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found in this room.",
        )
        
    return CharacterRead.model_validate(char)
