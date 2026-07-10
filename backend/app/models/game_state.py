from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class GameState(Base):
    __tablename__ = "game_states"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    current_location_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    current_location: Mapped[str] = mapped_column(String(100), nullable=False, default="Dungeon Entrance")
    current_time: Mapped[str] = mapped_column(String(50), nullable=False, default="Day 1 - Morning")
    weather: Mapped[str] = mapped_column(String(50), nullable=False, default="Clear")
    current_quest: Mapped[str] = mapped_column(String(255), nullable=False, default="Explore the Dungeon")

    # JSON representations for active state
    active_npcs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active_monsters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    objects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    inventory: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    world_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Turn stage management
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="player")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    room: Mapped["Room"] = relationship(foreign_keys=[room_id])
