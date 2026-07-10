from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, String, JSON, Uuid, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Biome(Base):
    __tablename__ = "biomes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    room = relationship("Room")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    region_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("regions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    biome_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("biomes.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    biome: Mapped[str] = mapped_column(String(50), nullable=False)
    
    connected_locations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # list of Uuids
    npc_list: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    monster_list: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    loot_table: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    weather: Mapped[str] = mapped_column(String(50), nullable=False, default="Clear")
    danger_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    room = relationship("Room")
    region = relationship("Region")
    biome_rel = relationship("Biome")
    buildings = relationship("Building", back_populates="location", cascade="all, delete-orphan")
    objects = relationship("WorldObject", back_populates="location", cascade="all, delete-orphan")


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    location_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # shop, tavern, temple
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    
    npc_list: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    inventory: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    location = relationship("Location", back_populates="buildings")


class WorldObject(Base):
    __tablename__ = "objects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    location_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # chest, gate, wall
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # open, closed, destroyed, intact
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    location = relationship("Location", back_populates="objects")
