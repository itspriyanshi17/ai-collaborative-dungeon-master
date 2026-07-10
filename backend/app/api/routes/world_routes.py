from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from app.api.deps import get_current_user
from app.database.session import get_session
from app.models.room import Room, RoomPlayer
from app.models.user import User
from app.models.character import Character
from app.models.game_state import GameState
from app.models.player_action import PlayerAction
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory
from app.models.world import Location, Building, WorldObject
from app.schemas.game import GameStateRead
from app.game_engine.game_engine import GameEngine
from app.ai.prompt_builder import DungeonMasterPrompt
from app.ai.gemini_service import GeminiService
from app.services.context_service import ContextService
from app.socket.server import (
    notify_story_generated,
    notify_npc_dialogue,
    notify_atmosphere_changed,
    notify_player_moved
)

router = APIRouter()

# --- Pydantic Schemas ---
class LocationRead(BaseModel):
    id: UUID
    room_id: UUID
    region_id: UUID | None
    biome_id: UUID | None
    name: str
    description: str
    biome: str
    connected_locations: list[str]
    npc_list: list[dict]
    monster_list: list[dict]
    loot_table: dict
    weather: str
    danger_level: int

    model_config = {"from_attributes": True}


class BuildingRead(BaseModel):
    id: UUID
    location_id: UUID
    name: str
    type: str
    description: str
    npc_list: list[dict]
    inventory: dict

    model_config = {"from_attributes": True}


class WorldObjectRead(BaseModel):
    id: UUID
    location_id: UUID
    name: str
    type: str
    status: str
    details: dict

    model_config = {"from_attributes": True}


class LocationDetailRead(LocationRead):
    buildings: list[BuildingRead]
    objects: list[WorldObjectRead]


class TravelRequest(BaseModel):
    code: str
    destination_id: UUID


# --- API Routers ---

@router.get("/world", response_model=list[LocationRead])
async def get_world_locations(
    code: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[LocationRead]:
    room = await session.scalar(
        select(Room).where(Room.code == code.upper())
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")

    # Verify player in room
    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == room.id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(status_code=403, detail="You are not a player in this room.")

    locations = (await session.scalars(
        select(Location).where(Location.room_id == room.id).order_by(Location.danger_level.asc())
    )).all()

    return [LocationRead.model_validate(loc) for loc in locations]


@router.get("/location/{id}", response_model=LocationDetailRead)
async def get_location_details(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LocationDetailRead:
    location = await session.scalar(
        select(Location)
        .where(Location.id == id)
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found.")

    # Verify player is in the corresponding room
    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == location.room_id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(status_code=403, detail="You are not a player in this room.")

    # Explicitly load buildings and objects
    buildings = (await session.scalars(
        select(Building).where(Building.location_id == location.id)
    )).all()
    
    objects = (await session.scalars(
        select(WorldObject).where(WorldObject.location_id == location.id)
    )).all()

    # Build response model
    return LocationDetailRead(
        id=location.id,
        room_id=location.room_id,
        region_id=location.region_id,
        biome_id=location.biome_id,
        name=location.name,
        description=location.description,
        biome=location.biome,
        connected_locations=location.connected_locations,
        npc_list=location.npc_list,
        monster_list=location.monster_list,
        loot_table=location.loot_table,
        weather=location.weather,
        danger_level=location.danger_level,
        buildings=[BuildingRead.model_validate(b) for b in buildings],
        objects=[WorldObjectRead.model_validate(o) for o in objects]
    )


@router.post("/location/travel", response_model=GameStateRead)
async def travel_to_location(
    payload: TravelRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GameStateRead:
    room = await session.scalar(
        select(Room).where(Room.code == payload.code.upper())
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")

    # Verify player in room
    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == room.id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(status_code=403, detail="You are not a player in this room.")

    # Find target location details
    dest_loc = await session.scalar(
        select(Location).where(Location.id == payload.destination_id, Location.room_id == room.id)
    )
    if not dest_loc:
        raise HTTPException(status_code=404, detail="Destination location not found in this room's world map.")

    character = await session.scalar(
        select(Character).where(
            Character.room_id == room.id, Character.user_id == current_user.id
        )
    )
    if not character:
        raise HTTPException(status_code=404, detail="Character not found.")

    # Get current GameState
    game_state = await session.scalar(
        select(GameState).where(GameState.room_id == room.id)
    )
    if not game_state:
        raise HTTPException(status_code=400, detail="Game state has not been initialized.")

    old_loc_name = game_state.current_location

    try:
        # Autoritative movement inside GameEngine (action: "travel to Whispering Forest")
        updated_state = await GameEngine.process_action(
            session=session,
            room_id=room.id,
            user_id=current_user.id,
            action_text=f"travel to {dest_loc.name}"
        )

        # Query player action outcome to verify success
        last_action_obj = await session.scalar(
            select(PlayerAction)
            .where(PlayerAction.room_id == room.id)
            .order_by(PlayerAction.created_at.desc())
        )

        if not last_action_obj:
            raise HTTPException(status_code=500, detail="Failed to retrieve travel action outcome.")

        if last_action_obj.resolved_status == "failed":
            raise HTTPException(
                status_code=400,
                detail=last_action_obj.outcome
            )

        # Trigger Gemini storytelling context narration
        context = await ContextService.build_game_context(session, room.id, current_user.id)
        players_list = context["players_list"]
        recent_events = context["recent_events"]
        story_history = context["story_history"]

        fallback_narration = (
            f"{character.character_name} traveled from {old_loc_name} to {dest_loc.name}. "
            f"Result: {last_action_obj.outcome}."
        )

        prompt = DungeonMasterPrompt(
            current_location=updated_state.current_location,
            current_time=updated_state.current_time,
            weather=updated_state.weather,
            current_quest=updated_state.current_quest,
            active_npcs=updated_state.active_npcs,
            active_monsters=updated_state.active_monsters,
            objects=updated_state.objects,
            inventory=updated_state.inventory,
            world_flags=updated_state.world_flags,
            players=players_list,
            last_action=last_action_obj.action_text,
            action_outcome=last_action_obj.outcome,
            recent_events=recent_events,
            story_history=story_history,
        )

        ai_res = await GeminiService.generate_narration(prompt.render(), fallback_narration)

        # Save AI story
        new_story = StoryHistory(room_id=room.id, entry_text=ai_res.story)
        session.add(new_story)
        await session.commit()

        # Emit Socket.IO synchronization events
        await notify_story_generated(room.code, ai_res.story)
        await notify_npc_dialogue(room.code, ai_res.npc_dialogue)
        await notify_atmosphere_changed(
            room.code, ai_res.atmosphere, ai_res.suggested_music
        )
        
        # Synchronize movement Socket event
        await notify_player_moved(room.code, {
            "from": old_loc_name,
            "to": dest_loc.name,
            "character": character.character_name
        })

        await session.refresh(updated_state)
        return GameStateRead.model_validate(updated_state)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
