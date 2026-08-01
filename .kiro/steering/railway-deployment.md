---
inclusion: auto
---

# Railway Deployment Rules

These rules MUST be followed to prevent breaking the hosted Railway deployment.

## Port Configuration
- The backend Dockerfile MUST hardcode port 8000: `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- NEVER use `${PORT}` or dynamic port variables in the Dockerfile CMD
- Railway has `PORT=8000` set as an explicit service variable — do NOT remove it
- Do NOT change EXPOSE or CMD port values without also updating the Railway variable

## Database Changes
- The backend runs `alembic upgrade head` before Uvicorn accepts traffic.
- Schema changes MUST be represented by a reviewed Alembic migration; application startup does not call `Base.metadata.create_all` or execute inline DDL.
- The migration runner uses a PostgreSQL advisory lock to serialize concurrent deployment instances.
- Adding new columns to existing tables requires an Alembic migration.
- A migration failure MUST leave the container stopped rather than serving a partial schema.

## Frontend Environment
- `NEXT_PUBLIC_API_URL` on the frontend Railway service MUST be `https://autostockmanager-production.up.railway.app/api/v1`
- This is a BUILD-TIME variable — if changed, the frontend must be redeployed
- ALWAYS use `https://` (not `http://`) for Railway URLs

## CORS
- Backend `CORS_ORIGINS` on Railway is set to `["*"]` — do NOT change to specific origins unless you include the frontend URL

## What NOT to do
- Do NOT remove or rename existing database columns without a migration
- Do NOT change the Dockerfile CMD port
- Do NOT remove the PORT=8000 Railway variable
- Do NOT change NEXT_PUBLIC_API_URL to use http:// instead of https://
