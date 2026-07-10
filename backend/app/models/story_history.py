from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class StoryHistory(Base):
    __tablename__ = "story_history"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    room: Mapped["Room"] = relationship(foreign_keys=[room_id])
