from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class NPCRead(BaseModel):
    id: UUID
    room_id: UUID
    location_id: UUID | None
    name: str
    race: str
    profession: str
    personality: str
    mood: str
    inventory: dict
    relationships: dict
    daily_schedule: str
    goals: str

    model_config = {"from_attributes": True}


class NPCMemoryRead(BaseModel):
    id: UUID
    npc_id: UUID
    character_name: str
    player_message: str
    npc_response: str
    created_at: datetime

    model_config = {"from_attributes": True}


class NPCDetailRead(NPCRead):
    memories: list[NPCMemoryRead]


class NPCTalkRequest(BaseModel):
    code: str
    npc_id: UUID
    message: str


class NPCTalkResponse(BaseModel):
    dialogue: str
    emotion: str
    relationship_score: int
