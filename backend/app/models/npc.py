from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import ForeignKey, String, JSON, Uuid, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class NPC(Base):
    __tablename__ = "npcs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    race: Mapped[str] = mapped_column(String(50), nullable=False)
    profession: Mapped[str] = mapped_column(String(50), nullable=False)
    personality: Mapped[str] = mapped_column(String(255), nullable=False)
    mood: Mapped[str] = mapped_column(String(50), nullable=False, default="Neutral")
    
    inventory: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    relationships: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # character_name -> relationship points
    
    daily_schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    goals: Mapped[str] = mapped_column(String(255), nullable=False)

    room = relationship("Room")
    location = relationship("Location")
    memories = relationship("NPCMemory", back_populates="npc", cascade="all, delete-orphan")


class NPCMemory(Base):
    __tablename__ = "npc_memories"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    npc_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("npcs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    player_message: Mapped[str] = mapped_column(String(512), nullable=False)
    npc_response: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    npc = relationship("NPC", back_populates="memories")
