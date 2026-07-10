import asyncio
import random
import string
import uuid
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


def generate_random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def run_verification():
    print("=== STARTING CORE GAME ENGINE VERIFICATION ===")
    
    session = AsyncSessionLocal()
    
    # 1. Create two players
    p1_username = f"player1_{generate_random_string()}"
    p1_email = f"{p1_username}@test.com"
    p2_username = f"player2_{generate_random_string()}"
    p2_email = f"{p2_username}@test.com"
    
    player1 = User(
        email=p1_email,
        username=p1_username,
        hashed_password="dummy_hashed_password",
        is_active=True
    )
    player2 = User(
        email=p2_email,
        username=p2_username,
        hashed_password="dummy_hashed_password",
        is_active=True
    )
    
    session.add_all([player1, player2])
    await session.commit()
    await session.refresh(player1)
    await session.refresh(player2)
    
    print(f"Created Player 1: {player1.username} (ID: {player1.id})")
    print(f"Created Player 2: {player2.username} (ID: {player2.id})")

    # 2. Player 1 creates room
    room_service = RoomService(session)
    room = await room_service.create_room(player1)
    print(f"Room created with code: {room.code}")

    # 3. Player 2 joins room
    await room_service.join_room(room.code, player2)
    print(f"Player 2 joined room {room.code}")

    # 4. Player 1 creates character (Warrior)
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
    session.add(char1)
    await session.commit()
    print("Player 1 created character: Gildor the Mighty (Warrior)")

    # 5. Player 2 creates character (Mage)
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
    session.add(char2)
    await session.commit()
    print("Player 2 created character: Eldrin the Wise (Mage)")

    # Close session and start a new one to simulate a fresh HTTP request context
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

    # 6. Player 2 toggles ready
    room = await room_service.toggle_ready(room_code, player2)
    print("Player 2 set to Ready")

    # 7. Start the game (Host/Player 1 starts it)
    print("Starting game...")
    room.status = "playing"
    session.add(room)
    game_state = await GameEngine.initialize_game(session, room.id)
    await session.commit()
    print(f"Room status updated to: {room.status}")

    # 8. Verify game state was initialized
    game_state = await session.scalar(
        select(GameState).where(GameState.room_id == room.id)
    )
    assert game_state is not None, "FAIL: GameState not initialized"
    assert game_state.current_location == "Dungeon Entrance", f"FAIL: Initial location incorrect: {game_state.current_location}"
    assert game_state.current_quest == "Open the Stone Gate", f"FAIL: Initial quest incorrect: {game_state.current_quest}"
    assert len(game_state.objects) == 3, "FAIL: Initial objects count incorrect"
    print("PASS: GameState initialized successfully in Supabase.")

    # 9. Verify StoryHistory has the initial entry
    initial_story = await session.scalar(
        select(StoryHistory).where(StoryHistory.room_id == room.id)
    )
    assert initial_story is not None, "FAIL: Initial story entry not created"
    print(f"PASS: Initial story entry recorded: \"{initial_story.entry_text}\"")

    # 10. Perform Action: Inspect General Room
    print("\n--- Submitting Action: 'inspect room' ---")
    game_state = await GameEngine.process_action(session, room.id, player1.id, "inspect room")
    last_action = await session.scalar(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.desc())
    )
    assert last_action.resolved_status == "success", "FAIL: Action failed"
    session.add(StoryHistory(room_id=room.id, entry_text=last_action.outcome))
    await session.commit()
    print(f"Outcome: {last_action.outcome}")
    print("PASS: general inspect action resolved successfully.")

    # 11. Perform Action: Talk to Wizard
    print("\n--- Submitting Action: 'talk to wizard' ---")
    game_state = await GameEngine.process_action(session, room.id, player1.id, "talk to wizard")
    last_action = await session.scalar(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.desc())
    )
    assert last_action.resolved_status == "success", "FAIL: Action failed"
    session.add(StoryHistory(room_id=room.id, entry_text=last_action.outcome))
    await session.commit()
    print(f"Outcome: {last_action.outcome}")
    print("PASS: NPC dialogue conversation succeeded.")

    # 12. Perform Action: Open wooden chest
    print("\n--- Submitting Action: 'open wooden chest' ---")
    game_state = await GameEngine.process_action(session, room.id, player1.id, "open wooden chest")
    last_action = await session.scalar(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.desc())
    )
    assert last_action.resolved_status == "success", "FAIL: Action failed"
    session.add(StoryHistory(room_id=room.id, entry_text=last_action.outcome))
    await session.commit()
    print(f"Outcome: {last_action.outcome}")
    
    # Reload character 1 gold
    await session.refresh(char1)
    assert char1.gold == 150, f"FAIL: Gold not awarded to character. Current: {char1.gold}"
    assert "iron key" in game_state.inventory["party"], "FAIL: Item 'iron key' not in inventory"
    assert "health potion" in game_state.inventory["party"], "FAIL: Item 'health potion' not in inventory"
    print("PASS: Wooden chest opened, gold awarded, and items transferred to inventory.")

    # 13. Perform Action: Open stone gate
    print("\n--- Submitting Action: 'open stone gate' ---")
    game_state = await GameEngine.process_action(session, room.id, player1.id, "open stone gate")
    last_action = await session.scalar(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.desc())
    )
    assert last_action.resolved_status == "success", "FAIL: Action failed"
    session.add(StoryHistory(room_id=room.id, entry_text=last_action.outcome))
    await session.commit()
    print(f"Outcome: {last_action.outcome}")
    assert "iron key" not in game_state.inventory["party"], "FAIL: Key not consumed from inventory"
    
    # Verify quest updated
    assert game_state.current_quest == "Defeat the Goblin Warrior and proceed to the Treasure Chamber", f"FAIL: Quest not updated: {game_state.current_quest}"
    print("PASS: Stone gate unlocked using key. Quest progression triggered.")

    # 14. Perform Action: Go to Goblin Camp
    print("\n--- Submitting Action: 'go to goblin camp' ---")
    game_state = await GameEngine.process_action(session, room.id, player1.id, "go to goblin camp")
    last_action = await session.scalar(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.desc())
    )
    assert last_action.resolved_status == "success", f"FAIL: Move failed: {last_action.outcome}"
    session.add(StoryHistory(room_id=room.id, entry_text=last_action.outcome))
    await session.commit()
    print(f"Outcome: {last_action.outcome}")
    assert game_state.current_location == "Goblin Camp", "FAIL: Current location not updated"
    assert len(game_state.active_monsters) == 1 and game_state.active_monsters[0]["name"] == "goblin warrior", "FAIL: Goblin warrior not loaded in Goblin Camp"
    print("PASS: Traveled to Goblin Camp. Room details loaded.")

    # 15. Perform Action: Attack goblin warrior (triggers combat round and enemy counterattack)
    print("\n--- Submitting Action: 'attack goblin warrior' ---")
    old_player_hp = char1.current_health
    game_state = await GameEngine.process_action(session, room.id, player1.id, "attack goblin warrior")
    last_action = await session.scalar(
        select(PlayerAction).where(PlayerAction.room_id == room.id).order_by(PlayerAction.created_at.desc())
    )
    assert last_action.resolved_status == "success", "FAIL: Attack failed"
    session.add(StoryHistory(room_id=room.id, entry_text=last_action.outcome))
    await session.commit()
    print(f"Outcome: {last_action.outcome}")
    
    # Reload character 1 health
    await session.refresh(char1)
    print(f"Gildor's HP before: {old_player_hp} -> after counterattack: {char1.current_health}")
    assert char1.current_health < old_player_hp, "FAIL: Monster did not counter-attack player (HP didn't drop)"
    print("PASS: Combat round completed. Player dealt damage and monster counter-attacked player character.")

    # 16. Verify events table contains correct events
    print("\nVerifying DB events...")
    events = (await session.scalars(
        select(GameEvent).where(GameEvent.room_id == room.id).order_by(GameEvent.created_at.asc())
    )).all()
    print(f"Total events recorded in Supabase: {len(events)}")
    for ev in events:
        print(f"  - Event: {ev.event_type} | Details: {ev.details}")
    
    assert len(events) >= 5, "FAIL: Expected multiple events to be persisted"
    print("PASS: Multiple game events successfully persisted to database.")

    # 17. Verify story history matches
    print("\nVerifying story history logs...")
    stories = (await session.scalars(
        select(StoryHistory).where(StoryHistory.room_id == room.id).order_by(StoryHistory.created_at.asc())
    )).all()
    print(f"Total story history entries: {len(stories)}")
    for st in stories:
        print(f"  - Story: {st.entry_text}")
    assert len(stories) >= 5, "FAIL: Expected multiple story narrative logs"
    print("PASS: All story history successfully persisted to database.")

    # Cleanup DB records
    print("\nCleaning up test records from database...")
    await session.delete(game_state)
    for st in stories:
        await session.delete(st)
    for ev in events:
        await session.delete(ev)
    # actions
    actions = (await session.scalars(select(PlayerAction).where(PlayerAction.room_id == room.id))).all()
    for ac in actions:
        await session.delete(ac)
    await session.delete(char1)
    await session.delete(char2)
    # players
    players = (await session.scalars(select(RoomPlayer).where(RoomPlayer.room_id == room.id))).all()
    for pl in players:
        await session.delete(pl)
    await session.delete(room)
    await session.delete(player1)
    await session.delete(player2)
    await session.commit()
    await session.close()
    
    print("\n=== ALL VERIFICATION TESTS PASSED! ===")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_verification())
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\nVerification encountered an error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
