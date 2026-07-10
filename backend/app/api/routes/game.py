from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user
from app.database.session import get_session
from app.models.room import Room
from app.models.user import User
from app.models.game_state import GameState
from app.models.player_action import PlayerAction
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory
from app.schemas.game import GameActionRequest, GameStateRead, GameHistoryResponse, PlayerActionRead, GameEventRead, StoryHistoryRead
from app.game_engine.game_engine import GameEngine

router = APIRouter()


from app.models.character import Character
from app.ai.prompt_builder import DungeonMasterPrompt
from app.ai.gemini_service import GeminiService
from app.services.context_service import ContextService
from app.socket.server import (
    notify_story_generated,
    notify_npc_dialogue,
    notify_atmosphere_changed,
)

@router.post("/action", response_model=GameStateRead)
async def process_action(
    payload: GameActionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GameStateRead:
    room = await session.scalar(
        select(Room).where(Room.code == payload.code.upper())
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

    try:
        updated_state = await GameEngine.process_action(
            session=session,
            room_id=room.id,
            user_id=current_user.id,
            action_text=payload.action,
        )

        # Retrieve player action outcome
        last_action_obj = await session.scalar(
            select(PlayerAction)
            .where(PlayerAction.room_id == room.id)
            .order_by(PlayerAction.created_at.desc())
        )

        if last_action_obj and last_action_obj.resolved_status in ["success", "failed"]:
            # Gather game context using unified ContextService
            context = await ContextService.build_game_context(session, room.id, current_user.id)
            characters = context["characters"]
            players_list = context["players_list"]
            recent_events_objs = context["recent_events_objs"]
            recent_events = context["recent_events"]
            story_history = context["story_history"]
            acting_char = context["acting_character"]

            # Build fallback narration
            acting_char = next((c for c in characters if c.user_id == current_user.id), None)
            acting_char_name = acting_char.character_name if acting_char else current_user.username
            
            fallback_parts = [
                f"{acting_char_name} attempted to '{last_action_obj.action_text}'. Resolution: {last_action_obj.outcome}."
            ]

            # Add context from events generated in this action
            for ev in recent_events_objs:
                if ev.created_at >= last_action_obj.created_at:
                    if ev.event_type == "Combat Started":
                        fallback_parts.append(
                            f"Combat round: {ev.details.get('attacker')} targets {ev.details.get('target')} dealing {ev.details.get('damage')} damage."
                        )
                    elif ev.event_type == "Quest Updated":
                        fallback_parts.append(
                            f"The quest progressed: {ev.details.get('new_quest') or ev.details.get('message')}"
                        )
                    elif ev.event_type == "Player Died":
                        fallback_parts.append(f"☠ {ev.details.get('character')} died.")
                    elif ev.event_type == "Item Collected":
                        items = ev.details.get("items")
                        gold = ev.details.get("gold")
                        items_str = f"items: {', '.join(items)}" if items else ""
                        gold_str = f"gold: {gold}" if gold else ""
                        fallback_parts.append(f"Items were found: {items_str} {gold_str}")

            fallback_parts.append(
                f"The environment shifts. Weather: {updated_state.weather}, Time: {updated_state.current_time}."
            )
            fallback_narration = " ".join(fallback_parts)

            # Build the structured prompt
            prompt = DungeonMasterPrompt(
                current_location=updated_state.current_location,
                current_time=updated_state.current_time,
                weather=updated_state.weather,
                current_quest=updated_state.current_quest,
                active_npcs=updated_state.active_npcs,
                active_monsters=updated_state.active_monsters,
                objects=updated_state.objects,
                inventory=updated_state.inventory,
                world_flags=updated_state.world_flags,
                players=players_list,
                last_action=last_action_obj.action_text,
                action_outcome=last_action_obj.outcome,
                recent_events=recent_events,
                story_history=story_history,
            )
            prompt_text = prompt.render()

            # Call Gemini
            ai_res = await GeminiService.generate_narration(prompt_text, fallback_narration)

            # Save the story narration
            new_story = StoryHistory(room_id=room.id, entry_text=ai_res.story)
            session.add(new_story)
            await session.commit()

            # Sockets broadcasts
            await notify_story_generated(room.code, ai_res.story)
            await notify_npc_dialogue(room.code, ai_res.npc_dialogue)
            await notify_atmosphere_changed(
                room.code, ai_res.atmosphere, ai_res.suggested_music
            )

        await session.refresh(updated_state)
        return GameStateRead.model_validate(updated_state)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/state", response_model=GameStateRead)
async def get_state(
    code: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GameStateRead:
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

    game_state = await session.scalar(
        select(GameState).where(GameState.room_id == room.id)
    )
    if not game_state:
        game_state = await GameEngine.initialize_game(session, room.id)

    return GameStateRead.model_validate(game_state)


@router.get("/history", response_model=GameHistoryResponse)
async def get_history(
    code: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GameHistoryResponse:
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

    actions = (await session.scalars(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.asc())
    )).all()
    
    events = (await session.scalars(
        select(GameEvent).where(GameEvent.room_id == room.id).order_by(GameEvent.created_at.asc())
    )).all()

    story = (await session.scalars(
        select(StoryHistory).where(StoryHistory.room_id == room.id).order_by(StoryHistory.created_at.asc())
    )).all()

    return GameHistoryResponse(
        actions=[PlayerActionRead.model_validate(a) for a in actions],
        events=[GameEventRead.model_validate(e) for e in events],
        story=[StoryHistoryRead.model_validate(s) for s in story],
    )
