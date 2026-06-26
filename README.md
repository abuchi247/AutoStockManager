# Auto Spare Parts ERP System

A comprehensive Enterprise Resource Planning system designed for automotive spare parts distributors and retailers. Built with Python FastAPI, Next.js, PostgreSQL, and Redis.

## Overview

This system digitizes and streamlines operations for auto spare parts businesses, replacing manual spreadsheet and paper-based processes with a modern, scalable ERP solution featuring immutable ledger architecture, FIFO cost management, and snapshot-based auditing.

## Key Capabilities

- **Inventory Management** — Multi-location stock tracking with FIFO cost layers and barcode support
- **Sales Management** — Cash and credit sales with pessimistic locking, automatic COGS calculation, and PDF invoice generation
- **Customer Management** — Credit ledger with limit enforcement, aging analysis, and payment tracking
- **Supplier Management** — Purchase orders with full lifecycle (draft → approved → received), goods receipt notes, and supplier balance tracking
- **Transfer Management** — Multi-location transfers with in-transit state and cost layer propagation
- **Barcode System** — Code 128 barcode generation, scanning, and lookup
- **Inventory Audits** — Snapshot-based cycle counts and full stock counts with variance tracking
- **Invoice Generation** — PDF invoices in A4 and thermal (80mm) formats with QR codes
- **Reporting & Dashboard** — Sales, inventory, customer, supplier, and financial reports with CSV/PDF export
- **Notifications** — Low stock alerts, credit limit warnings, overdue customer reminders, and pending approval notifications
- **Audit Trail** — Append-only, immutable record of all critical system events
- **Security** — Role-based access control (Admin, Manager, Salesperson, Storekeeper) with JWT authentication, rate limiting, and account lockout

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 15 |
| Cache/Sessions | Redis 7 |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Axios |
| Auth | JWT (Access + Refresh Tokens), bcrypt |
| PDF | WeasyPrint |
| Barcode/QR | python-barcode (Code 128), qrcode |
| Rate Limiting | slowapi + Redis |
| Testing | pytest, Hypothesis (property-based testing) |
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
   This starts PostgreSQL, Redis, the FastAPI backend, and the Next.js frontend.

4. **Database tables are created automatically** on first startup. If you prefer to run migrations manually:
   ```bash
   docker exec autostockmanager-backend alembic upgrade head
   ```

5. **Create admin user**
   ```bash
   docker exec autostockmanager-backend python scripts/create_user.py \
     --username admin --password Admin123! --role Admin --email admin@autostockmanager.com
   ```

6. **Seed default categories**
   ```bash
   docker exec autostockmanager-backend python scripts/seed_categories.py
   ```
   This creates 10 parent categories (Brakes, Filters, Engine Parts, etc.) with 35 subcategories.

7. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs (Swagger): http://localhost:8000/docs
   - Login: `admin` / `Admin123!`

### Default User Roles

| Role | Access |
|------|--------|
| Admin | Full system access including user management |
| Manager | Approvals, reports, operational oversight |
| Salesperson | Sales processing, customer lookup, invoices |
| Storekeeper | Inventory operations, stock counts, transfers |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application factory
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic layer
│   │   ├── routers/             # FastAPI route handlers
│   │   ├── middleware/          # Auth, rate limiting, security headers
│   │   └── utils/               # FIFO, PDF generation, barcode tools
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Unit and property-based tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # Shared UI components
│   │   ├── hooks/               # Custom React hooks
│   │   └── lib/                 # API client, auth, types
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── .kiro/specs/                  # Feature specifications
```

## API Endpoints

| Module | Prefix | Key Endpoints |
|--------|--------|---------------|
| Auth | `/api/v1/auth` | login, refresh, logout, reset-password |
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
| Notifications | `/api/v1/notifications` | List, mark read |
| Barcodes | `/api/v1/barcodes` | Lookup, decode |

## Creating Users

This is an internal ERP system — there's no public signup. Admins create user accounts via the Settings page or the CLI script.

### Using the CLI script

```bash
# Create an admin
docker exec autostockmanager-backend python scripts/create_user.py \
  --username admin --password Admin123! --role Admin --email admin@example.com

# Create a manager
docker exec autostockmanager-backend python scripts/create_user.py \
  -u manager -p Manager1! -r Manager -e manager@example.com

# Create a salesperson
docker exec autostockmanager-backend python scripts/create_user.py \
  -u sales1 -p Sales123! -r Salesperson -e sales@example.com

# Create a storekeeper
docker exec autostockmanager-backend python scripts/create_user.py \
  -u store1 -p Store123! -r Storekeeper -e store@example.com
```

**Password requirements:** minimum 8 characters, at least one uppercase letter, one lowercase letter, and one digit.

**Available roles:** `Admin`, `Manager`, `Salesperson`, `Storekeeper`

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
railway variable set CORS_ORIGINS='["*"]'
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

After the backend is deployed and the database is provisioned, run the setup script. This is a single command that creates tables, sequences, admin user, and seed data:

```bash
# Link CLI to backend service
railway link --service <backend-service-name>

# Run the all-in-one setup script (idempotent — safe to run multiple times)
cd backend && railway run python3 scripts/setup_db.py
```

This script will:
1. Create all database tables (if they don't exist)
2. Create the `invoice_number_seq` sequence
3. Create an admin user (`admin` / `Admin123!`)
4. Seed 45 default categories (Brakes, Filters, Engine Parts, etc.)

**Note:** The backend also auto-creates tables on every startup via `init_db()`. This means new model/column changes deployed via git push will automatically create any missing tables without manual intervention. However, the setup script is still needed for first-time seeding of admin user and categories.

### Step 7: Verify Setup

After running the setup script, verify everything is working:

```bash
# Test the health endpoint
curl https://<backend-service>.up.railway.app/health

# Test login
curl -X POST https://<backend-service>.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}'
```

If you need to create additional users or re-seed categories manually, the individual scripts still work:

```bash
# Create a specific user
cd backend && railway run python3 scripts/create_user.py -u manager -p Manager1! -r Manager -e manager@example.com

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

### Troubleshooting Railway Deployment

| Issue | Solution |
|-------|----------|
| Backend returns 502 | Ensure `PORT=8000` is set as a Railway service variable. The Dockerfile hardcodes port 8000. |
| Login fails | Run `cd backend && railway run python3 scripts/setup_db.py` to initialize tables and create admin |
| Frontend can't reach backend | Verify `NEXT_PUBLIC_API_URL` uses `https://` (not `http://`) and includes `/api/v1` |
| CORS errors in browser | Set `CORS_ORIGINS=["*"]` on the backend service, or add the frontend URL specifically |
| Variable change has no effect (frontend) | `NEXT_PUBLIC_*` vars are build-time; redeploy the frontend after changing |
| `railway run` fails with "No such file" | Make sure you're in the `backend/` directory locally when running commands |
| New columns/tables missing after deploy | The app auto-creates tables on startup; for column changes on existing tables, run Alembic migrations |

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

## Running Tests

```bash
# Run all backend tests
docker exec autostockmanager-backend pytest

# Run with verbose output
docker exec autostockmanager-backend pytest -v

# Run specific test file
docker exec autostockmanager-backend pytest tests/unit/test_sales_service.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL username |
| `POSTGRES_PASSWORD` | — | PostgreSQL password |
| `POSTGRES_DB` | `autostockmanager` | Database name |
| `SECRET_KEY` | — | JWT signing secret |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |
| `ENVIRONMENT` | `development` | development, staging, or production |
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
