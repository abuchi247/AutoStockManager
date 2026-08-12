# Auto Spare Parts ERP System

A comprehensive Enterprise Resource Planning system designed for automotive spare parts distributors and retailers. Built with Python FastAPI, Next.js, PostgreSQL, and Redis.

## Overview

This system digitizes and streamlines operations for auto spare parts businesses, replacing manual spreadsheet and paper-based processes with a modern, scalable ERP solution featuring immutable ledger architecture, FIFO cost management, and snapshot-based auditing.

## Key Capabilities

- **Inventory Management** — Multi-location stock tracking with FIFO cost layers and barcode support
- **Sales Management** — Cash and credit sales with pessimistic locking, automatic COGS calculation, partial payments at checkout, and PDF invoice generation
- **Customer Management** — Credit ledger with limit enforcement, aging analysis, payment tracking linked to specific sales, and partial payment support
- **Supplier Management** — Purchase orders with full lifecycle (draft → approved → received), goods receipt notes, and supplier balance tracking
- **Transfer Management** — Multi-location transfers with in-transit state and cost layer propagation
- **Barcode System** — Code 128 barcode generation, scanning, and lookup
- **Inventory Audits** — Snapshot-based cycle counts and full stock counts with variance tracking
- **Invoice Generation** — PDF invoices in A4 and thermal (80mm) formats with QR codes and barcodes. Supports regeneration to reflect updated business settings. Credit notes generated automatically for returns.
- **Business Settings** — Configurable company profile (name, logo, address, bank details) that populates invoices and reports
- **Reporting & Dashboard** — Sales, inventory, customer, supplier, and financial reports with CSV/PDF export. Dashboard with Top 5 Products and Top 5 Customers widgets filterable by period (month, 3M, 6M, 1Y, all time).
- **Notifications** — Low stock alerts, credit limit warnings, overdue customer reminders, and pending approval notifications
- **Audit Trail** — Append-only, immutable record of all critical system events
- **Security** — Role-based access control (Admin, Manager, Salesperson, Storekeeper) with JWT authentication, rate limiting, account lockout, and forced password change on first login

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 15 |
| Cache/Sessions | Redis 7 |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, React Query, Axios |
| Auth | JWT (Access + Refresh Tokens), bcrypt |
| PDF | WeasyPrint |
| Barcode/QR | python-barcode (Code 128), qrcode |
| Rate Limiting | slowapi + Redis |
| Background Jobs | ARQ (async Redis-based task queue) |
| Error Tracking | Sentry |
| Testing (Backend) | pytest (1115 unit tests), Hypothesis (property-based) |
| Testing (Frontend) | Vitest (48 unit tests), Playwright (E2E + accessibility via axe-core) |
| Deployment | Docker, Docker Compose, Railway |

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/abuchi247/AutoStockManager.git
   cd AutoStockManager
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your `POSTGRES_PASSWORD` and `SECRET_KEY` values.

3. **Start all services**
   ```bash
   docker-compose up --build
   ```
   This builds and starts all five containers: PostgreSQL, Redis, the FastAPI backend, the ARQ background worker, and the Next.js frontend. The frontend is built inside Docker using the production standalone build — no local Node.js installation required.

4. **Database migrations** run automatically inside the backend container before Uvicorn accepts traffic. To re-run them manually (e.g. after adding migrations):
   ```bash
   docker exec autostockmanager-backend alembic upgrade head
   ```

5. **Retrieve the initial admin password**. On a fresh database (no users), the backend auto-creates an `admin` account with a random temporary password and prints it to the container logs exactly once:
   ```bash
   docker logs autostockmanager-backend 2>&1 | grep "Temporary Password"
   ```
   You will see output like:
   ```
     Temporary Password: xK7#mPq2RvLnJ9Ys
   ```
   This password is generated uniquely for each deployment and is never stored in plaintext.

6. **Log in and set your password**. Open http://localhost:3000 and log in with username `admin` and the temporary password from the logs. You will be redirected to a "Set your password" screen where you must choose a new password before accessing the system.

7. **Seed default categories** (optional)
   ```bash
   docker exec autostockmanager-backend python scripts/seed_categories.py
   ```
   This creates 10 parent categories (Brakes, Filters, Engine Parts, etc.) with 35 subcategories.

8. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs (Swagger): http://localhost:8000/docs

> **Local development with hot-reload:** if you want live code reloading on the frontend, stop the frontend container (`docker-compose stop frontend`) and run `npm run dev` in the `frontend/` directory instead. The backend services stay in Docker.

### Database backups

Run an on-demand backup at any time (results go to `./backups/` on the host):

```bash
docker-compose run --rm --profile backup backup
```

Label it before a release to make it easy to find later:

```bash
docker-compose run --rm --profile backup -e BACKUP_LABEL=pre-release backup
```

In production, `docker-compose.production.yml` includes a scheduled backup service that runs automatically every day at 02:00 UTC. See [OPERATIONS_RUNBOOK.md §4](OPERATIONS_RUNBOOK.md#4-backup-and-restore) for restore instructions, off-site storage, and restore verification.

### Initial Admin Provisioning

The system follows security best practices for initial credentials:

- **No hardcoded passwords** — the initial admin password is a cryptographically random 16-character string generated at first startup.
- **Displayed once** — the password appears in the backend container logs only on the first boot when the users table is empty. It is not shown on subsequent restarts.
- **Forced password change** — the auto-provisioned admin (and all admin-created users) must change their password on first login before accessing any part of the system.
- **Scoped token** — during the password change flow, a short-lived token (10-minute TTL) restricts the user to only the password change endpoint until they set their own credentials.

If you need to create additional users via CLI, they also require a password change on first login by default:

```bash
docker exec autostockmanager-backend python scripts/create_user.py \
  --username manager --password TempPass1! --role Manager --email manager@example.com
```

To skip the forced password change (e.g., for automated testing), add `--no-force-change`:

```bash
docker exec autostockmanager-backend python scripts/create_user.py \
  --username testuser --password TestPass1! --role Salesperson --email test@example.com --no-force-change
```

### Production operations

Production deployments must replace every development placeholder, inject credentials through a secret manager, and run the serialized Alembic migration step before enabling traffic. The complete procedure covers required environment variables, secret generation, backups and restore drills, `/health` readiness checks, ARQ worker operation, error tracking, rollback, supported frontend versions, and dependency upgrades:

- [Production Operations Runbook](OPERATIONS_RUNBOOK.md)

The Compose defaults are for local development only. Never commit a populated `.env` file. The initial admin password is unique per deployment and must be changed on first login.

### Default User Roles

| Role | Access |
|------|--------|
| Admin | Full system access including user management |
| Manager | Approvals, reports, operational oversight |
| Salesperson | Sales processing, customer lookup, invoices |
| Storekeeper | Inventory operations, stock counts, transfers |

### Role Permissions Matrix

| Feature | Admin | Manager | Salesperson | Storekeeper |
|---------|:-----:|:-------:|:-----------:|:-----------:|
| User management | ✅ | ❌ | ❌ | ❌ |
| Business settings (update) | ✅ | ❌ | ❌ | ❌ |
| Delete categories/locations | ✅ | ❌ | ❌ | ❌ |
| Reports (all types) | ✅ | ✅ | ❌ | ❌ |
| Supplier management | ✅ | ✅ | ❌ | ❌ |
| Purchase orders | ✅ | ✅ | ❌ | ❌ |
| Approve transfers/audits | ✅ | ✅ | ❌ | ❌ |
| Credit adjustments | ✅ | ✅ | ❌ | ❌ |
| Sales returns | ✅ | ✅ | ❌ | ❌ |
| Delete customers/suppliers | ✅ | ✅ | ❌ | ❌ |
| Create/update categories | ✅ | ✅ | ❌ | ❌ |
| Sales (create/confirm/cancel) | ✅ | ✅ | ✅ | ❌ |
| Customer management | ✅ | ✅ | ✅ | ❌ |
| Record payments | ✅ | ✅ | ✅ | ❌ |
| Generate/download invoices | ✅ | ✅ | ✅ | ❌ |
| Spare parts (create/edit) | ✅ | ✅ | ❌ | ✅ |
| Stock adjustments | ✅ | ✅ | ❌ | ✅ |
| Transfers (create/receive) | ✅ | ✅ | ❌ | ✅ |
| Audits (initiate/count) | ✅ | ✅ | ❌ | ✅ |
| Receive purchase goods | ✅ | ✅ | ❌ | ✅ |
| Barcodes (generate/assign) | ✅ | ✅ | ❌ | ✅ |
| Dashboard (role-filtered) | ✅ | ✅ | ✅ | ✅ |
| Notifications (own) | ✅ | ✅ | ✅ | ✅ |
| View locations/categories/stock | ✅ | ✅ | ✅ | ✅ |

### Notification Routing by Role

Notifications are automatically generated and delivered to specific roles based on the event type:

| Notification Type | Target Roles | Trigger |
|-------------------|-------------|---------|
| Low Stock Alert | Storekeeper, Manager, Admin | Stock falls below minimum level |
| Credit Limit Exceeded | Manager, Admin | Customer balance exceeds credit limit |
| Overdue Customer | Manager, Admin | Customer balance outstanding 90+ days |
| Pending Approval Reminder | Manager, Admin | Transfer or PO pending approval > 24 hours |

Each user sees only their own notifications. Notifications support read/unread status and can be marked individually or in bulk.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application factory
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   ├── health.py            # Readiness/liveness probes
│   │   ├── models/              # SQLAlchemy ORM models (26 tables)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic layer + background jobs (ARQ)
│   │   ├── routers/             # FastAPI route handlers
│   │   ├── middleware/          # Auth, rate limiting, security headers, telemetry
│   │   └── utils/               # FIFO, PDF generation, barcode tools
│   ├── alembic/                 # Database migrations (8 revisions)
│   ├── tests/                   # 1115 unit + property-based tests
│   ├── scripts/                 # CLI utilities (create_user, seed, setup_db)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # Shared UI components (DataTable, Modal, etc.)
│   │   ├── hooks/               # Custom React hooks (useAuth, useDebouncedValue)
│   │   └── lib/                 # API client, auth, types, validation, reports
│   ├── e2e/                     # Playwright E2E + accessibility tests
│   ├── scripts/                 # Bundle budget checker
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml           # Backend, Worker, Frontend, PostgreSQL, Redis
├── .env.example
├── .github/workflows/           # CI + E2E pipelines
├── OPERATIONS_RUNBOOK.md        # Production deployment guide
└── .kiro/specs/                 # Feature specifications
```

## API Endpoints

| Module | Prefix | Key Endpoints |
|--------|--------|---------------|
| Auth | `/api/v1/auth` | login, refresh, logout, force-change-password, reset-password |
| Users | `/api/v1/users` | CRUD (Admin only) |
| Spare Parts | `/api/v1/spare-parts` | CRUD, search, barcode |
| Stock | `/api/v1/stock` | Locations, movements |
| Sales | `/api/v1/sales` | Create, confirm, return |
| Customers | `/api/v1/customers` | CRUD, ledger, aging |
| Credit | `/api/v1/credit` | Payments, adjustments |
| Suppliers | `/api/v1/suppliers` | CRUD, balance, aging |
| Purchases | `/api/v1/purchase-orders` | Create, approve, receive, cancel |
| Transfers | `/api/v1/transfers` | Create, approve, receive |
| Audits | `/api/v1/audits` | Initiate, counts, approve, reconciliation |
| Reports | `/api/v1/reports` | Sales, inventory, customers, suppliers, financial |
| Dashboard | `/api/v1/dashboard` | KPI widgets |
| Invoices | `/api/v1/invoices` | Generate, download PDF |
| Business Settings | `/api/v1/business-settings` | Get, update company profile |
| Notifications | `/api/v1/notifications` | List, mark read |
| Barcodes | `/api/v1/barcodes` | Lookup, decode |

## Creating Users

This is an internal ERP system — there's no public signup. Admins create user accounts via the Settings page or the CLI script. All newly created users must change their password on first login.

### Using the CLI script

```bash
# Create an admin (will be required to set own password on first login)
docker exec autostockmanager-backend python scripts/create_user.py \
  --username admin --password TempAdmin1! --role Admin --email admin@example.com

# Create a manager
docker exec autostockmanager-backend python scripts/create_user.py \
  -u manager -p TempMgr1! -r Manager -e manager@example.com

# Create a salesperson
docker exec autostockmanager-backend python scripts/create_user.py \
  -u sales1 -p TempSales1! -r Salesperson -e sales@example.com

# Create a storekeeper
docker exec autostockmanager-backend python scripts/create_user.py \
  -u store1 -p TempStore1! -r Storekeeper -e store@example.com

# Skip forced password change (for testing/automation only)
docker exec autostockmanager-backend python scripts/create_user.py \
  -u testuser -p TestPass1! -r Salesperson -e test@example.com --no-force-change
```

**Password requirements:** minimum 8 characters, at least one uppercase letter, one lowercase letter, and one digit.

**Available roles:** `Admin`, `Manager`, `Salesperson`, `Storekeeper`

**First login behavior:** By default, all CLI-created users must change their password on first login. The temporary password provided in the `--password` flag is only used for the initial authentication — the user immediately sets their own password. Use `--no-force-change` to skip this requirement (not recommended for production).

## Deploying to Railway

[Railway](https://railway.app) is the recommended platform for cloud deployment. This section covers the full process from project creation to a working production environment.

### Prerequisites

- [Railway CLI](https://docs.railway.com/guides/cli) installed (`brew install railway` on macOS)
- A Railway account (free tier available)
- GitHub repository connected to Railway

### Step 1: Create Railway Project

```bash
# Login to Railway
railway login

# Create a new project (or link to an existing one)
railway init
```

### Step 2: Add Database Services

In the Railway dashboard:
1. Click **"+ New"** → **"Database"** → **PostgreSQL**
2. Click **"+ New"** → **"Database"** → **Redis**

Both will auto-provision and provide connection URLs.

### Step 3: Deploy Backend Service

1. In Railway dashboard, click **"+ New"** → **"GitHub Repo"** → select your repo
2. Set the **Root Directory** to `backend` (or configure via `railway.json`)
3. Railway auto-detects the Dockerfile and builds/deploys

### Step 4: Deploy Frontend Service

1. Click **"+ New"** → **"GitHub Repo"** → select the same repo again
2. Set the **Root Directory** to `frontend`
3. Railway builds and deploys the Next.js app

### Step 5: Configure Environment Variables

Link your CLI to the backend service and set required variables:

```bash
# Link to backend service
railway link --service <backend-service-name>

# Set environment variables
railway variable set DATABASE_URL=<railway-postgres-url>
railway variable set REDIS_URL=<railway-redis-url>
railway variable set JWT_SECRET_KEY=<your-strong-secret>
railway variable set CORS_ORIGINS='["https://<frontend-service>.up.railway.app"]'
railway variable set ENVIRONMENT=production
railway variable set JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
railway variable set JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

For the frontend service:

```bash
# Link to frontend service
railway link --service <frontend-service-name>

# IMPORTANT: Use https:// (not http://) for the backend URL
railway variable set NEXT_PUBLIC_API_URL=https://<backend-service>.up.railway.app/api/v1
```

> **Note:** `NEXT_PUBLIC_API_URL` is a build-time variable in Next.js. After changing it, you must redeploy the frontend for it to take effect.

### Step 6: Initialize the Database

After the backend is deployed and the database is provisioned, apply the reviewed schema migrations before running the seed/setup script. The migration command is safe to rerun and is serialized with other deployment instances:

```bash
# Link CLI to backend service
railway link --service <backend-service-name>

# Apply migrations explicitly; a failure blocks the deployment step
cd backend && railway run alembic upgrade head

# Create the admin user and seed categories
cd backend && railway run python3 scripts/setup_db.py
```

The Docker entrypoint also runs `alembic upgrade head` before starting Uvicorn, so a failed migration prevents the API from accepting traffic. `setup_db.py` uses the same migration runner and only handles seed data after migrations succeed.

This script will:
1. Apply all pending Alembic migrations
2. Seed 45 default categories (Brakes, Filters, Engine Parts, etc.)

The initial admin account is auto-provisioned on first startup when the users table is empty. Check the backend logs for the temporary password:

```bash
railway logs --service <backend-service-name> | grep "Temporary Password"
```

**Note:** The backend does not create tables or apply schema patches at runtime. The Docker startup command and `setup_db.py` both run the reviewed Alembic migration chain before any seed data is written.

### Step 7: Verify Setup

After running the setup script, verify everything is working:

```bash
# Test the health endpoint
curl https://<backend-service>.up.railway.app/health

# Test login (use the temporary password from the backend logs)
curl -X POST https://<backend-service>.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<temp-password-from-logs>"}'
```

The login will return `password_change_required: true` with a scoped token. Use the frontend to complete the password change, or call the API directly:

```bash
curl -X POST https://<backend-service>.up.railway.app/api/v1/auth/force-change-password \
  -H "Content-Type: application/json" \
  -d '{"password_change_token":"<token-from-login>","new_password":"YourSecurePass1!"}'
```

If you need to create additional users or re-seed categories manually, the individual scripts still work:

```bash
# Create a specific user (will require password change on first login)
cd backend && railway run python3 scripts/create_user.py -u manager -p TempMgr1! -r Manager -e manager@example.com

# Re-seed categories (skips if any exist)
cd backend && railway run python3 scripts/seed_categories.py
```

### Step 8: Generate Public URLs

In the Railway dashboard, go to each service → **Settings** → **Networking** → **Generate Domain**. This gives you public `*.up.railway.app` URLs.

### Step 9: Redeploy Frontend

After setting `NEXT_PUBLIC_API_URL`, redeploy the frontend to bake the URL into the build:

```bash
railway link --service <frontend-service-name>
railway redeploy -y
```

**Migration policy:** Never modify production schema manually or rely on SQLAlchemy metadata creation. Add a reviewed revision under `backend/alembic/versions/`, validate it against a copy of the current database, then run:

```bash
# Local/container deployment
cd backend && alembic upgrade head

# Railway deployment
railway run alembic upgrade head
```

The migration runner holds a PostgreSQL advisory lock, so only one instance applies revisions at a time. If a revision fails, the command exits non-zero and the Docker startup command does not launch the API. To use controlled startup execution instead of the deployment command, set `RUN_MIGRATIONS_ON_STARTUP=true`; failures are propagated and abort application startup.

### Troubleshooting Railway Deployment

| Issue | Solution |
|-------|----------|
| Backend returns 502 | Ensure `PORT=8000` is set as a Railway service variable. The Dockerfile hardcodes port 8000. |
| Login fails | Run `cd backend && railway run python3 scripts/setup_db.py` to initialize tables and create admin |
| Frontend can't reach backend | Verify `NEXT_PUBLIC_API_URL` uses `https://` (not `http://`) and includes `/api/v1` |
| CORS errors in browser | Set `CORS_ORIGINS` to the exact frontend URL, e.g. `'["https://<frontend>.up.railway.app"]'`. Using `["*"]` is **not permitted** in production and will be rejected at startup. |
| Variable change has no effect (frontend) | `NEXT_PUBLIC_*` vars are build-time; redeploy the frontend after changing |
| `railway run` fails with "No such file" | Make sure you're in the `backend/` directory locally when running commands |
| New columns/tables missing after deploy | Add a reviewed Alembic revision and run `alembic upgrade head`; the API will not apply schema changes implicitly |

### Architecture on Railway

```
┌─────────────────────────────────────────────────┐
│                   Railway                        │
│                                                  │
│  ┌──────────────┐       ┌──────────────┐       │
│  │   Frontend   │──────▶│   Backend    │       │
│  │  (Next.js)   │       │  (FastAPI)   │       │
│  │  Port: $PORT │       │  Port: $PORT │       │
│  └──────────────┘       └──────┬───────┘       │
│                                 │                │
│                    ┌────────────┼────────────┐   │
│                    │            │            │   │
│              ┌─────▼─────┐ ┌───▼────┐       │   │
│              │ PostgreSQL │ │ Redis  │       │   │
│              │   (DB)     │ │(Cache) │       │   │
│              └───────────┘ └────────┘       │   │
│                                              │   │
└─────────────────────────────────────────────────┘
```

### Live URLs (Current Deployment)

- **Frontend:** https://lively-flexibility-production-2bae.up.railway.app
- **Backend API:** https://autostockmanager-production.up.railway.app
- **Health Check:** https://autostockmanager-production.up.railway.app/health

## First-Time Configuration

After initial setup, an Admin should configure the business profile so that invoices display the correct company information.

1. Log in as Admin
2. Go to **Settings** → **Business Profile**
3. Fill in:
   - Business name
   - Phone, email, address
   - Tax ID
   - Upload a business logo (PNG/JPEG, max 500KB — resized automatically for invoices)
   - Bank details (shown on invoices for payment instructions)
   - Invoice footer text
4. Click **Save Business Settings**

This information appears on all generated invoices. To update it later, change the settings and click **Regenerate** on any existing invoice to re-render it with the new details.

## Running Tests

### Backend Tests

```bash
# Run all backend tests (1115 unit tests)
docker exec autostockmanager-backend pytest

# Run with verbose output
docker exec autostockmanager-backend pytest -v

# Run specific test file
docker exec autostockmanager-backend pytest tests/unit/test_sales_service.py

# Run locally (requires system Python with deps installed)
cd backend && pytest --tb=short -q
```

### Frontend Tests

```bash
# Unit tests (Vitest — 48 tests across 14 files)
cd frontend && npm run test

# Type checking
cd frontend && npx tsc --noEmit

# Lint
cd frontend && npm run lint

# Bundle size budget check
cd frontend && npm run perf:bundle

# End-to-end tests (Playwright — requires running backend + frontend, and a user
# with --no-force-change so Playwright can log in directly)
cd frontend && E2E_USERNAME=testuser E2E_PASSWORD='TestPass1!' npm run e2e

# Accessibility audit via Lighthouse
cd frontend && npm run perf:lighthouse
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL username |
| `POSTGRES_PASSWORD` | — | PostgreSQL password |
| `POSTGRES_DB` | `autostockmanager` | Database name |
| `DATABASE_URL` | (derived) | Full async connection string (auto-built from above if not set) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL for caching and sessions |
| `JWT_SECRET_KEY` | — | JWT signing secret (min 32 chars in production) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `SENTRY_DSN` | — | Sentry error tracking DSN (optional, enabled in production) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Backend URL for frontend (must include /api/v1) |

## Scale Targets

- 1,000–10,000 spare parts catalog
- Multiple warehouse/store locations
- 5–20 concurrent users
- 20–100 sales transactions per day
- 100,000+ historical sales records
- Multi-year transaction retention (7+ year audit trail)

## License

Private — All rights reserved.

## Frontend end-to-end tests

The Playwright suite covers browser login and creation/cancellation of an isolated draft sale. It creates a unique location, spare part, and stock adjustment through the authenticated API, then removes the fixture records after the test; it does not use shared production data.

Create a dedicated test user first (bypassing the forced password change so Playwright can log in directly):

```bash
docker exec autostockmanager-backend python scripts/create_user.py \
  -u testuser -p TestPass1! -r Salesperson -e test@example.com --no-force-change
```

Then install dependencies and run the suite:

```bash
npm ci
npx playwright install chromium
npm run build
E2E_USERNAME=testuser E2E_PASSWORD='TestPass1!' npm run e2e
```

The API must be available at `E2E_API_URL` (default `http://127.0.0.1:8000/api/v1`) and the frontend at `PLAYWRIGHT_BASE_URL` (default `http://127.0.0.1:3000`). Set `PLAYWRIGHT_SKIP_WEBSERVER=true` when an already-running frontend should be reused. CI supplies `E2E_USERNAME` and `E2E_PASSWORD` through encrypted repository secrets and starts disposable PostgreSQL, Redis, and backend services before running the suite. The CI workflow is `.github/workflows/frontend-e2e.yml`.
