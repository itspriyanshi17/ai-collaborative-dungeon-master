from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_characters_room_user"),
        UniqueConstraint("room_id", "character_name", name="uq_characters_room_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    character_class: Mapped[str] = mapped_column("class", String(50), nullable=False)
    avatar: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Base Stats
    health: Mapped[int] = mapped_column(Integer, nullable=False)
    mana: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[int] = mapped_column(Integer, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    defense: Mapped[int] = mapped_column(Integer, nullable=False)
    luck: Mapped[int] = mapped_column(Integer, nullable=False)

    # Game Stats
    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    current_mana: Mapped[int] = mapped_column(Integer, nullable=False)
    gold: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status
    ready_for_game: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    room: Mapped["Room"] = relationship(foreign_keys=[room_id])
