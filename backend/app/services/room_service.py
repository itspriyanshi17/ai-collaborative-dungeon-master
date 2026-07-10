import secrets
import string

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.room import Room, RoomPlayer
from app.models.user import User

ROOM_CODE_ALPHABET = "".join(
    character for character in string.ascii_uppercase + string.digits if character not in "0O1I"
)
ROOM_CODE_LENGTH = 6
MAX_ROOM_CODE_ATTEMPTS = 12
MAX_ROOM_PLAYERS = 6


class RoomService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_room(self, creator: User) -> Room:
        for _ in range(MAX_ROOM_CODE_ATTEMPTS):
            room = Room(code=self._generate_room_code(), host_user_id=creator.id)
            room.players.append(RoomPlayer(user_id=creator.id, role="HOST", is_connected=True))
            self.session.add(room)

            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                continue

            return await self.get_room_by_code(room.code, creator)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate a unique room code. Please try again.",
        )

    async def get_room_by_code(self, code: str, current_user: User) -> Room:
        room = await self._get_room(code)

        if self.get_current_user_role(room, current_user) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a player in this room.",
            )

        return room

    async def join_room(self, code: str, current_user: User) -> Room:
        room = await self._get_room(code)

        if room.status != "waiting":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Game has already started.",
            )

        existing_player = self._get_room_player(room, current_user)
        if existing_player is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already joined this room.",
            )

        if len(room.players) >= MAX_ROOM_PLAYERS:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room is full.")

        room.players.append(
            RoomPlayer(user_id=current_user.id, role="PLAYER", is_connected=True, is_ready=False)
        )

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return await self.get_room_by_code(room.code, current_user)

        return await self.get_room_by_code(room.code, current_user)

    async def toggle_ready(self, code: str, current_user: User) -> Room:
        room = await self._get_room(code)
        player = self._get_room_player(room, current_user)
        if player is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found in this room.",
            )
        player.is_ready = not player.is_ready
        if player.character:
            player.character.ready_for_game = player.is_ready
        await self.session.commit()
        return room

    async def start_game(self, code: str, current_user: User) -> Room:
        room = await self._get_room(code)
        if room.host_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the host can start the game.",
            )
        
        # Validation checks
        for p in room.players:
            if not p.character:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Player '{p.user.username}' has not created a character.",
                )
            if p.role != "HOST" and not p.is_ready:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Player '{p.user.username}' is not ready.",
                )

        room.status = "playing"
        from app.game_engine.world_generator import WorldGenerator
        from app.game_engine.game_engine import GameEngine
        
        from app.models.world import WorldObject
        from sqlalchemy import select
        
        start_location, _ = await WorldGenerator.generate_world(self.session, room.id)
        
        # Load objects explicitly using async query to avoid lazy-loading MissingGreenlet
        objects_query = await self.session.scalars(
            select(WorldObject).where(WorldObject.location_id == start_location.id)
        )
        objects_list = objects_query.all()
        
        await GameEngine.initialize_game(
            session=self.session,
            room_id=room.id,
            start_location_id=start_location.id,
            start_location_name=start_location.name,
            start_location_desc=start_location.description,
            start_weather=start_location.weather,
            start_npcs=start_location.npc_list,
            start_monsters=start_location.monster_list,
            start_objects=[
                {
                    "name": o.name,
                    "type": o.type,
                    "status": o.status,
                    "details": o.details
                } for o in objects_list
            ]
        )
        await self.session.commit()
        return room

    async def kick_player(self, code: str, current_user: User, target_username: str) -> tuple[Room, str]:
        room = await self._get_room(code)
        if room.host_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the host can kick players.",
            )
        
        # Find player by username
        target_player = None
        for p in room.players:
            if p.user.username == target_username:
                target_player = p
                break
        
        if target_player is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found in this room.",
            )
            
        if target_player.user_id == room.host_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot kick the host.",
            )
            
        await self.session.delete(target_player)
        await self.session.commit()
        
        # Refresh room
        room = await self._get_room(code)
        return room, target_username

    async def transfer_host(self, code: str, current_user: User, target_username: str) -> Room:
        room = await self._get_room(code)
        if room.host_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the host can transfer hosting rights.",
            )
            
        target_player = None
        host_player = None
        for p in room.players:
            if p.user.username == target_username:
                target_player = p
            if p.user_id == current_user.id:
                host_player = p
                
        if target_player is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target player not found in this room.",
            )
            
        room.host_user_id = target_player.user_id
        if host_player:
            host_player.role = "PLAYER"
        target_player.role = "HOST"
        
        await self.session.commit()
        return room

    async def delete_room(self, code: str, current_user: User) -> None:
        room = await self._get_room(code)
        if room.host_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the host can delete the room.",
            )
        await self.session.delete(room)
        await self.session.commit()

    async def leave_room(self, code: str, current_user: User) -> tuple[Room | None, bool]:
        room = await self._get_room(code)
        player = self._get_room_player(room, current_user)
        if player is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found in this room.",
            )
            
        if room.host_user_id == current_user.id:
            await self.session.delete(room)
            await self.session.commit()
            return None, True
        else:
            await self.session.delete(player)
            await self.session.commit()
            room = await self._get_room(code)
            return room, False

    def get_current_user_role(self, room: Room, current_user: User) -> str | None:
        player = self._get_room_player(room, current_user)
        return player.role if player is not None else None

    def _get_room_player(self, room: Room, current_user: User) -> RoomPlayer | None:
        for player in room.players:
            if player.user_id == current_user.id:
                return player
        return None

    async def _get_room(self, code: str) -> Room:
        normalized_code = code.strip().upper()
        room = await self.session.scalar(
            select(Room)
            .where(Room.code == normalized_code)
            .options(
                selectinload(Room.host),
                selectinload(Room.players).selectinload(RoomPlayer.user),
                selectinload(Room.players).selectinload(RoomPlayer.character),
            )
        )
        if room is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")
        return room

    def _generate_room_code(self) -> str:
        return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))
