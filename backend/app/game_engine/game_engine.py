import random
import re
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import selectinload

from app.models.game_state import GameState
from app.models.player_action import PlayerAction
from app.models.game_event import GameEvent
from app.models.story_history import StoryHistory
from app.models.character import Character
from app.models.room import Room, RoomPlayer
from app.socket.server import (
    notify_world_updated,
    notify_player_action,
    notify_event_created,
    notify_combat_started,
    notify_inventory_updated,
    notify_quest_updated,
)


class GameEngine:
    @staticmethod
    async def initialize_game(
        session: AsyncSession,
        room_id: UUID,
        start_location_id: UUID | None = None,
        start_location_name: str = "Dungeon Entrance",
        start_location_desc: str = (
            "The party stands at the Dungeon Entrance. A thick fog hangs in the air. "
            "An old wizard named Elidor watches them silently. A small, hostile goblin sneers from the shadows. "
            "Ahead lies a massive, locked stone gate and a crumbling wall, and to the side sits a closed wooden chest."
        ),
        start_weather: str = "Foggy",
        start_npcs: list | None = None,
        start_monsters: list | None = None,
        start_objects: list | None = None
    ) -> GameState:
        # Check if GameState already exists
        existing = await session.scalar(
            select(GameState).where(GameState.room_id == room_id)
        )
        if existing:
            return existing

        if start_npcs is None:
            start_npcs = [
                {
                    "name": "Elidor",
                    "type": "wizard",
                    "health": 100,
                    "status": "friendly",
                    "dialogue": "Beware the stone gate! You'll need a key from the wooden chest to open it. Or perhaps you can find another way..."
                }
            ]
        if start_monsters is None:
            start_monsters = [
                {
                    "name": "small goblin",
                    "health": 30,
                    "max_health": 30,
                    "damage": 8,
                    "defense": 2,
                    "xp": 50,
                    "gold": 20
                }
            ]
        if start_objects is None:
            start_objects = [
                {
                    "name": "wooden chest",
                    "type": "chest",
                    "status": "closed",
                    "items": ["iron key", "health potion"],
                    "gold": 50
                },
                {
                    "name": "stone gate",
                    "type": "gate",
                    "status": "locked",
                    "requires": "iron key",
                    "leads_to": "Goblin Camp"
                },
                {
                    "name": "crumbly wall",
                    "type": "wall",
                    "status": "intact",
                    "leads_to": "Hidden Cave"
                }
            ]

        # Create initial GameState
        initial_state = GameState(
            room_id=room_id,
            current_location_id=start_location_id,
            current_location=start_location_name,
            current_time="Day 1 - Morning",
            weather=start_weather,
            current_quest="Explore " + start_location_name if start_location_name != "Dungeon Entrance" else "Open the Stone Gate",
            active_npcs=start_npcs,
            active_monsters=start_monsters,
            objects=start_objects,
            inventory={
                "party": [],
                "characters": {}
            },
            world_flags={
                "visited_locations": [start_location_name],
                "completed_quests": [],
                "killed_monsters": [],
                "opened_chests": [],
                "destroyed_objects": [],
                "npc_relationships": {
                    "Elidor": 50
                }
            },
            turn_index=0,
            turn_stage="player"
        )
        session.add(initial_state)
        await session.flush()

        # Create initial narrative entry
        story = StoryHistory(room_id=room_id, entry_text=start_location_desc)
        session.add(story)
        
        # Create initial event
        event = GameEvent(
            room_id=room_id,
            event_type="Game Started",
            details={"narrative": start_location_desc}
        )
        session.add(event)
        
        await session.commit()
        return initial_state

    @staticmethod
    async def process_action(
        session: AsyncSession, room_id: UUID, user_id: UUID, action_text: str
    ) -> GameState:
        # Load Room to verify status and get room code
        room = await session.scalar(
            select(Room)
            .where(Room.id == room_id)
            .options(
                selectinload(Room.players).selectinload(RoomPlayer.user),
                selectinload(Room.players).selectinload(RoomPlayer.character),
            )
        )
        if not room:
            raise ValueError("Room not found.")
        if room.status != "playing":
            raise ValueError("Game is not active in this room.")

        room_code = room.code

        # Load current GameState
        game_state = await session.scalar(
            select(GameState).where(GameState.room_id == room_id)
        )
        if not game_state:
            # Auto-initialize if it somehow doesn't exist
            game_state = await GameEngine.initialize_game(session, room_id)

        # Load character performing the action
        character = await session.scalar(
            select(Character).where(
                Character.room_id == room_id, Character.user_id == user_id
            )
        )
        if not character:
            raise ValueError("Character not found for this player in the room.")

        if character.current_health <= 0:
            raise ValueError("Your character is dead and cannot perform actions. Use 'revive' or wait.")

        # Normalize the action text
        cleaned_action = action_text.lower().strip()
        cleaned_action = re.sub(r"^(i|we|the party)\s+", "", cleaned_action)
        cleaned_action = re.sub(r"[.!?]+$", "", cleaned_action)

        resolved_status = "rejected"
        outcome = "I don't understand that action. Try commands like: 'inspect room', 'open wooden chest', 'go to goblin camp', 'attack goblin', 'talk to wizard', or 'use health potion'."
        event_type = "Player Action Attempted"
        event_details = {}

        # ----------------------------------------------------
        # ACTION PARSING
        # ----------------------------------------------------

        # 1. INSPECT / LOOK / SEARCH
        if any(cleaned_action.startswith(v) for v in ["inspect", "look at", "look around", "search"]):
            target = re.sub(r"^(inspect|look at|look around|search)\s+", "", cleaned_action).strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            if not target or target in ["room", "area", "around", "surroundings"]:
                # Inspect the general room
                monsters_desc = ", ".join(m["name"] for m in game_state.active_monsters) if game_state.active_monsters else "no hostile monsters"
                npcs_desc = ", ".join(n["name"] for n in game_state.active_npcs) if game_state.active_npcs else "no NPCs"
                objects_desc = ", ".join(o["name"] for o in game_state.objects) if game_state.objects else "no items"
                outcome = (
                    f"You look around {game_state.current_location}. "
                    f"You see {objects_desc}. There are {npcs_desc} and {monsters_desc}."
                )
                resolved_status = "success"
            else:
                # Look for target in objects, NPCs, or monsters
                matched_obj = next((o for o in game_state.objects if target in o["name"].lower()), None)
                matched_npc = next((n for n in game_state.active_npcs if target in n["name"].lower() or target in n.get("type", "").lower()), None)
                matched_monster = next((m for m in game_state.active_monsters if target in m["name"].lower()), None)

                if matched_obj:
                    status_info = matched_obj.get("status", "present")
                    outcome = f"You inspect the {matched_obj['name']}. It is currently {status_info}."
                    resolved_status = "success"
                elif matched_npc:
                    outcome = f"You look at {matched_npc['name']}. Status: {matched_npc['status']}. HP: {matched_npc['health']}/100."
                    resolved_status = "success"
                elif matched_monster:
                    outcome = f"You inspect the {matched_monster['name']}. HP: {matched_monster['health']}/{matched_monster['max_health']}. It looks aggressive!"
                    resolved_status = "success"
                else:
                    outcome = f"There is no '{target}' here to inspect."
                    resolved_status = "rejected"

        # 2. OPEN
        elif cleaned_action.startswith("open "):
            target = cleaned_action[5:].strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            matched_obj = next((o for o in game_state.objects if target in o["name"]), None)
            if matched_obj:
                if matched_obj["type"] == "chest":
                    if matched_obj["status"] == "open":
                        outcome = f"The {matched_obj['name']} is already open."
                        resolved_status = "failed"
                    else:
                        # Open the chest
                        matched_obj["status"] = "open"
                        flag_modified(game_state, "objects")
                        
                        items_found = matched_obj.get("items", [])
                        gold_found = matched_obj.get("gold", 0)
                        
                        # Add items and gold
                        if items_found:
                            game_state.inventory["party"].extend(items_found)
                            flag_modified(game_state, "inventory")
                        character.gold += gold_found
                        
                        if matched_obj["name"] not in game_state.world_flags["opened_chests"]:
                            game_state.world_flags["opened_chests"].append(matched_obj["name"])
                            flag_modified(game_state, "world_flags")

                        resolved_status = "success"
                        outcome = f"You open the {matched_obj['name']}! Inside you find: {', '.join(items_found)} and {gold_found} gold."
                        event_type = "Item Collected"
                        event_details = {"object": matched_obj["name"], "items": items_found, "gold": gold_found}

                elif matched_obj["type"] == "gate":
                    if matched_obj["status"] == "open":
                        outcome = f"The {matched_obj['name']} is already open."
                        resolved_status = "failed"
                    else:
                        key_needed = matched_obj.get("requires")
                        if key_needed in game_state.inventory["party"]:
                            game_state.inventory["party"].remove(key_needed)
                            flag_modified(game_state, "inventory")
                            
                            matched_obj["status"] = "open"
                            flag_modified(game_state, "objects")
                            
                            if matched_obj["name"] not in game_state.world_flags["opened_chests"]:
                                game_state.world_flags["opened_chests"].append(matched_obj["name"])
                                flag_modified(game_state, "world_flags")

                            resolved_status = "success"
                            outcome = f"You unlock and open the {matched_obj['name']} using the {key_needed}! The path to {matched_obj['leads_to']} is now clear."
                            event_type = "Door Opened"
                            event_details = {"object": matched_obj["name"]}
                        else:
                            outcome = f"The {matched_obj['name']} is locked. You need a {key_needed} to open it."
                            resolved_status = "failed"
                else:
                    outcome = f"You cannot open the {matched_obj['name']}."
                    resolved_status = "rejected"
            else:
                outcome = f"There is no '{target}' here to open."
                resolved_status = "rejected"

        # 3. ATTACK / FIGHT / KILL
        elif any(cleaned_action.startswith(v) for v in ["attack ", "fight ", "kill "]):
            target = re.sub(r"^(attack|fight|kill)\s+", "", cleaned_action).strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            matched_monster = next((m for m in game_state.active_monsters if target in m["name"].lower()), None)
            matched_npc = next((n for n in game_state.active_npcs if target in n["name"].lower() or target in n.get("type", "").lower()), None)

            if matched_monster:
                # Combat round
                damage_roll = random.randint(1, 6)
                damage = max(1, character.strength + damage_roll - matched_monster["defense"])
                matched_monster["health"] -= damage
                flag_modified(game_state, "active_monsters")

                if matched_monster["health"] <= 0:
                    # Monster killed!
                    game_state.active_monsters.remove(matched_monster)
                    flag_modified(game_state, "active_monsters")
                    
                    game_state.world_flags["killed_monsters"].append(matched_monster["name"])
                    flag_modified(game_state, "world_flags")
                    
                    xp_gained = matched_monster["xp"]
                    gold_gained = matched_monster["gold"]
                    
                    character.experience += xp_gained
                    character.gold += gold_gained
                    
                    level_up_msg = ""
                    # Level up checks (100 XP per level)
                    if character.experience >= character.level * 100:
                        character.experience -= character.level * 100
                        character.level += 1
                        character.health += 20
                        character.current_health = character.health
                        character.mana += 10
                        character.current_mana = character.mana
                        character.strength += 2
                        character.defense += 1
                        level_up_msg = f" Character leveled up! {character.character_name} is now Level {character.level}!"
                        # Emit level up event
                        lvl_event = GameEvent(
                            room_id=room_id,
                            event_type="Quest Updated",  
                            details={"message": f"{character.character_name} leveled up to {character.level}!"}
                        )
                        session.add(lvl_event)

                    outcome = f"You attack the {matched_monster['name']} for {damage} damage and slay it! Gained {xp_gained} XP and {gold_gained} gold.{level_up_msg}"
                    resolved_status = "success"
                    event_type = "Item Collected"  
                    event_details = {"killed": matched_monster["name"], "xp": xp_gained, "gold": gold_gained}
                    
                    # Custom drop for goblin warrior
                    if matched_monster["name"] == "goblin warrior":
                        game_state.inventory["party"].append("king's key")
                        flag_modified(game_state, "inventory")
                        outcome += " It dropped a king's key, which was added to the party inventory."
                else:
                    outcome = f"You attack the {matched_monster['name']} for {damage} damage! (HP: {matched_monster['health']}/{matched_monster['max_health']})"
                    resolved_status = "success"
                    event_type = "Player Action Attempted"
                    event_details = {"damage_dealt": damage, "target": matched_monster["name"]}

            elif matched_npc:
                # Attack friendly NPC
                npc_name = matched_npc["name"]
                rel = game_state.world_flags["npc_relationships"].get(npc_name, 50)
                rel = max(0, rel - 20)
                game_state.world_flags["npc_relationships"][npc_name] = rel
                flag_modified(game_state, "world_flags")
                
                outcome = f"You attack {npc_name}, but they quickly block your blow! {npc_name}'s relationship drops to {rel}."
                resolved_status = "failed"
                
                if rel <= 10:
                    matched_npc["status"] = "hostile"
                    flag_modified(game_state, "active_npcs")
                    outcome += f" {npc_name} is now hostile!"
            else:
                outcome = f"There is no '{target}' here to attack."
                resolved_status = "rejected"

        # 4. TALK TO / SPEAK TO
        elif any(cleaned_action.startswith(v) for v in ["talk to ", "speak to ", "talk ", "speak "]):
            target = re.sub(r"^(talk to|speak to|talk|speak)\s+", "", cleaned_action).strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            matched_npc = next((n for n in game_state.active_npcs if target in n["name"].lower() or target in n.get("type", "").lower()), None)
            if matched_npc:
                npc_name = matched_npc["name"]
                if matched_npc.get("status") == "hostile":
                    outcome = f"{npc_name} refuses to speak with you and lunges aggressively!"
                    resolved_status = "failed"
                else:
                    outcome = f"{npc_name} says: \"{matched_npc['dialogue']}\""
                    resolved_status = "success"
                    event_type = "NPC Joined"  
                    event_details = {"npc": npc_name, "dialogue": matched_npc['dialogue']}
                    
                    # Specific interaction with injured elf Aerith
                    if npc_name == "Aerith":
                        if "health potion" in game_state.inventory["party"]:
                            outcome += " (You have a health potion! Type 'give potion to elf' to heal her.)"
            else:
                outcome = f"There is no one here named '{target}' to speak to."
                resolved_status = "rejected"

        # 5. GO TO / MOVE TO / TRAVEL TO
        elif any(cleaned_action.startswith(v) for v in ["go to ", "move to ", "travel to ", "go ", "move "]):
            target = re.sub(r"^(go to|move to|travel to|go|move)\s+", "", cleaned_action).strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            if game_state.current_location_id is not None:
                from app.models.world import Location
                all_locs = (await session.scalars(
                    select(Location).where(Location.room_id == room_id)
                )).all()
                
                dest_loc = next((l for l in all_locs if l.name.lower() == target or target in l.name.lower()), None)
                if dest_loc:
                    if dest_loc.id == game_state.current_location_id:
                        outcome = f"You are already at the {dest_loc.name}."
                        resolved_status = "failed"
                    else:
                        curr_loc = next((l for l in all_locs if l.id == game_state.current_location_id), None)
                        if curr_loc:
                            # Check connectivity
                            if str(dest_loc.id) in curr_loc.connected_locations or dest_loc.id in curr_loc.connected_locations:
                                old_loc_name = game_state.current_location
                                game_state.current_location_id = dest_loc.id
                                game_state.current_location = dest_loc.name
                                
                                # Sync environment, monsters, NPCs
                                game_state.weather = dest_loc.weather
                                game_state.active_npcs = dest_loc.npc_list
                                game_state.active_monsters = dest_loc.monster_list
                                
                                from app.models.world import WorldObject
                                loc_objects = (await session.scalars(
                                    select(WorldObject).where(WorldObject.location_id == dest_loc.id)
                                    .order_by(WorldObject.name.asc())
                                )).all()
                                game_state.objects = [
                                    {
                                        "name": o.name,
                                        "type": o.type,
                                        "status": o.status,
                                        "details": o.details
                                    } for o in loc_objects
                                ]
                                
                                if dest_loc.name not in game_state.world_flags["visited_locations"]:
                                    game_state.world_flags["visited_locations"].append(dest_loc.name)
                                flag_modified(game_state, "world_flags")
                                flag_modified(game_state, "active_npcs")
                                flag_modified(game_state, "active_monsters")
                                flag_modified(game_state, "objects")
                                
                                resolved_status = "success"
                                outcome = f"You travel to the {dest_loc.name}."
                                event_type = "Player Moved"
                                event_details = {"from": old_loc_name, "to": dest_loc.name}
                            else:
                                outcome = f"Move failed: {dest_loc.name} is not connected to your current location."
                                resolved_status = "failed"
                        else:
                            outcome = "Move failed: current location coordinate state invalid."
                            resolved_status = "failed"
                else:
                    outcome = f"I don't know of a location named '{target}'."
                    resolved_status = "rejected"
            else:
                # Map inputs to standard room names
                dest = None
                if "entrance" in target or "dungeon entrance" in target:
                    dest = "Dungeon Entrance"
                elif "camp" in target or "goblin camp" in target:
                    dest = "Goblin Camp"
                elif "cave" in target or "hidden cave" in target:
                    dest = "Hidden Cave"
                elif "chamber" in target or "treasure chamber" in target:
                    dest = "Treasure Chamber"

                if dest:
                    if dest == game_state.current_location:
                        outcome = f"You are already at the {dest}."
                        resolved_status = "failed"
                    else:
                        allowed = False
                        reason = ""
                        
                        if game_state.current_location == "Dungeon Entrance":
                            if dest == "Goblin Camp":
                                # Check stone gate status
                                gate_obj = next((o for o in game_state.objects if o["name"] == "stone gate"), None)
                                if gate_obj and gate_obj["status"] == "open":
                                    allowed = True
                                else:
                                    reason = "The massive stone gate is locked and blocks the path."
                            elif dest == "Hidden Cave":
                                # Check crumbly wall status
                                wall_obj = next((o for o in game_state.objects if o["name"] == "crumbly wall"), None)
                                if wall_obj and wall_obj["status"] == "destroyed":
                                    allowed = True
                                else:
                                    reason = "A solid crumbling wall blocks the hidden passage."
                            else:
                                reason = f"You cannot travel directly to {dest} from here."
                                
                        elif game_state.current_location == "Goblin Camp":
                            if dest == "Dungeon Entrance":
                                allowed = True
                            elif dest == "Treasure Chamber":
                                # Check if monsters are still present
                                if game_state.active_monsters:
                                    reason = f"A hostile {game_state.active_monsters[0]['name']} blocks the entrance to the Treasure Chamber!"
                                else:
                                    allowed = True
                            else:
                                reason = f"You cannot travel directly to {dest} from here."

                        elif game_state.current_location == "Hidden Cave":
                            if dest == "Dungeon Entrance":
                                allowed = True
                            else:
                                reason = f"You cannot travel directly to {dest} from here."

                        elif game_state.current_location == "Treasure Chamber":
                            if dest == "Goblin Camp":
                                allowed = True
                            else:
                                reason = f"You cannot travel directly to {dest} from here."

                        if allowed:
                            old_loc = game_state.current_location
                            game_state.current_location = dest
                            if dest not in game_state.world_flags["visited_locations"]:
                                game_state.world_flags["visited_locations"].append(dest)
                            flag_modified(game_state, "world_flags")

                            # Load objects/monsters for the new room
                            GameEngine._load_location_details(game_state, dest)

                            resolved_status = "success"
                            outcome = f"You travel to the {dest}."
                            event_type = "Player Moved"
                            event_details = {"from": old_loc, "to": dest}
                        else:
                            outcome = f"Move failed: {reason}"
                            resolved_status = "failed"
                else:
                    outcome = f"I don't know how to get to '{target}'."
                    resolved_status = "rejected"

        # 6. DESTROY / BREAK / SMASH
        elif any(cleaned_action.startswith(v) for v in ["destroy ", "break ", "smash "]):
            target = re.sub(r"^(destroy|break|smash)\s+", "", cleaned_action).strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            matched_obj = next((o for o in game_state.objects if target in o["name"]), None)
            if matched_obj:
                if matched_obj["name"] == "crumbly wall":
                    if matched_obj["status"] == "destroyed":
                        outcome = "The crumbly wall has already been smashed to bits."
                        resolved_status = "failed"
                    else:
                        matched_obj["status"] = "destroyed"
                        flag_modified(game_state, "objects")
                        
                        game_state.world_flags["destroyed_objects"].append(matched_obj["name"])
                        flag_modified(game_state, "world_flags")
                        
                        resolved_status = "success"
                        outcome = "You summon your strength and smash the crumbly wall into pieces, revealing a hidden passage to the Hidden Cave!"
                        event_type = "Door Opened"  
                        event_details = {"object": "crumbly wall"}
                else:
                    outcome = f"You cannot destroy the {matched_obj['name']}."
                    resolved_status = "failed"
            else:
                outcome = f"There is no '{target}' here to destroy."
                resolved_status = "rejected"

        # 7. USE / DRINK / GIVE
        elif any(cleaned_action.startswith(v) for v in ["use ", "drink ", "give ", "equip "]):
            target = re.sub(r"^(use|drink|give|equip)\s+", "", cleaned_action).strip()
            target = re.sub(r"^(the|a|an)\s+", "", target)

            if "potion" in target or "health potion" in target:
                if "health potion" in game_state.inventory["party"]:
                    game_state.inventory["party"].remove("health potion")
                    flag_modified(game_state, "inventory")
                    
                    old_hp = character.current_health
                    character.current_health = min(character.health, character.current_health + 50)
                    healed = character.current_health - old_hp
                    
                    resolved_status = "success"
                    outcome = f"You drink a health potion, restoring {healed} HP! (HP: {character.current_health}/{character.health})"
                    event_type = "Item Collected"  
                    event_details = {"item": "health potion", "recipient": character.character_name, "healed": healed}
                else:
                    outcome = "The party does not have any health potions left."
                    resolved_status = "failed"

            elif "spring" in target or "healing spring" in target:
                spring_obj = next((o for o in game_state.objects if o["name"] == "healing spring"), None)
                if spring_obj and game_state.current_location == "Hidden Cave":
                    character.current_health = character.health
                    character.current_mana = character.mana
                    resolved_status = "success"
                    outcome = "You drink from the crystal-clear healing spring. Your Health and Mana are completely restored!"
                    event_type = "Item Collected"
                    event_details = {"item": "healing spring", "recipient": character.character_name}
                else:
                    outcome = "There is no healing spring here."
                    resolved_status = "rejected"

            elif "sword" in target or "steel sword" in target:
                if "steel sword" in game_state.inventory["party"]:
                    character.strength += 4
                    game_state.inventory["party"].remove("steel sword")
                    flag_modified(game_state, "inventory")
                    
                    resolved_status = "success"
                    outcome = f"You equip the steel sword. Your strength increases by 4! (Strength: {character.strength})"
                else:
                    outcome = "You don't have a steel sword."
                    resolved_status = "failed"

            elif "shield" in target or "iron shield" in target:
                if "iron shield" in game_state.inventory["party"]:
                    character.defense += 3
                    game_state.inventory["party"].remove("iron shield")
                    flag_modified(game_state, "inventory")
                    
                    resolved_status = "success"
                    outcome = f"You equip the iron shield. Your defense increases by 3! (Defense: {character.defense})"
                else:
                    outcome = "You don't have an iron shield."
                    resolved_status = "failed"

            elif "potion to elf" in target or "potion to aerith" in target or "health potion to aerith" in target or "health potion to elf" in target:
                if game_state.current_location == "Hidden Cave":
                    matched_elf = next((n for n in game_state.active_npcs if n["name"] == "Aerith"), None)
                    if matched_elf:
                        if "health potion" in game_state.inventory["party"]:
                            game_state.inventory["party"].remove("health potion")
                            game_state.inventory["party"].append("amulet of protection")
                            flag_modified(game_state, "inventory")
                            
                            game_state.active_npcs.remove(matched_elf)
                            flag_modified(game_state, "active_npcs")
                            
                            game_state.world_flags["completed_quests"].append("Helped Aerith")
                            flag_modified(game_state, "world_flags")

                            resolved_status = "success"
                            outcome = (
                                "You offer a health potion to Aerith. She drinks it eagerly. "
                                "She stands up and breathes a sigh of relief: 'Thank you! You saved me. "
                                "Please take this Amulet of Protection as a token of my thanks.' "
                                "An amulet of protection (+5 defense when equipped) has been added to your inventory."
                            )
                            event_type = "NPC Joined"  
                            event_details = {"npc": "Aerith", "reward": "amulet of protection"}
                        else:
                            outcome = "You do not have a health potion to give."
                            resolved_status = "failed"
                    else:
                        outcome = "Aerith is not here."
                        resolved_status = "failed"
                else:
                    outcome = "There is no elf here to give a potion to."
                    resolved_status = "failed"

            elif "amulet" in target or "amulet of protection" in target:
                if "amulet of protection" in game_state.inventory["party"]:
                    character.defense += 5
                    game_state.inventory["party"].remove("amulet of protection")
                    flag_modified(game_state, "inventory")
                    
                    resolved_status = "success"
                    outcome = f"You wear the amulet of protection. Your defense increases by 5! (Defense: {character.defense})"
                else:
                    outcome = "You don't have an amulet of protection."
                    resolved_status = "failed"
            else:
                outcome = f"I don't know how to use '{target}'."
                resolved_status = "rejected"

        elif cleaned_action == "revive":
            character.current_health = character.health
            resolved_status = "success"
            outcome = f"{character.character_name} has been revived and healed to full!"
            event_type = "Player Action Attempted"
            event_details = {"cheat": "revive"}

        # ----------------------------------------------------
        # RESOLUTION AND TURN STATE MACHINE
        # ----------------------------------------------------

        db_action = PlayerAction(
            room_id=room_id,
            user_id=user_id,
            action_text=action_text,
            resolved_status=resolved_status,
            outcome=outcome,
        )
        session.add(db_action)

        # Find the username of the user performing the action
        player_username = "Player"
        for p in room.players:
            if p.user_id == user_id:
                player_username = p.user.username
                break

        await notify_player_action(
            room_code,
            {
                "username": player_username,
                "character_name": character.character_name,
                "action_text": action_text,
                "resolved_status": resolved_status,
                "outcome": outcome,
            },
        )

        if resolved_status in ["success", "failed"]:
            if event_type != "Player Action Attempted" or event_details:
                action_event = GameEvent(
                    room_id=room_id,
                    event_type=event_type,
                    details=event_details
                )
                session.add(action_event)
                await notify_event_created(room_code, {"event_type": event_type, "details": event_details})

            # --- PHASE 2: ENEMY TURN ---
            game_state.turn_stage = "enemy"
            enemy_outcomes = []
            
            if game_state.active_monsters:
                monster = game_state.active_monsters[0] 
                monster_damage = max(1, monster["damage"] - character.defense)
                character.current_health = max(0, character.current_health - monster_damage)
                
                enemy_outcomes.append(
                    f"The {monster['name']} retaliates and attacks {character.character_name} for {monster_damage} damage!"
                )
                
                if character.current_health <= 0:
                    enemy_outcomes.append(f"☠ {character.character_name} has fallen in battle!")
                    death_event = GameEvent(
                        room_id=room_id,
                        event_type="Player Died",
                        details={"character": character.character_name, "slain_by": monster["name"]}
                    )
                    session.add(death_event)
                    await notify_event_created(room_code, {"event_type": "Player Died", "details": {"character": character.character_name, "slain_by": monster["name"]}})
                
                combat_event = GameEvent(
                    room_id=room_id,
                    event_type="Combat Started", 
                    details={"attacker": monster["name"], "damage": monster_damage, "target": character.character_name}
                )
                session.add(combat_event)
                await notify_event_created(
                    room_code, 
                    {"event_type": "Combat Started", "details": {"attacker": monster["name"], "damage": monster_damage, "target": character.character_name}}
                )
                await notify_combat_started(room_code, {"attacker": monster["name"], "damage": monster_damage, "target": character.character_name})

            # --- PHASE 3: WORLD TURN ---
            game_state.turn_stage = "world"
            world_outcomes = []
            
            weathers = ["Clear", "Foggy", "Rainy", "Stormy"]
            if random.random() < 0.3: 
                game_state.weather = random.choice(weathers)
                world_outcomes.append(f"The weather changes. It is now {game_state.weather}.")

            current_day_str = game_state.current_time.split(" - ")[0]
            current_time_str = game_state.current_time.split(" - ")[1]
            day_num = int(current_day_str.split(" ")[1])
            
            times = ["Morning", "Afternoon", "Night"]
            next_idx = (times.index(current_time_str) + 1) % len(times)
            if next_idx == 0:
                day_num += 1
            
            game_state.current_time = f"Day {day_num} - {times[next_idx]}"
            world_outcomes.append(f"Time progresses to {game_state.current_time}.")

            old_quest = game_state.current_quest
            new_quest = old_quest
            
            if old_quest == "Open the Stone Gate":
                gate_obj = next((o for o in game_state.objects if o["name"] == "stone gate"), None)
                if gate_obj and gate_obj["status"] == "open":
                    new_quest = "Defeat the Goblin Warrior and proceed to the Treasure Chamber"
            elif old_quest == "Defeat the Goblin Warrior and proceed to the Treasure Chamber":
                if "goblin warrior" in game_state.world_flags["killed_monsters"]:
                    new_quest = "Defeat the Goblin King and retrieve the Holy Grail"
            elif old_quest == "Defeat the Goblin King and retrieve the Holy Grail":
                if "goblin king" in game_state.world_flags["killed_monsters"]:
                    new_quest = "Retrieve the Holy Grail from the Golden Chest"
            elif old_quest == "Retrieve the Holy Grail from the Golden Chest":
                if "Holy Grail" in game_state.inventory["party"]:
                    new_quest = "Escape the Dungeon with the Holy Grail (Go back to Dungeon Entrance)"
            elif old_quest == "Escape the Dungeon with the Holy Grail (Go back to Dungeon Entrance)":
                if game_state.current_location == "Dungeon Entrance":
                    new_quest = "Dungeon Escaped! You have won the game!"

            if new_quest != old_quest:
                game_state.current_quest = new_quest
                world_outcomes.append(f"Quest updated: {new_quest}")
                quest_event = GameEvent(
                    room_id=room_id,
                    event_type="Quest Updated",
                    details={"new_quest": new_quest}
                )
                session.add(quest_event)
                await notify_quest_updated(room_code, {"quest": new_quest})



            # --- PHASE 4: PLAYER TURN RESET ---
            game_state.turn_stage = "player"
            game_state.turn_index += 1

            await session.commit()

            state_data = {
                "current_location": game_state.current_location,
                "current_time": game_state.current_time,
                "weather": game_state.weather,
                "current_quest": game_state.current_quest,
                "active_npcs": game_state.active_npcs,
                "active_monsters": game_state.active_monsters,
                "objects": game_state.objects,
                "turn_index": game_state.turn_index,
                "turn_stage": game_state.turn_stage,
            }
            await notify_world_updated(room_code, state_data)
            await notify_inventory_updated(room_code, game_state.inventory)
        
        else:
            await session.commit()

        return game_state

    @staticmethod
    def _load_location_details(game_state: GameState, location: str) -> None:
        if location == "Dungeon Entrance":
            game_state.active_npcs = [
                {
                    "name": "Elidor",
                    "type": "wizard",
                    "health": 100,
                    "status": "friendly",
                    "dialogue": "Beware the stone gate! You'll need a key from the wooden chest to open it. Or perhaps you can find another way..."
                }
            ]
            if "small goblin" not in game_state.world_flags["killed_monsters"]:
                game_state.active_monsters = [
                    {
                        "name": "small goblin",
                        "health": 30,
                        "max_health": 30,
                        "damage": 8,
                        "defense": 2,
                        "xp": 50,
                        "gold": 20
                    }
                ]
            else:
                game_state.active_monsters = []
            
            gate_status = "open" if "stone gate" in game_state.world_flags["opened_chests"] else "locked"
            wall_status = "destroyed" if "crumbly wall" in game_state.world_flags["destroyed_objects"] else "intact"
            chest_status = "open" if "wooden chest" in game_state.world_flags["opened_chests"] else "closed"

            game_state.objects = [
                {
                    "name": "wooden chest",
                    "type": "chest",
                    "status": chest_status,
                    "items": [] if chest_status == "open" else ["iron key", "health potion"],
                    "gold": 0 if chest_status == "open" else 50
                },
                {
                    "name": "stone gate",
                    "type": "gate",
                    "status": gate_status,
                    "requires": "iron key",
                    "leads_to": "Goblin Camp"
                },
                {
                    "name": "crumbly wall",
                    "type": "wall",
                    "status": wall_status,
                    "leads_to": "Hidden Cave"
                }
            ]

        elif location == "Goblin Camp":
            game_state.active_npcs = []
            if "goblin warrior" not in game_state.world_flags["killed_monsters"]:
                game_state.active_monsters = [
                    {
                        "name": "goblin warrior",
                        "health": 50,
                        "max_health": 50,
                        "damage": 12,
                        "defense": 4,
                        "xp": 100,
                        "gold": 40
                    }
                ]
            else:
                game_state.active_monsters = []

            rack_status = "open" if "weapon rack" in game_state.world_flags["opened_chests"] else "intact"
            game_state.objects = [
                {
                    "name": "weapon rack",
                    "type": "chest",
                    "status": rack_status,
                    "items": [] if rack_status == "open" else ["steel sword", "iron shield"],
                    "gold": 0
                }
            ]

        elif location == "Hidden Cave":
            if "Helped Aerith" not in game_state.world_flags["completed_quests"]:
                game_state.active_npcs = [
                    {
                        "name": "Aerith",
                        "type": "elf",
                        "health": 40,
                        "status": "friendly",
                        "dialogue": "Please help me! If you have a health potion, I will reward you with a magical amulet of protection."
                    }
                ]
            else:
                game_state.active_npcs = []
            game_state.active_monsters = []
            game_state.objects = [
                {
                    "name": "healing spring",
                    "type": "usable",
                    "status": "active"
                }
            ]

        elif location == "Treasure Chamber":
            game_state.active_npcs = []
            if "goblin king" not in game_state.world_flags["killed_monsters"]:
                game_state.active_monsters = [
                    {
                        "name": "goblin king",
                        "health": 100,
                        "max_health": 100,
                        "damage": 18,
                        "defense": 6,
                        "xp": 300,
                        "gold": 200
                    }
                ]
            else:
                game_state.active_monsters = []
            
            chest_status = "open" if "golden chest" in game_state.world_flags["opened_chests"] else "locked"
            game_state.objects = [
                {
                    "name": "golden chest",
                    "type": "chest",
                    "status": chest_status,
                    "requires": "king's key",
                    "items": [] if chest_status == "open" else ["Holy Grail"],
                    "gold": 0 if chest_status == "open" else 500
                }
            ]

        flag_modified(game_state, "active_npcs")
        flag_modified(game_state, "active_monsters")
        flag_modified(game_state, "objects")
