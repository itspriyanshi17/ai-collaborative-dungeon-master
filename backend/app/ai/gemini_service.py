import json
import logging
import asyncio
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


class AIDungeonMasterResponse(BaseModel):
    story: str = Field(..., description="The story narration detailing what happens next based on the player's action and engine outcome.")
    npc_dialogue: list[str] = Field(default_factory=list, description="A list of spoken dialogues from NPCs present in the scene, if any.")
    next_events: list[str] = Field(default_factory=list, description="Suggested next events or hooks for the players.")
    atmosphere: str = Field(..., description="Description of the current atmosphere/ambient environment.")
    suggested_music: str = Field(..., description="Suggested background track description to match the mood.")


class GeminiService:
    _client = None

    @classmethod
    def get_client(cls) -> genai.Client:
        if cls._client is None:
            cls._client = genai.Client(api_key=settings.gemini_api_key)
        return cls._client

    @classmethod
    async def generate_narration(cls, prompt_text: str, fallback_outcome: str) -> AIDungeonMasterResponse:
        client = cls.get_client()

        # Retry once if Gemini fails
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=prompt_text,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=AIDungeonMasterResponse,
                            temperature=0.7,
                        ),
                    )
                )
                
                if not response.text:
                    raise ValueError("Empty response text from Gemini API.")
                
                # Validate the JSON matches the Pydantic schema
                parsed_response = AIDungeonMasterResponse.model_validate_json(response.text)
                return parsed_response

            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.error("All Gemini API attempts failed. Falling back to local narration.")
                    break
                # Wait briefly before retry
                await asyncio.sleep(1)

        # Fallback response
        return AIDungeonMasterResponse(
            story=f"The narrative unfolds. {fallback_outcome}",
            npc_dialogue=[],
            next_events=[],
            atmosphere="Tense, quiet, mysterious",
            suggested_music="Ambient Dungeon Theme"
        )
