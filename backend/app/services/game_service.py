from app.ai.prompt_builder import DungeonMasterPrompt


class GameService:
    def build_action_prompt(self, world_state: str, player_actions: list[str]) -> str:
        return DungeonMasterPrompt(world_state=world_state, player_actions=player_actions).render()
