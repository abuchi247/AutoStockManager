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
- The backend auto-creates new tables on startup via `init_db()` using `Base.metadata.create_all`
- Adding new models/tables is safe — they'll be created automatically on deploy
- Adding new columns to EXISTING tables requires an Alembic migration (create_all won't add columns to existing tables)
- NEVER modify the `init_db()` function to remove the `create_all` call
- The `invoice_number_seq` sequence is also auto-created on startup

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
