import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from google.genai import types

from app.api.deps import get_current_user
from app.database.session import get_session
from app.models.room import Room, RoomPlayer
from app.models.user import User
from app.models.character import Character
from app.models.story_history import StoryHistory
from app.models.npc import NPC, NPCMemory
from app.schemas.npc import NPCRead, NPCDetailRead, NPCTalkRequest, NPCTalkResponse, NPCMemoryRead
from app.ai.gemini_service import GeminiService
from app.socket.server import notify_npc_updated, notify_story_generated

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Structured Pydantic Response Schema for Gemini ---
class AINPCResponse(BaseModel):
    dialogue: str = Field(..., description="The spoken response from the NPC to the player's character.")
    emotion: str = Field(..., description="The new mood or emotion of the NPC (e.g. Happy, Offended, Suspicious, Peaceful, Tired).")
    reaction_type: str = Field(..., description="The reaction classification: friendly, hostile, or neutral.")
    relationship_change: int = Field(..., description="Relationship impact score (-15 to 15 offset points).")
    rumor: str = Field(..., description="A rumor or gossip clue about the dungeon, castle, or mountains, if any, otherwise empty.")


# --- APIs ---

@router.get("/npc", response_model=list[NPCRead])
async def get_room_npcs(
    code: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[NPCRead]:
    room = await session.scalar(
        select(Room).where(Room.code == code.upper())
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")

    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == room.id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(status_code=403, detail="You are not a player in this room.")

    npcs = (await session.scalars(
        select(NPC).where(NPC.room_id == room.id).order_by(NPC.name.asc())
    )).all()

    return [NPCRead.model_validate(n) for n in npcs]


@router.get("/npc/{id}", response_model=NPCDetailRead)
async def get_npc_details(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> NPCDetailRead:
    npc = await session.scalar(
        select(NPC).where(NPC.id == id)
    )
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found.")

    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == npc.room_id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(status_code=403, detail="You are not a player in this room.")

    # Load memories
    memories = (await session.scalars(
        select(NPCMemory)
        .where(NPCMemory.npc_id == npc.id)
        .order_by(NPCMemory.created_at.desc())
        .limit(20)
    )).all()

    return NPCDetailRead(
        id=npc.id,
        room_id=npc.room_id,
        location_id=npc.location_id,
        name=npc.name,
        race=npc.race,
        profession=npc.profession,
        personality=npc.personality,
        mood=npc.mood,
        inventory=npc.inventory,
        relationships=npc.relationships,
        daily_schedule=npc.daily_schedule,
        goals=npc.goals,
        memories=[NPCMemoryRead.model_validate(m) for m in reversed(memories)]
    )


@router.post("/npc/talk", response_model=NPCTalkResponse)
async def talk_to_npc(
    payload: NPCTalkRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> NPCTalkResponse:
    room = await session.scalar(
        select(Room).where(Room.code == payload.code.upper())
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")

    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == room.id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(status_code=403, detail="You are not a player in this room.")

    npc = await session.scalar(
        select(NPC).where(NPC.id == payload.npc_id, NPC.room_id == room.id)
    )
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found.")

    character = await session.scalar(
        select(Character).where(
            Character.room_id == room.id, Character.user_id == current_user.id
        )
    )
    if not character:
        raise HTTPException(status_code=404, detail="Character not found.")

    # Retrieve current relationship points (default to 50)
    char_name = character.character_name
    current_relationship = npc.relationships.get(char_name, 50)

    # Load recent conversation memories (last 10)
    memories = (await session.scalars(
        select(NPCMemory)
        .where(NPCMemory.npc_id == npc.id, NPCMemory.character_name == char_name)
        .order_by(NPCMemory.created_at.desc())
        .limit(10)
    )).all()
    
    memories_list = reversed(memories)
    memories_str = "\n".join(
        f"- {m.character_name}: \"{m.player_message}\" | You: \"{m.npc_response}\""
        for m in memories_list
    ) if memories else "No prior conversations recorded."

    # Build Prompt
    prompt_text = f"""You are the AI roleplaying engine acting as the NPC '{npc.name}' in a fantasy adventure text game.
Your details are:
- Race: {npc.race}
- Profession: {npc.profession}
- Personality: {npc.personality}
- Current Mood: {npc.mood}
- Daily Schedule: {npc.daily_schedule}
- Goals: {npc.goals}
- Inventory items you hold: {npc.inventory}
- Current relationship score with player: {current_relationship} (out of 100, where 0 is hostile enemy, 50 is neutral stranger, 100 is loyal friend)

Here is a memory of your previous dialogue exchanges with {char_name}:
{memories_str}

{char_name} ({character.character_class}, Level {character.level}) says to you:
"{payload.message}"

Respond to {char_name} in character! Make your dialogue fit your profession, goals, personality, and relationship.
Provide a change in relationship based on what they said (e.g. positive change if they are respectful or helpful, negative change if they are insulting or threatening).
Adhere strictly to the AINPCResponse JSON schema. Do not break character.
"""

    # Call Gemini Service
    client = GeminiService.get_client()
    fallback_obj = AINPCResponse(
        dialogue=f"I don't have much to say to you, {char_name}. Move along.",
        emotion="Neutral",
        reaction_type="neutral",
        relationship_change=0,
        rumor=""
    )

    ai_obj = fallback_obj
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt_text,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=AINPCResponse,
                        temperature=0.8,
                    ),
                )
            )
            if response.text:
                ai_obj = AINPCResponse.model_validate_json(response.text)
                break
        except Exception as e:
            logger.warning(f"NPC talk Gemini attempt {attempt} failed: {e}")
            await asyncio.sleep(1)

    # Autoritative Game Engine updates
    new_relationship = max(0, min(100, current_relationship + ai_obj.relationship_change))
    npc.relationships[char_name] = new_relationship
    flag_modified(npc, "relationships")
    
    npc.mood = ai_obj.emotion

    # Persist memories in Supabase
    new_memory = NPCMemory(
        npc_id=npc.id,
        character_name=char_name,
        player_message=payload.message,
        npc_response=ai_obj.dialogue
    )
    session.add(new_memory)

    # Save narration summary to StoryHistory
    story_summary = (
        f"{char_name} talked to NPC {npc.name}. "
        f"Dialogue: \"{ai_obj.dialogue}\". (Mood: {npc.mood}, Relationship: {new_relationship}/100)"
    )
    new_story = StoryHistory(room_id=room.id, entry_text=story_summary)
    session.add(new_story)
    await session.commit()

    # Broadcast updates via Socket.IO
    npc_data = {
        "id": str(npc.id),
        "name": npc.name,
        "mood": npc.mood,
        "relationships": npc.relationships
    }
    await notify_npc_updated(room.code, npc_data)
    await notify_story_generated(room.code, story_summary)

    return NPCTalkResponse(
        dialogue=ai_obj.dialogue,
        emotion=npc.mood,
        relationship_score=new_relationship
    )
