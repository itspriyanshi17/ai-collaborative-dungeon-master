from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PlayerAction(Base):
    __tablename__ = "player_actions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action_text: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_status: Mapped[str] = mapped_column(String(50), nullable=False)  # success, failed, rejected
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    room: Mapped["Room"] = relationship(foreign_keys=[room_id])
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
