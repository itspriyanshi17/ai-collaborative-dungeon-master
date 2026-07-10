# Deployment Notes

## Frontend

Deploy `frontend/` to Vercel.

Required environment variables:

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_SOCKET_URL`

## Backend

Deploy `backend/` to Render.

Required environment variables:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `GEMINI_API_KEY`
- `ALLOWED_ORIGINS`

## Database

Use Supabase PostgreSQL. Run Alembic migrations from the backend deployment pipeline before serving traffic.
