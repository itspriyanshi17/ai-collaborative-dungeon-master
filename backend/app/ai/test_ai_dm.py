import asyncio
import random
import string
import sys
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.models.room import Room, RoomPlayer
from app.models.character import Character
from app.models.game_state import GameState
from app.models.player_action import PlayerAction
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory
from app.services.room_service import RoomService
from app.game_engine.game_engine import GameEngine
from app.ai.gemini_service import GeminiService, AIDungeonMasterResponse
from app.ai.prompt_builder import DungeonMasterPrompt
from app.config import settings


def generate_random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def run_ai_dm_verification():
    print("=== STARTING AI DUNGEON MASTER VERIFICATION ===")
    
    session = AsyncSessionLocal()
    
    # 1. Create players
    p1_username = f"ai_p1_{generate_random_string()}"
    p2_username = f"ai_p2_{generate_random_string()}"
    
    player1 = User(
        email=f"{p1_username}@test.com",
        username=p1_username,
        hashed_password="dummy_hashed_password",
        is_active=True
    )
    player2 = User(
        email=f"{p2_username}@test.com",
        username=p2_username,
        hashed_password="dummy_hashed_password",
        is_active=True
    )
    
    session.add_all([player1, player2])
    await session.commit()
    await session.refresh(player1)
    await session.refresh(player2)
    
    print(f"Players created: {player1.username}, {player2.username}")

    # 2. Setup Room
    room_service = RoomService(session)
    room = await room_service.create_room(player1)
    await room_service.join_room(room.code, player2)
    
    # 3. Create characters
    char1 = Character(
        user_id=player1.id,
        room_id=room.id,
        character_name="Gildor the Mighty",
        character_class="Warrior",
        avatar="warrior_icon",
        health=140,
        mana=20,
        strength=16,
        intelligence=6,
        agility=8,
        defense=12,
        luck=8,
        current_health=140,
        current_mana=20,
        gold=100,
        ready_for_game=False
    )
    char2 = Character(
        user_id=player2.id,
        room_id=room.id,
        character_name="Eldrin the Wise",
        character_class="Mage",
        avatar="mage_icon",
        health=80,
        mana=150,
        strength=6,
        intelligence=18,
        agility=9,
        defense=6,
        luck=10,
        current_health=80,
        current_mana=150,
        gold=120,
        ready_for_game=False
    )
    session.add_all([char1, char2])
    await session.commit()
    print("Characters created.")

    # Separation of sessions to reload clean relationship links
    room_code = room.code
    player1_id = player1.id
    player2_id = player2.id
    char1_id = char1.id
    char2_id = char2.id
    await session.close()

    session = AsyncSessionLocal()
    room_service = RoomService(session)
    player1 = await session.get(User, player1_id)
    player2 = await session.get(User, player2_id)
    char1 = await session.get(Character, char1_id)
    char2 = await session.get(Character, char2_id)

    # 4. Ready & Start game
    room = await room_service.toggle_ready(room_code, player2)
    room.status = "playing"
    session.add(room)
    game_state = await GameEngine.initialize_game(session, room.id)
    await session.commit()
    print("Game started and initialized.")

    # Get updated GameState
    game_state = await session.scalar(
        select(GameState).where(GameState.room_id == room.id)
    )

    # 5. Process first action and trigger Gemini
    action_text = "open wooden chest"
    print(f"\nProcessing player action: '{action_text}'")
    
    # Process Game Engine
    updated_state = await GameEngine.process_action(session, room.id, player1.id, action_text)
    
    # Load last action from DB
    last_action_obj = await session.scalar(
        select(PlayerAction)
        .where(PlayerAction.room_id == room.id)
        .order_by(PlayerAction.created_at.desc())
    )
    
    # Prepare player and history details for AI prompt
    players_list = [{
        "name": char1.character_name,
        "class": char1.character_class,
        "level": char1.level,
        "hp": char1.current_health,
        "max_hp": char1.health,
        "mana": char1.current_mana,
        "max_mana": char1.mana,
    }, {
        "name": char2.character_name,
        "class": char2.character_class,
        "level": char2.level,
        "hp": char2.current_health,
        "max_hp": char2.health,
        "mana": char2.current_mana,
        "max_mana": char2.mana,
    }]
    
    recent_events_objs = (await session.scalars(
        select(GameEvent).where(GameEvent.room_id == room.id).order_by(GameEvent.created_at.desc()).limit(10)
    )).all()
    recent_events = [{"event_type": ev.event_type, "details": ev.details} for ev in recent_events_objs]
    
    story_history_objs = (await session.scalars(
        select(StoryHistory).where(StoryHistory.room_id == room.id).order_by(StoryHistory.created_at.desc()).limit(15)
    )).all()
    story_history = [s.entry_text for s in reversed(story_history_objs)]
    
    # Build deterministic fallback outcome description
    fallback_narration = f"Gildor opened the wooden chest. Outcomes: {last_action_obj.outcome}."

    # Render Prompt Builder
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
        story_history=story_history
    )
    prompt_text = prompt.render()
    print("AI Prompt Builder generated successfully.")

    # 6. Test Gemini Call
    print("Calling Gemini API...")
    ai_response = await GeminiService.generate_narration(prompt_text, fallback_narration)
    print("Gemini response received.")
    print(f"  - Story: {ai_response.story}")
    print(f"  - NPC Dialogue: {ai_response.npc_dialogue}")
    print(f"  - Atmosphere: {ai_response.atmosphere}")
    print(f"  - Suggested Music: {ai_response.suggested_music}")

    # Validate output structure
    assert ai_response.story is not None and len(ai_response.story) > 0, "FAIL: story is missing or empty"
    assert ai_response.atmosphere is not None, "FAIL: atmosphere is missing"
    assert ai_response.suggested_music is not None, "FAIL: music is missing"
    print("PASS: Gemini generated valid structured JSON response.")

    # Save to DB
    new_story = StoryHistory(room_id=room.id, entry_text=ai_response.story)
    session.add(new_story)
    await session.commit()
    print("PASS: Story narration successfully saved to StoryHistory table.")

    # 7. Check Game Engine Authority (verify character gold, stats, inventory from action success)
    await session.refresh(char1)
    assert char1.gold == 150, f"FAIL: Character gold not authoritative (expected 150, got {char1.gold})"
    assert "iron key" in updated_state.inventory["party"], "FAIL: Party inventory not authoritative (missing key)"
    print("PASS: Core Game Engine remains authoritative. Stats and items resolved correctly, untouched by AI.")

    # 8. Verify /api/story/history query
    print("Verifying story history retrieval...")
    hist_entries = (await session.scalars(
        select(StoryHistory).where(StoryHistory.room_id == room.id).order_by(StoryHistory.created_at.asc())
    )).all()
    print(f"Retrieved {len(hist_entries)} story events:")
    for h in hist_entries:
        print(f"  - {h.entry_text[:90]}...")
    assert len(hist_entries) >= 2, "FAIL: Missing initial intro story or final AI story in DB"
    print("PASS: Story history retrieves correctly.")

    # 9. Test Failure Handling (Force fail using an invalid API key / client configuration)
    print("\n--- Testing AI Failure Handling & Fallback logic ---")
    
    # Store current API key to restore later
    original_key = settings.gemini_api_key
    settings.gemini_api_key = "INVALID_API_KEY_FOR_FAILURE_TEST"
    GeminiService._client = None  # Force re-instantiation with bad key
    
    print("Invoking narration with bad credentials (should retry and trigger fallback)...")
    fallback_res = await GeminiService.generate_narration(prompt_text, "FALLBACK: Chest was opened, iron key collected.")
    print("Narration returned.")
    print(f"  - Fallback story: {fallback_res.story}")
    assert "FALLBACK" in fallback_res.story or "The narrative unfolds" in fallback_res.story, "FAIL: Fallback narration logic did not run"
    print("PASS: Fallback narration generated successfully under connection failure.")

    # Restore key
    settings.gemini_api_key = original_key
    GeminiService._client = None

    # Cleanup DB records
    print("\nCleaning up test records from database...")
    # game states
    await session.delete(updated_state)
    # stories
    stories = (await session.scalars(select(StoryHistory).where(StoryHistory.room_id == room.id))).all()
    for s in stories:
        await session.delete(s)
    # events
    events = (await session.scalars(select(GameEvent).where(GameEvent.room_id == room.id))).all()
    for e in events:
        await session.delete(e)
    # actions
    actions = (await session.scalars(select(PlayerAction).where(PlayerAction.room_id == room.id))).all()
    for a in actions:
        await session.delete(a)
    # characters
    await session.delete(char1)
    await session.delete(char2)
    # players
    players = (await session.scalars(select(RoomPlayer).where(RoomPlayer.room_id == room.id))).all()
    for p in players:
        await session.delete(p)
    # room
    await session.delete(room)
    # users
    await session.delete(player1)
    await session.delete(player2)
    await session.commit()
    await session.close()
    
    print("\n=== ALL AI DUNGEON MASTER VERIFICATION TESTS PASSED! ===")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_ai_dm_verification())
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\nAI DM verification encountered an error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
