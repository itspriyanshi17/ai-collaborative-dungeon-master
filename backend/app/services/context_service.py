from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.character import Character
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory


class ContextService:
    @staticmethod
    async def build_game_context(
        session: AsyncSession,
        room_id: UUID,
        current_user_id: UUID | None = None
    ) -> dict:
        # Gather characters in the room
        characters = (await session.scalars(
            select(Character).where(Character.room_id == room_id)
        )).all()
        
        players_list = []
        acting_character = None
        for c in characters:
            players_list.append({
                "name": c.character_name,
                "class": c.character_class,
                "level": c.level,
                "hp": c.current_health,
                "max_hp": c.health,
                "mana": c.current_mana,
                "max_mana": c.mana,
            })
            if current_user_id and c.user_id == current_user_id:
                acting_character = c

        # Gather recent events (last 10)
        recent_events_objs = (await session.scalars(
            select(GameEvent)
            .where(GameEvent.room_id == room_id)
            .order_by(GameEvent.created_at.desc())
            .limit(10)
        )).all()
        
        recent_events = [
            {"event_type": ev.event_type, "details": ev.details}
            for ev in recent_events_objs
        ]

        # Gather story history memory (last 15 items)
        story_history_objs = (await session.scalars(
            select(StoryHistory)
            .where(StoryHistory.room_id == room_id)
            .order_by(StoryHistory.created_at.desc())
            .limit(15)
        )).all()
        story_history = [s.entry_text for s in reversed(story_history_objs)]

        return {
            "characters": characters,
            "players_list": players_list,
            "acting_character": acting_character,
            "recent_events_objs": recent_events_objs,
            "recent_events": recent_events,
            "story_history": story_history,
        }
