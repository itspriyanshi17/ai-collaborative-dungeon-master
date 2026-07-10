from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(6), unique=True, index=True, nullable=False)
    host_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    host: Mapped["User"] = relationship(foreign_keys=[host_user_id])
    players: Mapped[list["RoomPlayer"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RoomPlayer.joined_at",
    )


class RoomPlayer(Base):
    __tablename__ = "room_players"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_players_room_user"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="PLAYER")
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    room: Mapped[Room] = relationship(back_populates="players")
    user: Mapped["User"] = relationship()
    character: Mapped["Character | None"] = relationship(
        "Character",
        primaryjoin="and_(RoomPlayer.room_id==Character.room_id, RoomPlayer.user_id==Character.user_id)",
        foreign_keys="[Character.room_id, Character.user_id]",
        uselist=False,
        viewonly=True,
    )
