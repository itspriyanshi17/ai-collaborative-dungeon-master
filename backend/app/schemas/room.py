from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import UserRead


class JoinRoomRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")


from app.schemas.character import CharacterRead


class RoomPlayerRead(BaseModel):
    id: UUID
    user: UserRead
    role: str
    is_connected: bool
    is_ready: bool
    joined_at: datetime
    character: CharacterRead | None = None

    model_config = {"from_attributes": True}


class RoomRead(BaseModel):
    id: UUID
    code: str = Field(min_length=6, max_length=6, pattern=r"^[A-Z0-9]{6}$")
    status: str
    host: UserRead
    players: list[RoomPlayerRead]
    current_user_role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class KickPlayerRequest(BaseModel):
    username: str


class TransferHostRequest(BaseModel):
    username: str
