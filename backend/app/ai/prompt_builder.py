from dataclasses import dataclass
from typing import Any


@dataclass
class DungeonMasterPrompt:
    current_location: str
    current_time: str
    weather: str
    current_quest: str
    active_npcs: list[dict]
    active_monsters: list[dict]
    objects: list[dict]
    inventory: dict
    world_flags: dict
    players: list[dict]  # List of {"name": name, "class": class, "level": level, "hp": hp, "max_hp": max_hp, "mana": mana, "max_mana": max_mana}
    last_action: str
    action_outcome: str
    recent_events: list[dict]
    story_history: list[str]

    def render(self) -> str:
        players_str = "\n".join(
            f"- {p['name']} ({p['class']}, Level {p['level']}): HP {p['hp']}/{p['max_hp']}, MP {p['mana']}/{p['max_mana']}"
            for p in self.players
        )
        npcs_str = "\n".join(
            f"- {n['name']} ({n.get('type', 'NPC')}): Status: {n.get('status', 'Neutral')}, HP: {n.get('health', 100)}/100. Dialogue clue: \"{n.get('dialogue', '')}\""
            for n in self.active_npcs
        ) if self.active_npcs else "No active NPCs in this location."
        
        monsters_str = "\n".join(
            f"- {m['name']}: HP {m['health']}/{m['max_health']}, Damage: {m['damage']}, Defense: {m['defense']}"
            for m in self.active_monsters
        ) if self.active_monsters else "No active monsters in this location."
        
        objects_str = "\n".join(
            f"- {o['name']} ({o.get('type', 'Object')}): Status: {o.get('status', 'Neutral')}"
            for o in self.objects
        ) if self.objects else "No active objects in this location."

        recent_events_str = "\n".join(
            f"- Event: {e['event_type']} | Details: {e['details']}"
            for e in self.recent_events
        ) if self.recent_events else "No recent events."

        history_str = "\n".join(
            f"Event {idx+1}: {entry}" for idx, entry in enumerate(self.story_history)
        ) if self.story_history else "No prior history."

        party_inv = ", ".join(self.inventory.get("party", [])) if self.inventory.get("party") else "Empty"

        return f"""You are the AI Dungeon Master for a collaborative fantasy text-adventure game.
Your role is strictly to narrate the outcome of player actions, describe the environment/weather changes, write NPC dialogue, and depict combat rounds.

CRITICAL INSTRUCTIONS:
1. DO NOT CALCULATE GAME RULES, DAMAGE, OR HEALTH CHANGES. The game engine has already processed the action and calculated the outcome.
2. DO NOT MODIFY INVENTORY or grant items.
3. Simply NARRATE the outcome and expansion of the story based on the provided engine outcome.
4. Your story narration must be immersive, rich, descriptive, and highly engaging.

=== CONTEXT ===
Current Location: {self.current_location}
Current Time: {self.current_time}
Current Weather: {self.weather}
Current Quest: {self.current_quest}

Active Players:
{players_str}

Party Inventory:
{party_inv}

Active NPCs:
{npcs_str}

Active Monsters:
{monsters_str}

Objects in Area:
{objects_str}

World Flags & History:
- Visited Places: {self.world_flags.get('visited_locations', [])}
- Completed Quests: {self.world_flags.get('completed_quests', [])}
- NPC Relationships: {self.world_flags.get('npc_relationships', {})}

Recent System Events:
{recent_events_str}

Recent Story Memory (Last 10-20 Events):
{history_str}

=== LAST ACTION RESOLVED BY GAME ENGINE ===
Player action request: "{self.last_action}"
Engine Outcome: {self.action_outcome}

Generate the next narration based on the Engine Outcome. Ensure the narration fits the story memory, weather transitions, and room descriptions.
"""
