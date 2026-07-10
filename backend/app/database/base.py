from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models import character, room, user, game_state, player_action, game_event, story_history, world, npc  # noqa: E402,F401
