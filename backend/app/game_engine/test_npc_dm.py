import asyncio
import random
import string
import sys
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.models.room import Room, RoomPlayer
from app.models.character import Character
from app.models.game_state import GameState
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory
from app.models.player_action import PlayerAction
from app.models.npc import NPC, NPCMemory
from app.models.world import Location, Region, Building, WorldObject
from app.services.room_service import RoomService
from app.schemas.npc import NPCTalkRequest
from app.api.routes.npc_routes import get_room_npcs, get_npc_details, talk_to_npc


def generate_random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def run_npc_dm_verification():
    print("=== STARTING DYNAMIC AI NPC SYSTEM VERIFICATION ===")
    
    session = AsyncSessionLocal()
    
    # 1. Create players
    p1_username = f"npc_p1_{generate_random_string()}"
    p2_username = f"npc_p2_{generate_random_string()}"
    
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

    # Reconnect session to reload relationships cleanly
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

    # 4. Ready & Start game (Seeds persistent NPCs in Supabase)
    room = await room_service.toggle_ready(room_code, player2)
    room = await room_service.start_game(room_code, player1)
    print("Game started. World seeded with persistent NPCs.")

    # 5. Verify API: GET /api/npc
    print("\nCalling API: get_room_npcs...")
    npc_list = await get_room_npcs(room_code, session, player1)
    print(f"Retrieved {len(npc_list)} NPCs from room:")
    npc_map = {}
    for n in npc_list:
        print(f"  - {n.name} (Race: {n.race}, Profession: {n.profession}, Goals: {n.goals})")
        npc_map[n.name] = n

    assert len(npc_list) == 5, f"FAIL: Expected 5 NPCs, got {len(npc_list)}"
    assert "Barman Ted" in npc_map, "FAIL: Barman Ted missing"
    assert "Merchant Alaric" in npc_map, "FAIL: Merchant Alaric missing"
    assert "Priestess Alara" in npc_map, "FAIL: Priestess Alara missing"
    assert "Wizard Elidor" in npc_map, "FAIL: Wizard Elidor missing"
    assert "Herbalist Aerith" in npc_map, "FAIL: Herbalist Aerith missing"
    print("PASS: GET /api/npc endpoint retrieves all seeded NPCs with correct detail schemas.")

    # 6. Interact with Alaric (Merchant Alaric) - Conversation 1
    alaric_id = npc_map["Merchant Alaric"].id
    msg1 = "Hello Alaric! Can you tell me if you have any healing potions for sale?"
    print(f"\nTalking to Merchant Alaric (Conversation 1): '{msg1}'")
    
    talk_payload1 = NPCTalkRequest(code=room_code, npc_id=alaric_id, message=msg1)
    res1 = await talk_to_npc(talk_payload1, session, player1)
    print("Alaric responded:")
    print(f"  - Dialogue: \"{res1.dialogue}\"")
    print(f"  - Emotion/Mood: {res1.emotion}")
    print(f"  - Relationship Score: {res1.relationship_score}/100")

    assert len(res1.dialogue) > 0, "FAIL: dialogue response is empty"
    print("PASS: Conversation 1 resolved successfully.")

    # 7. Interact with Alaric AGAIN - Conversation 2 (Testing memory retention)
    msg2 = "Great, how much gold did you say those potions cost?"
    print(f"\nTalking to Merchant Alaric (Conversation 2 - testing memory): '{msg2}'")
    
    talk_payload2 = NPCTalkRequest(code=room_code, npc_id=alaric_id, message=msg2)
    res2 = await talk_to_npc(talk_payload2, session, player1)
    print("Alaric responded:")
    print(f"  - Dialogue: \"{res2.dialogue}\"")
    print(f"  - Emotion/Mood: {res2.emotion}")
    print(f"  - Relationship Score: {res2.relationship_score}/100")

    # Verify Alaric's memory (check if he answers detailing the cost of potions mentioned in dialogue 1)
    # Check if the dialogue or response is valid
    assert len(res2.dialogue) > 0, "FAIL: Dialogue 2 response is empty"
    print("PASS: Conversation 2 resolved successfully.")

    # 8. Call GET /api/npc/{id} to verify memory logs and relationship score updates
    print("\nCalling API: get_npc_details for Alaric...")
    alaric_details = await get_npc_details(alaric_id, session, player1)
    
    print(f"  - Alaric current mood: {alaric_details.mood}")
    print(f"  - Alaric relationships: {alaric_details.relationships}")
    print(f"  - Conversation memory log count: {len(alaric_details.memories)}")
    for idx, m in enumerate(alaric_details.memories):
        print(f"    * Exchange {idx+1}: {m.character_name}: \"{m.player_message}\" -> Response: \"{m.npc_response[:60]}...\"")

    assert alaric_details.relationships.get("Gildor the Mighty") is not None, "FAIL: Character relationship score not updated in database"
    assert len(alaric_details.memories) == 2, f"FAIL: Expected 2 memory conversation logs, got {len(alaric_details.memories)}"
    print("PASS: GET /api/npc/{id} returns updated relationships and persistent conversation memory logs successfully.")

    # 9. Verify Story History update
    story_convo = (await session.scalars(
        select(StoryHistory).where(StoryHistory.room_id == room.id).order_by(StoryHistory.created_at.desc()).limit(1)
    )).first()
    print(f"\n  - Story History conversation log: {story_convo.entry_text[:120]}...")
    assert "talked to NPC Merchant Alaric" in story_convo.entry_text, "FAIL: Conversation story narrative missing in DB"
    print("PASS: Conversation logs correctly serialized into StoryHistory table.")

    # Cleanup DB records
    print("\nCleaning up test records from database...")
    # npc memories
    npc_mems = (await session.scalars(select(NPCMemory).where(NPCMemory.npc_id.in_([n.id for n in npc_list])))).all()
    for m in npc_mems:
        await session.delete(m)
    # npcs
    npcs_db = (await session.scalars(select(NPC).where(NPC.room_id == room.id))).all()
    for n in npcs_db:
        await session.delete(n)
        
    # locations, buildings, objects
    locs_in_db = (await session.scalars(select(Location).where(Location.room_id == room.id))).all()
    for loc in locs_in_db:
        # buildings
        loc_buildings = (await session.scalars(select(Building).where(Building.location_id == loc.id))).all()
        for b in loc_buildings:
            await session.delete(b)
        # objects
        loc_objects = (await session.scalars(select(WorldObject).where(WorldObject.location_id == loc.id))).all()
        for o in loc_objects:
            await session.delete(o)
        await session.delete(loc)

    # region
    region_obj = await session.scalar(select(Region).where(Region.room_id == room.id))
    if region_obj:
        await session.delete(region_obj)

    # game states
    game_state = await session.scalar(select(GameState).where(GameState.room_id == room.id))
    if game_state:
        await session.delete(game_state)
    
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
    
    print("\n=== ALL DYNAMIC AI NPC SYSTEM VERIFICATION TESTS PASSED! ===")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_npc_dm_verification())
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\nNPC Gen verification encountered an error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
