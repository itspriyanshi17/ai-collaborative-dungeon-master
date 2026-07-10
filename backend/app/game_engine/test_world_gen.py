import asyncio
import random
import string
import sys
from fastapi import HTTPException
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.models.room import Room, RoomPlayer
from app.models.character import Character
from app.models.game_state import GameState
from app.models.player_action import PlayerAction
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory
from app.models.world import Location, Building, WorldObject, Region
from app.services.room_service import RoomService
from app.game_engine.game_engine import GameEngine
from app.api.routes.world_routes import TravelRequest, travel_to_location, get_world_locations, get_location_details


def generate_random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def run_world_gen_verification():
    print("=== STARTING WORLD GENERATION SYSTEM VERIFICATION ===")
    
    session = AsyncSessionLocal()
    
    # 1. Create players
    p1_username = f"world_p1_{generate_random_string()}"
    p2_username = f"world_p2_{generate_random_string()}"
    
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

    # 4. Ready & Start game (Triggers procedural World Generation)
    room = await room_service.toggle_ready(room_code, player2)
    room = await room_service.start_game(room_code, player1)
    print("Game started. Procedural World generated and persisted to Supabase.")

    # 5. Verify Locations exist in DB
    locs_in_db = (await session.scalars(
        select(Location).where(Location.room_id == room.id)
    )).all()
    print(f"Generated {len(locs_in_db)} locations in DB:")
    loc_by_name = {}
    for l in locs_in_db:
        print(f"  - {l.name} ({l.biome}), Danger: {l.danger_level}")
        loc_by_name[l.name] = l

    assert len(locs_in_db) == 6, f"FAIL: Expected 6 locations, got {len(locs_in_db)}"
    assert "Stoneford Village" in loc_by_name, "FAIL: Village missing"
    assert "Whispering Forest" in loc_by_name, "FAIL: Forest missing"
    assert "Silver River" in loc_by_name, "FAIL: River missing"
    assert "Spine Mountain" in loc_by_name, "FAIL: Mountain missing"
    assert "Cryptic Dungeon" in loc_by_name, "FAIL: Dungeon missing"
    assert "Shadowfang Castle" in loc_by_name, "FAIL: Castle missing"
    print("PASS: All required locations successfully created in database.")

    # 6. Verify starting location and current_location_id in GameState
    game_state = await session.scalar(
        select(GameState).where(GameState.room_id == room.id)
    )
    assert game_state.current_location == "Stoneford Village", "FAIL: Starting location is not Village"
    assert game_state.current_location_id == loc_by_name["Stoneford Village"].id, "FAIL: starting location id not set"
    print("PASS: GameState initialized at Stoneford Village with correct location ID coordinate.")

    # 7. Verify API: GET /api/world
    print("Calling API: get_world_locations...")
    world_api_res = await get_world_locations(room_code, session, player1)
    assert len(world_api_res) == 6, "FAIL: api did not return all locations"
    print("PASS: GET /api/world endpoint returns correct map list.")

    # 8. Verify API: GET /api/location/{id}
    print("Calling API: get_location_details for Village...")
    village_details = await get_location_details(loc_by_name["Stoneford Village"].id, session, player1)
    print(f"  - Village Buildings found: {[b.name for b in village_details.buildings]}")
    assert len(village_details.buildings) == 3, "FAIL: Village should contain 3 buildings (shop, tavern, temple)"
    building_types = [b.type for b in village_details.buildings]
    assert "shop" in building_types, "FAIL: Shop building missing"
    assert "tavern" in building_types, "FAIL: Tavern building missing"
    assert "temple" in building_types, "FAIL: Temple building missing"
    print("PASS: GET /api/location/{id} returns detailed buildings correctly.")

    print("Calling API: get_location_details for Whispering Forest...")
    forest_details = await get_location_details(loc_by_name["Whispering Forest"].id, session, player1)
    print(f"  - Forest Objects found: {[o.name for o in forest_details.objects]}")
    assert len(forest_details.objects) == 1, "FAIL: Forest should contain 1 object"
    assert forest_details.objects[0].name == "moldy chest", "FAIL: Forest object is not moldy chest"
    print("PASS: GET /api/location/{id} returns detailed objects correctly.")

    # 9. Verify API: POST /api/location/travel (Valid Connected Movement)
    dest_id = loc_by_name["Whispering Forest"].id
    print(f"\nSubmitting Travel Request: Stoneford Village -> Whispering Forest (UUID: {dest_id})")
    
    travel_payload = TravelRequest(code=room_code, destination_id=dest_id)
    updated_state = await travel_to_location(travel_payload, session, player1)
    
    # Reload and verify
    await session.refresh(game_state)
    assert game_state.current_location == "Whispering Forest", "FAIL: Location name did not update to Whispering Forest"
    assert game_state.current_location_id == dest_id, "FAIL: Location ID did not update to Whispering Forest UUID"
    assert game_state.weather == "Foggy", "FAIL: Weather did not sync to destination weather"
    
    # Verify active monsters and objects were synced
    assert len(game_state.active_monsters) == 1, "FAIL: Active monsters not loaded for Forest"
    assert game_state.active_monsters[0]["name"] == "gnoll hunter", "FAIL: Active monster is not gnoll hunter"
    assert len(game_state.objects) == 1, "FAIL: Active objects not loaded for Forest"
    assert game_state.objects[0]["name"] == "moldy chest", "FAIL: Active object is not moldy chest"
    print("PASS: Authoritative travel processed. Coordinates, monsters, weather, and objects synchronized successfully.")

    # Verify Gemini narrated the travel action
    travel_story = (await session.scalars(
        select(StoryHistory).where(StoryHistory.room_id == room.id).order_by(StoryHistory.created_at.desc()).limit(1)
    )).first()
    print(f"  - Travel Story narration generated: {travel_story.entry_text[:120]}...")
    assert travel_story is not None, "FAIL: Story narration not written to DB"
    print("PASS: Gemini story narration generated and stored successfully.")

    # 10. Verify API: POST /api/location/travel (Invalid/Illegal Unconnected Movement)
    illegal_dest_id = loc_by_name["Spine Mountain"].id
    print(f"\nSubmitting Illegal Travel Request: Whispering Forest -> Spine Mountain (Not connected) (UUID: {illegal_dest_id})")
    
    illegal_payload = TravelRequest(code=room_code, destination_id=illegal_dest_id)
    try:
        await travel_to_location(illegal_payload, session, player1)
        print("FAIL: Unconnected movement travel request succeeded (should have thrown 400).")
        sys.exit(1)
    except HTTPException as e:
        print(f"PASS: Unconnected movement correctly rejected with status: {e.status_code}, detail: '{e.detail}'")
        assert e.status_code == 400, f"FAIL: Expected status 400, got {e.status_code}"

    # Verify state remains at Whispering Forest
    await session.refresh(game_state)
    assert game_state.current_location == "Whispering Forest", "FAIL: Current location changed on illegal travel"

    # Cleanup DB records
    print("\nCleaning up test records from database...")
    # locations, buildings, objects
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
    
    print("\n=== ALL WORLD GENERATION SYSTEM VERIFICATION TESTS PASSED! ===")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_world_gen_verification())
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\nWorld Gen verification encountered an error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
