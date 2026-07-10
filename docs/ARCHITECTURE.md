# Architecture

The application is split into a Next.js frontend and a FastAPI backend. The backend owns authentication, game state, AI orchestration, persistence, and real-time event fanout. The frontend owns player-facing room, character, story, chat, inventory, quest, and combat experiences.

## Backend Layers

- `api`: HTTP route modules grouped by product area.
- `models`: SQLAlchemy ORM entities.
- `schemas`: Pydantic request and response contracts.
- `services`: business workflows such as room membership, authentication, inventory, and quests.
- `ai`: prompt construction, Gemini client integration, and AI response parsing.
- `game_engine`: deterministic game rules around action batching, combat, rewards, and world-state transitions.
- `socket`: Socket.IO server and event handlers.
- `database`: engine, sessions, migrations, and base metadata.
- `utils`: cross-cutting helpers for security, validation, and rate limiting.

## Frontend Layers

- `app`: Next.js routes and providers.
- `components`: reusable UI and domain components.
- `hooks`: client-side reusable behavior.
- `lib`: shared utilities and framework adapters.
- `services`: typed API clients.
- `socket`: Socket.IO client lifecycle.
- `types`: shared frontend domain types.

## Phase Order

1. Project setup
2. Authentication
3. Database
4. Room system
5. Real-time multiplayer
6. Character creation
7. Story UI
8. Gemini integration
9. World state
10. Combat
11. Inventory
12. NPC system
13. Quest system
14. Testing
15. Deployment
