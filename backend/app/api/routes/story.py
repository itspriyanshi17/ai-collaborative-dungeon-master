from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user
from app.database.session import get_session
from app.models.room import Room
from app.models.user import User
from app.models.story_history import StoryHistory
from app.schemas.game import StoryHistoryRead

router = APIRouter()


@router.get("/history", response_model=list[StoryHistoryRead])
async def get_story_history(
    code: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[StoryHistoryRead]:
    room = await session.scalar(
        select(Room).where(Room.code == code.upper())
    )
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    from app.models.room import RoomPlayer
    player_in_room = await session.scalar(
        select(RoomPlayer).where(
            RoomPlayer.room_id == room.id, RoomPlayer.user_id == current_user.id
        )
    )
    if not player_in_room:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this room.",
        )

    story_entries = (await session.scalars(
        select(StoryHistory)
        .where(StoryHistory.room_id == room.id)
        .order_by(StoryHistory.created_at.asc())
    )).all()

    return [StoryHistoryRead.model_validate(s) for s in story_entries]
