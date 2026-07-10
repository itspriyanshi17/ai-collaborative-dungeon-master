from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.world import Biome, Region, Location, Building, WorldObject
from app.models.npc import NPC


class WorldGenerator:
    @staticmethod
    async def generate_world(session: AsyncSession, room_id: UUID) -> tuple[Location, list[Location]]:
        # 1. Seed Biomes if they do not exist
        biomes_to_seed = [
            ("Plains", "Flat grasslands and gentle valleys, ideal for settlements."),
            ("Forest", "Dense woodlands filled with towering trees and hidden shadows."),
            ("River", "Flowing watercourses, wetlands, and aquatic creatures."),
            ("Mountain", "Rugged cliffs, freezing peaks, and vertical passes."),
            ("Dungeon", "Subterranean crypts, caves, and ancient underground vaults."),
            ("Castle", "Gothic fortresses, keeps, and stone castles.")
        ]
        
        biome_map = {}
        for name, desc in biomes_to_seed:
            existing = await session.scalar(
                select(Biome).where(Biome.name == name)
            )
            if not existing:
                existing = Biome(name=name, description=desc)
                session.add(existing)
                await session.flush()
            biome_map[name] = existing

        # 2. Create the Region for this Room
        region = Region(
            room_id=room_id,
            name="The Forgotten Vale",
            description="A secluded valley forgotten by mapmakers, harboring ancient secrets."
        )
        session.add(region)
        await session.flush()

        # 3. Create Locations (Temporary variables to map connections later)
        # Village
        village = Location(
            room_id=room_id,
            region_id=region.id,
            biome_id=biome_map["Plains"].id,
            name="Stoneford Village",
            description="A peaceful village built next to a river crossing. Safe but filled with rumors.",
            biome="Plains",
            connected_locations=[],
            npc_list=[
                {"name": "Elder Jonas", "dialogue": "Travelers! Beware the Whispering Forest to our north. Shadows walk there."}
            ],
            monster_list=[],
            loot_table={"gold": 0, "items": []},
            weather="Clear",
            danger_level=0
        )
        
        # Forest
        forest = Location(
            room_id=room_id,
            region_id=region.id,
            biome_id=biome_map["Forest"].id,
            name="Whispering Forest",
            description="A dense canopy where the wind sounds like whispered warnings. Hostile creatures lurk here.",
            biome="Forest",
            connected_locations=[],
            npc_list=[],
            monster_list=[
                {
                    "name": "gnoll hunter",
                    "health": 35,
                    "max_health": 35,
                    "damage": 10,
                    "defense": 2,
                    "xp": 60,
                    "gold": 25
                }
            ],
            loot_table={"gold": 15, "items": ["healing herb"]},
            weather="Foggy",
            danger_level=1
        )
        
        # River
        river = Location(
            room_id=room_id,
            region_id=region.id,
            biome_id=biome_map["River"].id,
            name="Silver River",
            description="The sparkling waters of the Silver River. Strong currents and water elementals block passage.",
            biome="River",
            connected_locations=[],
            npc_list=[],
            monster_list=[
                {
                    "name": "water elemental",
                    "health": 45,
                    "max_health": 45,
                    "damage": 12,
                    "defense": 4,
                    "xp": 90,
                    "gold": 30
                }
            ],
            loot_table={"gold": 20, "items": ["mana potion"]},
            weather="Rainy",
            danger_level=2
        )
        
        # Mountain
        mountain = Location(
            room_id=room_id,
            region_id=region.id,
            biome_id=biome_map["Mountain"].id,
            name="Spine Mountain",
            description="A treacherous, rocky path heading high into the snowline. Mountain trolls patrol the heights.",
            biome="Mountain",
            connected_locations=[],
            npc_list=[],
            monster_list=[
                {
                    "name": "mountain troll",
                    "health": 65,
                    "max_health": 65,
                    "damage": 15,
                    "defense": 5,
                    "xp": 150,
                    "gold": 60
                }
            ],
            loot_table={"gold": 40, "items": ["steel sword"]},
            weather="Stormy",
            danger_level=3
        )
        
        # Dungeon
        dungeon = Location(
            room_id=room_id,
            region_id=region.id,
            biome_id=biome_map["Dungeon"].id,
            name="Cryptic Dungeon",
            description="A dark, subterranean crypt full of dust, cobwebs, and undead mages searching for runic keys.",
            biome="Dungeon",
            connected_locations=[],
            npc_list=[],
            monster_list=[
                {
                    "name": "skeletal mage",
                    "health": 55,
                    "max_health": 55,
                    "damage": 16,
                    "defense": 3,
                    "xp": 180,
                    "gold": 80
                }
            ],
            loot_table={"gold": 100, "items": ["crypt key"]},
            weather="Foggy",
            danger_level=4
        )
        
        # Castle
        castle = Location(
            room_id=room_id,
            region_id=region.id,
            biome_id=biome_map["Castle"].id,
            name="Shadowfang Castle",
            description="A towering, dark stone castle overlooking the vale. A vampire lord rules from his throne room.",
            biome="Castle",
            connected_locations=[],
            npc_list=[],
            monster_list=[
                {
                    "name": "vampire lord",
                    "health": 110,
                    "max_health": 110,
                    "damage": 22,
                    "defense": 6,
                    "xp": 350,
                    "gold": 250
                }
            ],
            loot_table={"gold": 300, "items": ["Holy Grail"]},
            weather="Stormy",
            danger_level=5
        )
        
        session.add_all([village, forest, river, mountain, dungeon, castle])
        await session.flush()

        # 4. Set connections (Use UUID strings)
        village.connected_locations = [str(forest.id), str(mountain.id)]
        forest.connected_locations = [str(village.id), str(river.id), str(castle.id)]
        river.connected_locations = [str(forest.id), str(dungeon.id)]
        mountain.connected_locations = [str(village.id)]
        dungeon.connected_locations = [str(river.id)]
        castle.connected_locations = [str(forest.id)]

        # 5. Seed Dynamic NPCs in Database
        ted = NPC(
            room_id=room_id,
            location_id=village.id,
            name="Barman Ted",
            race="Human",
            profession="Barman",
            personality="Gruff, friendly, talkative about rumors",
            mood="Tired",
            inventory={"mead": 5, "ale": 10},
            relationships={},
            daily_schedule="Morning: Stocking ale at the cellar, Afternoon/Night: Tending the bar at The Rusty Anchor Tavern",
            goals="Keep the tavern running, hear all gossip in the valley"
        )
        
        alaric = NPC(
            room_id=room_id,
            location_id=village.id,
            name="Merchant Alaric",
            race="Dwarf",
            profession="Merchant",
            personality="Jolly, shrewd, likes hard bargaining",
            mood="Happy",
            inventory={"health potion": 3, "mana potion": 3},
            relationships={},
            daily_schedule="Morning/Afternoon: Running the merchant stall in the market square, Night: Drinking at the tavern",
            goals="Earn gold, buy rare artifacts from adventurers"
        )
        
        alara = NPC(
            room_id=room_id,
            location_id=village.id,
            name="Priestess Alara",
            race="Elf",
            profession="Priestess",
            personality="Peaceful, soft-spoken, spiritual",
            mood="Peaceful",
            inventory={"holy water": 2},
            relationships={},
            daily_schedule="Morning: Prayers at the altar, Afternoon: Guiding villagers, Night: Studying ancient texts",
            goals="Promote light and healing, cleanse dungeon evil"
        )
        
        elidor = NPC(
            room_id=room_id,
            location_id=village.id,
            name="Wizard Elidor",
            race="Human",
            profession="Wizard",
            personality="Wise, cryptic, secretive about magic",
            mood="Suspicious",
            inventory={"magic scroll": 1},
            relationships={},
            daily_schedule="Morning: Reading in the tower, Afternoon: Walking near the stone gate, Night: Observing the stars",
            goals="Research the ancient seals, guide chosen heroes"
        )
        
        aerith = NPC(
            room_id=room_id,
            location_id=forest.id,
            name="Herbalist Aerith",
            race="Elf",
            profession="Herbalist",
            personality="Gentle, nervous, desperately helpful",
            mood="Anxious",
            inventory={"healing herb": 4, "elixir": 1},
            relationships={},
            daily_schedule="Morning: Gathering herbs in the forest, Afternoon/Night: Hiding in the forest camp",
            goals="Survival, reward brave heroes who heal her wounds"
        )

        session.add_all([ted, alaric, alara, elidor, aerith])

        # 6. Populate Buildings inside Village
        merchant_shop = Building(
            location_id=village.id,
            name="Wandering Merchant's Guild",
            type="shop",
            description="A small wooden store selling potions and simple gear.",
            npc_list=[{"name": "Merchant Alaric", "dialogue": "Looking to buy? I have the finest potions in the vale!"}],
            inventory={
                "items": ["health potion", "mana potion"],
                "prices": {"health potion": 25, "mana potion": 25}
            }
        )
        
        tavern = Building(
            location_id=village.id,
            name="The Rusty Anchor Tavern",
            type="tavern",
            description="A cozy, bustling tavern offering warm fire, food, and rumors.",
            npc_list=[
                {"name": "Barman Ted", "dialogue": "Welcome to the Rusty Anchor! Watch out for the trolls up on Spine Mountain."},
                {"name": "Bard Elidor", "dialogue": "They say the skeletal mages in the Cryptic Dungeon hold a key to Shadowfang Castle."}
            ],
            inventory={"drinks": ["dwarven ale", "mead"], "prices": {"dwarven ale": 5, "mead": 8}}
        )
        
        temple = Building(
            location_id=village.id,
            name="Plains Altar Temple",
            type="temple",
            description="A serene temple offering healing and respite for weary adventurers.",
            npc_list=[{"name": "Priestess Alara", "dialogue": "May the light bless your path. Rest here and heal your wounds."}],
            inventory={"blessings": ["heal"], "prices": {"heal": 10}}
        )

        session.add_all([merchant_shop, tavern, temple])

        # 7. Populate Objects in Dungeon & Forest
        dungeon_gate = WorldObject(
            location_id=dungeon.id,
            name="iron gate",
            type="gate",
            status="locked",
            details={"requires": "crypt key"}
        )
        
        forest_chest = WorldObject(
            location_id=forest.id,
            name="moldy chest",
            type="chest",
            status="closed",
            details={"items": ["health potion"], "gold": 20}
        )
        
        session.add_all([dungeon_gate, forest_chest])
        await session.flush()

        return village, [village, forest, river, mountain, dungeon, castle]
