from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

PlayerClassType = Literal["Warrior", "Mage", "Archer", "Rogue", "Healer"]


class CharacterCreate(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=100)
    character_class: PlayerClassType = Field(..., alias="class")
    avatar: str = Field(..., min_length=1, max_length=100)

    model_config = ConfigDict(
        populate_by_name=True
    )


class CharacterRead(BaseModel):
    id: UUID
    user_id: UUID
    room_id: UUID
    character_name: str
    character_class: str = Field(..., alias="class")
    avatar: str
    level: int
    experience: int
    health: int
    mana: int
    strength: int
    intelligence: int
    agility: int
    defense: int
    luck: int
    current_health: int
    current_mana: int
    gold: int
    ready_for_game: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
