from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class GameActionRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")
    action: str = Field(..., min_length=1)


class GameStateRead(BaseModel):
    id: UUID
    room_id: UUID
    current_location: str
    current_time: str
    weather: str
    current_quest: str
    active_npcs: list
    active_monsters: list
    objects: list
    inventory: dict
    world_flags: dict
    turn_index: int
    turn_stage: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlayerActionRead(BaseModel):
    id: UUID
    room_id: UUID
    user_id: UUID
    action_text: str
    resolved_status: str
    outcome: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GameEventRead(BaseModel):
    id: UUID
    room_id: UUID
    event_type: str
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryHistoryRead(BaseModel):
    id: UUID
    room_id: UUID
    entry_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GameHistoryResponse(BaseModel):
    actions: list[PlayerActionRead]
    events: list[GameEventRead]
    story: list[StoryHistoryRead]

    model_config = {"from_attributes": True}
