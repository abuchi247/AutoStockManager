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

4. **Run database migrations**
   ```bash
   docker exec autostockmanager-backend alembic upgrade head
   ```
   Or create tables directly from models:
   ```bash
   docker exec autostockmanager-backend python -c "
   import asyncio
   from app.database import engine, Base
   from app.models import *
   async def create():
       async with engine.begin() as conn:
           await conn.run_sync(Base.metadata.create_all)
   asyncio.run(create())
   "
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

After the backend is deployed and the database is provisioned, run the setup commands:

```bash
# Link CLI to backend service
railway link --service <backend-service-name>

# Create all database tables
railway run python3 -c "
import asyncio
from app.database import engine, Base
from app.models import *

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(create_tables())
"

# Create the invoice number sequence
railway run python3 -c "
import asyncio
from sqlalchemy import text
from app.database import engine

async def create_seq():
    async with engine.begin() as conn:
        await conn.execute(text('CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1'))
    await engine.dispose()

asyncio.run(create_seq())
"
```

### Step 7: Create Admin User

```bash
railway run python3 -c "
import sys
sys.path.insert(0, '.')
import asyncio, uuid, bcrypt
from datetime import datetime, timezone
from sqlalchemy import text
from app.database import async_session_factory, engine

async def create_admin():
    async with async_session_factory() as session:
        result = await session.execute(
            text('SELECT id FROM users WHERE username = :u'), {'u': 'admin'})
        if result.scalar():
            print('Admin already exists')
            return
        pw_hash = bcrypt.hashpw('Admin123!'.encode(), bcrypt.gensalt(12)).decode()
        await session.execute(text('''
            INSERT INTO users (id, username, email, password_hash, role, is_active, failed_login_attempts, created_at, updated_at)
            VALUES (:id, :u, :e, :pw, :r, TRUE, 0, :now, :now)
        '''), {'id': uuid.uuid4(), 'u': 'admin', 'e': 'admin@autostockmanager.com',
               'pw': pw_hash, 'r': 'Admin', 'now': datetime.now(timezone.utc)})
        await session.commit()
        print('Admin created: admin / Admin123!')
    await engine.dispose()

asyncio.run(create_admin())
"
```

### Step 8: Seed Categories

```bash
railway run python3 -c "
import sys
sys.path.insert(0, '.')
import asyncio, uuid
from datetime import datetime, timezone
from sqlalchemy import text
from app.database import async_session_factory, engine

CATEGORIES = {
    'Brakes': ['Brake Pads', 'Brake Discs', 'Brake Fluid'],
    'Filters': ['Oil Filters', 'Air Filters', 'Fuel Filters', 'Cabin Filters'],
    'Engine Parts': ['Pistons', 'Gaskets', 'Timing Belts', 'Spark Plugs'],
    'Electrical': ['Batteries', 'Alternators', 'Starters', 'Sensors'],
    'Suspension': ['Shock Absorbers', 'Springs', 'Control Arms'],
    'Body Parts': ['Bumpers', 'Fenders', 'Mirrors', 'Lights'],
    'Transmission': ['Clutch', 'Gearbox', 'CV Joints'],
    'Cooling': ['Radiators', 'Water Pumps', 'Thermostats', 'Hoses'],
    'Exhaust': ['Mufflers', 'Catalytic Converters', 'Exhaust Pipes'],
    'Fuel System': ['Fuel Pumps', 'Injectors', 'Fuel Lines'],
}

async def seed():
    async with async_session_factory() as session:
        r = await session.execute(text('SELECT COUNT(*) FROM categories'))
        if (r.scalar() or 0) > 0:
            print('Categories exist, skipping'); return
        now = datetime.now(timezone.utc)
        for parent, subs in CATEGORIES.items():
            pid = uuid.uuid4()
            await session.execute(text('''INSERT INTO categories (id, name, parent_id, description, is_active, created_at, updated_at)
                VALUES (:id, :n, NULL, :d, TRUE, :now, :now)'''),
                {'id': pid, 'n': parent, 'd': f'Auto spare parts - {parent}', 'now': now})
            for s in subs:
                await session.execute(text('''INSERT INTO categories (id, name, parent_id, description, is_active, created_at, updated_at)
                    VALUES (:id, :n, :pid, :d, TRUE, :now, :now)'''),
                    {'id': uuid.uuid4(), 'n': s, 'pid': pid, 'd': f'{parent} - {s}', 'now': now})
        await session.commit()
        print('Categories seeded')
    await engine.dispose()

asyncio.run(seed())
"
```

### Step 9: Generate Public URLs

In the Railway dashboard, go to each service → **Settings** → **Networking** → **Generate Domain**. This gives you public `*.up.railway.app` URLs.

### Step 10: Redeploy Frontend

After setting `NEXT_PUBLIC_API_URL`, redeploy the frontend to bake the URL into the build:

```bash
railway link --service <frontend-service-name>
railway redeploy -y
```

### Troubleshooting Railway Deployment

| Issue | Solution |
|-------|----------|
| Backend returns 502 | Ensure the Dockerfile uses `${PORT:-8000}` — Railway injects its own PORT |
| Login fails | Database is empty — run Steps 6–8 to initialize tables and create admin |
| Frontend can't reach backend | Verify `NEXT_PUBLIC_API_URL` uses `https://` (not `http://`) and includes `/api/v1` |
| CORS errors in browser | Set `CORS_ORIGINS=["*"]` on the backend service, or add the frontend URL specifically |
| Variable change has no effect (frontend) | `NEXT_PUBLIC_*` vars are build-time; redeploy the frontend after changing |
| `railway run` fails with "No such file" | Make sure you're in the `backend/` directory locally when running commands |

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
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for frontend |

## Scale Targets

- 1,000–10,000 spare parts catalog
- Multiple warehouse/store locations
- 5–20 concurrent users
- 20–100 sales transactions per day
- 100,000+ historical sales records
- Multi-year transaction retention (7+ year audit trail)

## License

Private — All rights reserved.
