# AI Collaborative Dungeon Master

A production-ready, real-time multiplayer storytelling game powered by an AI Dungeon Master (Google Gemini).

## Features

- **Real-Time Multiplayer:** Built on Socket.IO for seamless synchronized gameplay, waiting rooms, and turn-based interactions.
- **AI Dungeon Master:** Employs the Google Gemini API to narrate adventures, generate dynamic dialogue, and respond logically to player actions.
- **Procedural World Generation:** Unique worlds featuring biomes, locations, and NPCs generated dynamically per session.
- **Modern Tech Stack:** 
  - **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, shadcn-ui, TanStack Query.
  - **Backend:** FastAPI, Python, SQLAlchemy, Alembic, Socket.IO.
- **Security & Persistence:** JWT Authentication and robust PostgreSQL/SQLite database persistence.

## Local Development Setup

### 1. Repository Setup

```bash
# Install node dependencies
npm install
```

### 2. Environment Variables

Create `.env` files in both the frontend and backend directories:
- Copy `frontend/.env.example` to `frontend/.env.local`
- Copy `backend/.env.example` to `backend/.env`
- Make sure to add your Google Gemini API key inside the backend `.env`.

### 3. Start Development Servers

Run the full stack concurrently from the root:
```bash
npm run dev
```

Alternatively, you can run them separately:
**Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:socket_app --reload --port 8000
```
**Frontend:**
```bash
cd frontend
npm run dev
```

## E2E Testing
Run the comprehensive Playwright end-to-end tests:
```bash
npm run dev # Start servers first
node playwright_e2e.js
```
