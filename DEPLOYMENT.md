# Deployment Guide — Render

This guide deploys AutoStockManager (frontend, backend API, background worker,
PostgreSQL, and Redis) to [Render](https://render.com) using the `render.yaml`
blueprint in this repo, and then decommissions the old Railway deployment.

The app is deployed **as-is** — no code rewrite. Render runs the existing
Docker images.

---

## What gets deployed

| Service | Type | Plan | Notes |
|---------|------|------|-------|
| `autostockmanager-db` | PostgreSQL | free | Managed Postgres 15 |
| `autostockmanager-redis` | Key Value (Redis) | free | Sessions, rate limiting, job queue |
| `autostockmanager-backend` | Web (Docker) | free | FastAPI; runs migrations then uvicorn workers |
| `autostockmanager-worker` | Worker (Docker) | free | ARQ background jobs (password-reset emails) |
| `autostockmanager-frontend` | Web (Docker) | free | Next.js |

> **Free-tier note:** Free web services sleep after ~15 minutes of inactivity
> and take ~30 seconds to wake on the next request. For steady business use,
> upgrade `autostockmanager-backend` and `autostockmanager-frontend` to the
> cheapest paid instance (about $7/month each) to keep them always-on. The
> database and Redis free tiers are fine to start, but the **free Postgres
> expires after 90 days** — upgrade it before then to avoid data loss.

---

## Prerequisites

1. A [Render account](https://dashboard.render.com/register) (free).
2. This repository pushed to GitHub (already done).
3. An SMTP provider for password-reset emails. Free options:
   - [Brevo](https://www.brevo.com) (formerly Sendinblue) — 300 emails/day free
   - [Resend](https://resend.com) — free tier
   - Gmail SMTP (with an app password) for low volume
   You need: host, port (usually 587), username, password, from-email.

---

## Step 1 — Create the Blueprint

1. Go to the Render Dashboard → **New** → **Blueprint**.
2. Connect your GitHub account and select the **AutoStockManager** repo.
3. Render reads `render.yaml` and shows the 5 services it will create.
4. Click **Apply**. Render creates the database, Redis, and the three
   Docker services, and starts the first build.

The first build takes several minutes (Docker images for backend + frontend).

---

## Step 2 — Set the cross-service URLs and SMTP

A few values can't be known until Render assigns hostnames on the first deploy.
Render marks these as "sync: false" so you fill them in manually.

After the first deploy, note your two public URLs (they look like):
- Backend:  `https://autostockmanager-backend.onrender.com`
- Frontend: `https://autostockmanager-frontend.onrender.com`

Then set the following environment variables in the Render dashboard:

### On `autostockmanager-backend` → Environment
| Variable | Value |
|----------|-------|
| `CORS_ORIGINS` | `https://autostockmanager-frontend.onrender.com` |
| `FRONTEND_BASE_URL` | `https://autostockmanager-frontend.onrender.com` |
| `SMTP_HOST` | your SMTP host |
| `SMTP_USERNAME` | your SMTP username |
| `SMTP_PASSWORD` | your SMTP password |
| `SMTP_FROM_EMAIL` | e.g. `no-reply@yourdomain.com` |

### On `autostockmanager-worker` → Environment
| Variable | Value |
|----------|-------|
| `SMTP_HOST` | same as backend |
| `SMTP_USERNAME` | same as backend |
| `SMTP_PASSWORD` | same as backend |
| `SMTP_FROM_EMAIL` | same as backend |

### On `autostockmanager-frontend` → Environment
| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://autostockmanager-backend.onrender.com/api/v1` |

> **Important:** `NEXT_PUBLIC_API_URL` is baked into the browser bundle at
> **build time**. After setting it, you must **trigger a new deploy** of the
> frontend (Manual Deploy → Deploy latest commit / Clear build cache & deploy)
> so the value is compiled in. Render passes the service env var to the Docker
> build as a build argument because the frontend Dockerfile declares
> `ARG NEXT_PUBLIC_API_URL`.

After setting the backend variables, redeploy the backend too (it needs the
correct `CORS_ORIGINS` and `FRONTEND_BASE_URL` at runtime).

---

## Step 3 — Verify the deployment

1. **Backend health:** open `https://autostockmanager-backend.onrender.com/health`
   → should return `{"status":"healthy", ...}` with `database` and `redis` up.
2. **Migrations:** on the backend service **Logs**, confirm you see
   `Running database migrations...` followed by
   `Starting uvicorn with 2 worker(s)...`. Migrations run automatically on
   backend startup.
3. **Frontend:** open `https://autostockmanager-frontend.onrender.com`.
   You should see the login page.
4. **Admin password:** on first startup with an empty database, the backend
   seeds an initial admin and logs a temporary password. Find it in the
   backend **Logs** (search for `Temporary Password`). Log in and change it.

---

## Step 4 — Log in and set up your business

Follow **SETUP_GUIDE.md** for the business setup SOP (locations, categories,
users, roles, inventory, etc.). It applies identically on Render.

---

## Step 5 — Shut down the Railway deployment

Once the Render deployment is verified and you can log in and use the app:

1. **Back up Railway data first (if you have production data to keep).**
   In the Railway Postgres service, use the connection details to dump:
   ```
   pg_dump "postgresql://USER:PASSWORD@HOST:PORT/DB" -Fc -f railway_backup.dump
   ```
   Restore into Render's database if needed (see "Migrating existing data" below).
2. In the Railway dashboard, open the **project**.
3. For each service (backend, worker, frontend, Postgres, Redis): **Settings →
   Remove Service**, or simply **delete the whole project** (Project Settings →
   Danger → Delete Project).
4. Cancel any Railway subscription/plan if you were on a paid tier so you stop
   being billed.

> Do the Railway shutdown **only after** confirming Render works and you have a
> backup of any data you care about — deletion on Railway is permanent.

---

## Migrating existing data (optional)

If you have real data in Railway you want to keep:

1. Dump from Railway (command above) → `railway_backup.dump`.
2. Get the Render database's **external** connection string
   (Render dashboard → `autostockmanager-db` → Connect → External).
3. Restore:
   ```
   pg_restore --clean --no-owner \
     -d "postgresql://USER:PASSWORD@HOST/DB" railway_backup.dump
   ```
4. Because migrations already ran on Render, restore **data only** if the
   schema matches, or restore into a fresh database before the backend's first
   migration run. When in doubt, start fresh on Render and re-enter setup data.

---

## Ongoing deploys

Render auto-deploys on every push to your default branch by default. To deploy
a change:

```
git push origin main
```

Render rebuilds and redeploys the affected services. The backend applies any
new migrations automatically on startup.

To disable auto-deploy or deploy manually, use each service's **Settings →
Auto-Deploy** and the **Manual Deploy** button.

---

## Troubleshooting

- **Frontend can't reach the API / CORS errors:** confirm `NEXT_PUBLIC_API_URL`
  is set to the backend URL *with* `/api/v1`, that the frontend was
  **rebuilt** after setting it, and that `CORS_ORIGINS` on the backend exactly
  matches the frontend origin (no trailing slash).
- **Login works but refresh/logout fails cross-site:** the refresh cookie is
  `SameSite=none; Secure` (set in `render.yaml`) because the UI and API are on
  different `onrender.com` subdomains. Both must be HTTPS (they are on Render).
- **Backend fails to start on production config validation:** the app rejects
  placeholder secrets and localhost CORS in production. Ensure `CORS_ORIGINS`
  is your real frontend URL and `JWT_SECRET_KEY` is the Render-generated value
  (not a placeholder).
- **Emails not sending:** verify SMTP variables on **both** the backend and the
  worker (the worker actually sends the mail).
- **Service is slow to first response:** free-tier services are waking from
  sleep. Upgrade to a paid instance to keep them warm.
