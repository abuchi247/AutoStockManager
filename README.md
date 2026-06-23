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
| Deployment | Docker, Docker Compose |

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
   docker exec autostockmanager-backend python -c "
   import asyncio, uuid
   from datetime import datetime, timezone
   from passlib.context import CryptContext
   from sqlalchemy import text
   from app.database import async_session_factory

   pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

   async def create_admin():
       async with async_session_factory() as session:
           await session.execute(text('''
               INSERT INTO users (id, username, email, password_hash, role, is_active, failed_login_attempts, created_at, updated_at)
               VALUES (:id, :username, :email, :pw, :role, true, 0, :now, :now)
           '''), {'id': uuid.uuid4(), 'username': 'admin', 'email': 'admin@autostockmanager.com',
                  'pw': pwd_context.hash('Admin123!'), 'role': 'ADMIN', 'now': datetime.now(timezone.utc)})
           await session.commit()
           print('Admin created - username: admin, password: Admin123!')
   asyncio.run(create_admin())
   "
   ```

6. **Access the application**
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
