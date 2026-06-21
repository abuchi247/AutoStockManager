# Auto Spare Parts ERP System

A production-ready Enterprise Resource Planning system designed for automotive spare parts distributors and retailers.

## Overview

This system digitizes and streamlines operations for auto spare parts businesses, replacing manual spreadsheet and paper-based processes with a modern, scalable ERP solution.

## Key Capabilities

- **Inventory Management** — Multi-location stock tracking with barcode support
- **Sales Management** — Cash and credit sales with invoice generation
- **Customer Management** — Credit ledger, aging analysis, payment tracking
- **Supplier Management** — Purchase orders, goods receipt, supplier balances
- **Reporting & Dashboard** — Real-time business intelligence and KPIs
- **Audit Trail** — Complete transaction history and accountability
- **Security** — Role-based access control with JWT authentication

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL |
| Frontend | Next.js, TypeScript, Tailwind CSS, React Query |
| Auth | JWT (Access + Refresh Tokens) |
| Documents | PDF generation (invoices, reports) |
| Barcode | Generation and scanning |
| Deployment | Docker, Docker Compose |

## Scale Targets

- 1,000–10,000 spare parts catalog
- Multiple warehouse/store locations
- 5–20 concurrent users
- 20–100 sales transactions per day
- 100,000+ historical sales records
- Multi-year transaction retention

## Project Structure

```
├── backend/          # FastAPI application
├── frontend/         # Next.js application
├── docker/           # Docker and compose files
├── docs/             # Documentation
└── .kiro/specs/      # Feature specifications
```

## Getting Started

> Setup instructions will be added as the project progresses.

## License

Private — All rights reserved.
