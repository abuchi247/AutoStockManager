# Implementation Plan: Auto Spare Parts ERP System

## Overview

This plan implements a comprehensive ERP system for automotive spare parts using Python FastAPI backend with SQLAlchemy 2.0 (async), PostgreSQL, and a Next.js frontend. The architecture centers on immutable ledger patterns, FIFO cost layer management, pessimistic locking for concurrency control, and snapshot-based auditing.

## Tasks

- [x] 1. Project scaffolding and infrastructure
  - [x] 1.1 Create Docker Compose configuration with FastAPI, PostgreSQL 15, Redis, and Next.js services
    - Create `docker-compose.yml` with service definitions, volumes, networks, and environment variables
    - Create `backend/Dockerfile` and `frontend/Dockerfile`
    - Create `.env.example` with all required environment variables
    - _Requirements: 17.7, 18.1_

  - [x] 1.2 Set up FastAPI application factory with async configuration
    - Create `backend/app/main.py` with application factory pattern
    - Create `backend/app/config.py` using pydantic-settings for configuration management
    - Create `backend/app/database.py` with async SQLAlchemy engine and session factory
    - Create `backend/app/dependencies.py` with `get_db` and `get_current_user` dependency injection
    - Create `backend/requirements.txt` with all Python dependencies (pinned versions)
    - _Requirements: 17.7, 18.1_

  - [x] 1.3 Set up Alembic for database migrations
    - Create `backend/alembic.ini` and `backend/alembic/` directory structure
    - Configure Alembic `env.py` for async SQLAlchemy
    - Create initial migration script
    - _Requirements: 1.1_

- [x] 2. Base models and database foundation
  - [x] 2.1 Create SQLAlchemy BaseModel with audit columns and SoftDeleteMixin
    - Create `backend/app/models/base.py` with `BaseModel` (id, created_at, updated_at, created_by, updated_by) and `SoftDeleteMixin` (deleted_at, deleted_by)
    - Implement query filter that excludes soft-deleted records by default
    - _Requirements: 1.1, 1.2_

  - [x]* 2.2 Write property test for soft delete preserves data
    - **Property 4: Soft Delete Preserves Data**
    - **Validates: Requirements 1.2**

  - [x] 2.3 Create Location model
    - Create `backend/app/models/location.py` with name, type, address, is_active fields
    - _Requirements: 4.1_

  - [x] 2.4 Create SparePart model with category hierarchy
    - Create `backend/app/models/spare_part.py` with all attributes (part_number, barcode, name, description, brand, category, subcategory, vehicle_compatibility, UOM, cost_price, selling_price, min/max stock levels, reorder_quantity)
    - Create `backend/app/models/category.py` for hierarchical categories
    - _Requirements: 3.1, 3.4_

  - [x]* 2.5 Write property test for unique part number and barcode
    - **Property 9: Unique Part Number and Barcode**
    - **Validates: Requirements 3.2, 18.5**

  - [x] 2.6 Generate Alembic migration for base models, locations, spare_parts, and categories
    - Run `alembic revision --autogenerate` and verify the generated migration
    - Apply partial unique indexes for soft-delete compatibility
    - _Requirements: 18.5, 18.7_

- [x] 3. Authentication and security infrastructure
  - [x] 3.1 Create User model and authentication service
    - Create `backend/app/models/user.py` with username, email, password_hash, role, is_active, locked_until, failed_login_attempts
    - Create `backend/app/services/auth_service.py` with login, refresh, logout, password reset, and account lockout logic
    - Implement bcrypt password hashing with cost factor 12
    - Implement JWT access token and refresh token generation/validation
    - Implement account lockout after 5 failed attempts within 15 minutes (30-minute lockout)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 2.8_

  - [x]* 3.2 Write property test for password complexity validation
    - **Property 8: Password Complexity Validation**
    - **Validates: Requirements 2.5**

  - [x] 3.3 Create RBAC middleware and security middleware
    - Create `backend/app/middleware/auth.py` with JWT verification and role extraction
    - Create `backend/app/middleware/rate_limit.py` using Redis + slowapi (100 req/min authenticated, 20 req/min unauthenticated)
    - Create `backend/app/middleware/security_headers.py` (CSP, X-Content-Type-Options, X-Frame-Options, HSTS)
    - _Requirements: 17.1, 17.2, 17.7, 17.8_

  - [x]* 3.4 Write property test for RBAC endpoint enforcement
    - **Property 25: RBAC Endpoint Enforcement**
    - **Validates: Requirements 17.1**

  - [x] 3.5 Create auth router with login, refresh, logout, password reset endpoints
    - Create `backend/app/routers/auth.py` with POST /api/v1/auth/login, /refresh, /logout, /reset-password
    - Create `backend/app/routers/users.py` with GET/POST /api/v1/users (Admin only)
    - Create `backend/app/schemas/auth.py` and `backend/app/schemas/user.py` with Pydantic models
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 17.3, 17.4, 17.5, 17.6_

  - [x] 3.6 Create session registry and login history
    - Implement session registry tracking active refresh tokens per user in Redis
    - Implement login history recording (timestamp, IP, user agent, success/failure)
    - Implement admin session revocation (invalidate all refresh tokens for a user)
    - _Requirements: 17.3, 17.4, 17.5, 17.6_

- [x] 4. Checkpoint - Ensure base infrastructure tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Core inventory domain
  - [x] 5.1 Create inventory service and spare parts CRUD
    - Create `backend/app/services/inventory_service.py` with create, read, update, soft-delete operations
    - Create `backend/app/schemas/spare_part.py` with request/response Pydantic models
    - Create `backend/app/routers/spare_parts.py` with GET/POST/PUT/DELETE endpoints
    - Implement search by part_number, barcode, name, brand, category, vehicle_compatibility
    - _Requirements: 3.1, 3.2, 3.4, 3.5_

  - [x] 5.2 Create Stock_Status_Cache model and service
    - Create `backend/app/models/stock_status_cache.py` with spare_part_id, location_id, current_quantity, last_reconciled_at
    - Create composite unique index on (spare_part_id, location_id)
    - Implement stock query endpoint GET /api/v1/stock/locations/{id}
    - _Requirements: 18.1, 18.3, 18.8_

- [x] 6. Immutable ledger infrastructure
  - [x] 6.1 Create Inventory_Movement_Ledger model
    - Create `backend/app/models/inventory_movement_ledger.py` with spare_part_id, location_id, quantity_change, movement_type, reference_type, reference_id, unit_cost, created_by, created_at
    - Create composite index on (spare_part_id, location_id, created_at) for reconciliation
    - _Requirements: 4.8, 18.9_

  - [x] 6.2 Create Cost_Layer model and FIFO consumption algorithm
    - Create `backend/app/models/cost_layer.py` with spare_part_id, location_id, unit_cost, original_quantity, remaining_quantity, source_type, source_reference_id, created_at
    - Create partial composite index on (spare_part_id, location_id, created_at) WHERE remaining_quantity > 0
    - Create `backend/app/utils/fifo.py` with `consume_fifo_layers` function implementing chronological consumption with pessimistic locking
    - _Requirements: 1.5, 1.8, 1.10, 18.10_

  - [x]* 6.3 Write property test for FIFO consumption order
    - **Property 1: FIFO Consumption Order**
    - **Validates: Requirements 1.5, 1.10, 3.7, 4.11**

  - [x] 6.4 Implement atomic ledger-write + cache-update pattern
    - Create helper function that writes to Inventory_Movement_Ledger and atomically updates Stock_Status_Cache in the same transaction
    - _Requirements: 18.2_

  - [x]* 6.5 Write property test for stock cache equals ledger sum
    - **Property 7: Stock Cache Equals Ledger Sum**
    - **Validates: Requirements 3.6, 18.2**

  - [x]* 6.6 Write property test for double-entry balance
    - **Property 6: Double-Entry Balance**
    - **Validates: Requirements 1.7**

- [x] 7. Multi-location management
  - [x] 7.1 Create Transfer model and transfer service
    - Create `backend/app/models/transfer.py` with spare_part_id, source/destination location, quantity, status, consumed_layer_details (JSON), requested_by, approved_by, received_by, timestamps
    - Create `backend/app/services/transfer_service.py` with create, approve, receive, cancel operations
    - Implement transfer state machine: pending → approved → in_transit → received (or cancelled)
    - _Requirements: 4.2, 4.4_

  - [x] 7.2 Implement transfer approval with FIFO cost layer consumption
    - In approve flow: acquire pessimistic lock on source Stock_Status_Cache, validate quantity, consume FIFO layers at source, write ledger entries (TRANSFER_OUT at source, TRANSFER_IN_TRANSIT), update cache, store consumed layer details on transfer record
    - _Requirements: 4.3, 4.5, 4.9, 4.11_

  - [x] 7.3 Implement transfer receive with cost layer creation at destination
    - In receive flow: write ledger entries (TRANSFER_RECEIVED from in_transit, TRANSFER_IN at destination), create new cost layers at destination using unit costs from consumed source layers, update destination cache
    - _Requirements: 4.6, 4.10, 4.12_

  - [x]* 7.4 Write property test for transfer source deduction and destination creation
    - **Property 10: Transfer Source Deduction and Destination Creation**
    - **Validates: Requirements 4.5, 4.6, 4.10, 4.12**

  - [x]* 7.5 Write property test for in-transit stock unavailability
    - **Property 11: In-Transit Stock Unavailability**
    - **Validates: Requirements 4.7**

  - [x]* 7.6 Write property test for transfer quantity validation
    - **Property 12: Transfer Quantity Validation**
    - **Validates: Requirements 4.9**

  - [x] 7.7 Create transfer router with endpoints
    - Create `backend/app/routers/transfers.py` with GET/POST /api/v1/transfers, POST /approve, POST /receive
    - Create `backend/app/schemas/transfer.py` with request/response models
    - _Requirements: 4.2, 4.4, 4.5, 4.6_

- [x] 8. Checkpoint - Ensure inventory and transfer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Sales management
  - [x] 9.1 Create Sale and SaleItem models
    - Create `backend/app/models/sale.py` with customer_id, location_id, invoice_number, status, payment_type, subtotal, tax_amount, total_amount, discount_total
    - Create sale_items table with sale_id, spare_part_id, quantity, unit_price, discount_amount, line_total, cost_of_goods_sold
    - _Requirements: 5.1_

  - [x] 9.2 Implement sales service with pessimistic locking and FIFO COGS
    - Create `backend/app/services/sales_service.py` with create_sale and confirm_sale methods
    - In confirm_sale: acquire SELECT FOR UPDATE on Stock_Status_Cache rows, validate stock, consume FIFO layers (calculate COGS), write ledger entries, update cache — all in single transaction
    - Implement line_total calculation as (quantity × unit_price) - discount_amount
    - _Requirements: 5.2, 5.6, 5.7, 5.9, 5.10, 5.11_

  - [x]* 9.3 Write property test for sale line total calculation
    - **Property 13: Sale Line Total Calculation**
    - **Validates: Requirements 5.7**

  - [x]* 9.4 Write property test for sale stock deduction via ledger
    - **Property 14: Sale Stock Deduction via Ledger**
    - **Validates: Requirements 5.2**

  - [x] 9.5 Implement sales return with new cost layer creation
    - Implement return_sale method that creates return entries in the ledger, creates a new cost layer at return location using original sale line item's unit cost with created_at = return processing date
    - Ensure no previously consumed/closed cost layers are modified
    - _Requirements: 5.8, 5.12, 5.13, 5.14_

  - [x]* 9.6 Write property test for return creates new cost layer (never re-opens)
    - **Property 15: Return Creates New Cost Layer (Never Re-opens)**
    - **Validates: Requirements 5.12, 5.13, 5.14**

  - [x] 9.7 Implement sequential invoice number generation
    - Create thread-safe sequential invoice number generator using database sequence or advisory lock
    - _Requirements: 5.5_

  - [x]* 9.8 Write property test for sequential invoice numbers
    - **Property 23: Sequential Invoice Numbers**
    - **Validates: Requirements 5.5**

  - [x] 9.9 Create sales router with endpoints
    - Create `backend/app/routers/sales.py` with GET/POST /api/v1/sales, POST /confirm, POST /return
    - Create `backend/app/schemas/sale.py` with request/response models
    - _Requirements: 5.1, 5.3, 5.4_

- [x] 10. Customer and credit management
  - [x] 10.1 Create Customer model and customer service
    - Create `backend/app/models/customer.py` with name, phone, email, address, tax_id, credit_limit, account_status
    - Create `backend/app/services/customer_service.py` with CRUD and purchase history
    - Create `backend/app/routers/customers.py` with GET/POST endpoints
    - Create `backend/app/schemas/customer.py` with Pydantic models
    - _Requirements: 6.1, 6.2_

  - [x] 10.2 Create Customer_Credit_Ledger model and credit ledger service
    - Create `backend/app/models/customer_credit_ledger.py` with customer_id, transaction_type (sale/payment/adjustment/return), amount, reference_type, reference_id, notes, created_by
    - Create `backend/app/services/credit_ledger_service.py` with record_debit, record_credit, validate_credit_limit, calculate_balance, aging_analysis
    - Implement credit limit enforcement at database transaction layer using pessimistic lock on customer record
    - _Requirements: 5.4, 6.3, 6.4, 7.1, 7.2, 7.5, 7.7, 7.8, 7.9_

  - [x]* 10.3 Write property test for ledger-derived customer balance
    - **Property 2: Ledger-Derived Customer Balance**
    - **Validates: Requirements 1.3, 6.4**

  - [x]* 10.4 Write property test for credit limit enforcement
    - **Property 16: Credit Limit Enforcement**
    - **Validates: Requirements 7.2, 7.7, 7.8, 7.9**

  - [x]* 10.5 Write property test for aging analysis bucketing
    - **Property 17: Aging Analysis Bucketing**
    - **Validates: Requirements 7.3**

  - [x]* 10.6 Write property test for credit ledger round-trip
    - **Property 18: Credit Ledger Round-Trip**
    - **Validates: Requirements 7.6**

  - [x] 10.7 Create credit router with payment and adjustment endpoints
    - Create `backend/app/routers/credit.py` with POST /api/v1/credit/payments, POST /api/v1/credit/adjustments
    - Create GET /api/v1/customers/{id}/ledger and GET /api/v1/customers/{id}/aging
    - _Requirements: 6.3, 7.1, 7.3, 7.5_

- [x] 11. Supplier and purchasing
  - [x] 11.1 Create Supplier model and supplier service
    - Create `backend/app/models/supplier.py` with name, contact_person, phone, email, address, tax_id, payment_terms, account_status
    - Create `backend/app/services/supplier_service.py` with CRUD, balance calculation, aging analysis
    - Create `backend/app/routers/suppliers.py` and `backend/app/schemas/supplier.py`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 11.2 Write property test for ledger-derived supplier balance
    - **Property 3: Ledger-Derived Supplier Balance**
    - **Validates: Requirements 1.4, 8.3, 8.5**

  - [x] 11.3 Create PurchaseOrder and PurchaseOrderItem models
    - Create `backend/app/models/purchase_order.py` with supplier_id, status (draft/approved/ordered/partially_received/received/cancelled), total_amount, notes, approved_by
    - Create purchase_order_items table with quantity_ordered, quantity_received, unit_cost
    - _Requirements: 9.1, 9.2, 9.8_

  - [x] 11.4 Implement purchase service with PO lifecycle and GRN processing
    - Create `backend/app/services/purchase_service.py` with create_po, approve_po, receive_goods, cancel_po
    - Create `backend/app/models/goods_receipt_note.py` and `backend/app/models/grn_items.py`
    - Implement GRN confirmation: update PO state, add received quantities to location via ledger, create cost layers per GRN line item
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x]* 11.5 Write property test for GRN creates cost layers
    - **Property 5: GRN Creates Cost Layers**
    - **Validates: Requirements 1.9**

  - [x]* 11.6 Write property test for purchase order total
    - **Property 27: Purchase Order Total**
    - **Validates: Requirements 9.8**

  - [x] 11.7 Create purchase router with endpoints
    - Create `backend/app/routers/purchases.py` with GET/POST /api/v1/purchase-orders, POST /approve, POST /receive, POST /cancel
    - Create `backend/app/schemas/purchase_order.py` and `backend/app/schemas/grn.py`
    - _Requirements: 9.1, 9.3, 9.4, 9.7_

- [x] 12. Checkpoint - Ensure sales, credit, and purchasing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Barcode management
  - [x] 13.1 Implement barcode service with generation and scanning
    - Create `backend/app/services/barcode_service.py` with generate_barcode (Code 128), decode_barcode, and lookup functions
    - Create `backend/app/utils/barcode_generator.py` using python-barcode library
    - Support both manufacturer-provided and system-generated barcodes
    - Implement barcode lookup within 500ms performance target
    - Create `backend/app/routers/barcodes.py` with GET /api/v1/spare-parts/{id}/barcode
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x]* 13.2 Write property test for barcode encode-decode round-trip
    - **Property 19: Barcode Encode-Decode Round-Trip**
    - **Validates: Requirements 10.6**

- [x] 14. Inventory audits
  - [x] 14.1 Create audit models (AuditSession, AuditSnapshotItem, AuditCount)
    - Create `backend/app/models/audit_session.py` with location_id, audit_type (cycle_count/full_stock_count), status, snapshot_timestamp, initiated_by, approved_by
    - Create audit_snapshot_items table with session_id, spare_part_id, snapshot_quantity
    - Create audit_counts table with session_id, spare_part_id, counted_quantity, variance, counted_by
    - _Requirements: 11.1, 11.2_

  - [x] 14.2 Implement audit service with snapshot-based pattern
    - Create `backend/app/services/audit_service.py` with initiate_audit (captures Stock_Status_Cache snapshot), submit_count (calculates variance against snapshot), complete_audit (creates adjustment ledger entries)
    - Implement reconciliation view showing post-snapshot movements
    - Implement re-count flagging for movements during active audit
    - _Requirements: 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10_

  - [x]* 14.3 Write property test for audit snapshot isolation
    - **Property 21: Audit Snapshot Isolation**
    - **Validates: Requirements 11.7, 11.8, 11.9**

  - [x]* 14.4 Write property test for audit adjustment correctness
    - **Property 22: Audit Adjustment Correctness**
    - **Validates: Requirements 11.4**

  - [x] 14.5 Create audit router with endpoints
    - Create `backend/app/routers/audits.py` with GET/POST /api/v1/audits, POST /counts, POST /approve
    - Create `backend/app/schemas/audit.py` with request/response models
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 15. Reporting and dashboard
  - [x] 15.1 Implement report service
    - Create `backend/app/services/report_service.py` with generate_sales_report, generate_inventory_report, generate_customer_report, generate_supplier_report, generate_financial_summary
    - Implement date range filtering, location/salesperson/customer/category filters
    - Implement PDF and CSV export using WeasyPrint and csv module
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 15.2 Implement dashboard service with KPI widgets
    - Create `backend/app/services/dashboard_service.py` with KPI queries: total sales today/month, outstanding receivables, low stock count, pending POs, top selling products
    - Implement role-based KPI visibility (Salesperson sees sales only, Manager/Admin sees all)
    - Ensure all KPI data loads within 3 seconds
    - _Requirements: 13.1, 13.2, 13.4_

  - [x] 15.3 Create report and dashboard routers
    - Create `backend/app/routers/reports.py` with GET /api/v1/reports/{type}
    - Create `backend/app/routers/dashboard.py` with GET /api/v1/dashboard/kpis
    - _Requirements: 12.1, 13.1_

- [x] 16. Invoice management
  - [x] 16.1 Implement invoice service with PDF generation and QR codes
    - Create `backend/app/services/invoice_service.py` with generate_invoice_pdf
    - Create `backend/app/utils/pdf_generator.py` using WeasyPrint for A4 and thermal (80mm) formats
    - Embed QR code (invoice number + total amount) and barcode on each invoice
    - Include company logo, details, line items, totals, payment terms, status
    - Store generated PDF for future retrieval
    - Create `backend/app/models/invoice.py` with sale_id, invoice_number, pdf_data, format
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x]* 16.2 Write property test for invoice QR code round-trip
    - **Property 20: Invoice QR Code Round-Trip**
    - **Validates: Requirements 14.6**

  - [x] 16.3 Create invoice router
    - Create `backend/app/routers/invoices.py` with GET /api/v1/invoices/{id}/pdf
    - _Requirements: 14.5_

- [x] 17. Notifications
  - [x] 17.1 Create notification model and service
    - Create `backend/app/models/notification.py` with user_id, notification_type, title, message, metadata (JSON), is_read, read_at
    - Create `backend/app/services/notification_service.py` with create_notification, mark_read, mark_all_read, get_user_notifications
    - Implement trigger hooks: low stock alert, credit limit exceeded, overdue customer (90+ days), pending approval reminder (24+ hours)
    - _Requirements: 3.3, 7.4, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [x]* 17.2 Write property test for low stock notification trigger
    - **Property 26: Low Stock Notification Trigger**
    - **Validates: Requirements 3.3, 16.1**

  - [x] 17.3 Create notification router
    - Create `backend/app/routers/notifications.py` with GET /api/v1/notifications, POST /mark-read
    - _Requirements: 16.5, 16.6_

- [x] 18. Audit trail
  - [x] 18.1 Create audit trail model and service
    - Create `backend/app/models/audit_trail.py` with user_id, action_type, entity_type, entity_id, old_values (JSON), new_values (JSON), ip_address, created_at
    - Create `backend/app/services/audit_trail_service.py` with record_event and query methods
    - Implement append-only enforcement (no UPDATE or DELETE allowed via application layer and DB trigger/policy)
    - Support querying by user, entity_type, entity_id, action_type, date_range
    - Integrate with all critical operations (login/logout, CRUD, approvals, payments, stock adjustments)
    - _Requirements: 2.6, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [x]* 18.2 Write property test for audit trail immutability
    - **Property 24: Audit Trail Immutability**
    - **Validates: Requirements 15.6**

- [x] 19. Checkpoint - Ensure all backend services pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Performance optimization
  - [x] 20.1 Implement indexing strategy via Alembic migration
    - Create migration applying all performance indexes from design: partial unique indexes for soft-delete, composite indexes on ledger, partial index on cost_layers, credit_ledger index, audit_trail index, notifications index, transfers status index
    - _Requirements: 18.5, 18.7, 18.8, 18.9, 18.10_

  - [x] 20.2 Implement periodic reconciliation job
    - Create reconciliation function that compares Stock_Status_Cache against Inventory_Movement_Ledger sums, corrects drift, and generates admin notifications
    - Implement as an async background task or periodic scheduler
    - _Requirements: 18.4, 18.6_

- [x] 21. Property-based test infrastructure and remaining tests
  - [x] 21.1 Set up Hypothesis testing framework and shared fixtures
    - Create `backend/tests/conftest.py` with async test database setup, session fixtures, and factory functions
    - Create `backend/tests/property/conftest.py` with Hypothesis custom strategies (cost_layers, credit_entries, passwords, sale_line_items)
    - Configure pytest with hypothesis settings (max_examples=100)
    - _Requirements: 1.5, 1.10, 3.7_

  - [x]* 21.2 Write property tests for FIFO and ledger properties (test_fifo_properties.py)
    - Create `backend/tests/property/test_fifo_properties.py` containing:
    - **Property 1: FIFO Consumption Order**
    - **Property 10: Transfer Source Deduction and Destination Creation** (if not covered by 7.4)
    - **Property 12: Transfer Quantity Validation** (if not covered by 7.6)
    - **Property 15: Return Creates New Cost Layer** (if not covered by 9.6)
    - **Validates: Requirements 1.5, 1.10, 3.7, 4.5, 4.6, 4.9, 4.10, 4.11, 4.12, 5.12, 5.13, 5.14**

  - [x]* 21.3 Write property tests for ledger balance properties (test_ledger_properties.py)
    - Create `backend/tests/property/test_ledger_properties.py` containing:
    - **Property 2: Ledger-Derived Customer Balance**
    - **Property 3: Ledger-Derived Supplier Balance**
    - **Property 6: Double-Entry Balance**
    - **Property 7: Stock Cache Equals Ledger Sum**
    - **Property 14: Sale Stock Deduction via Ledger**
    - **Validates: Requirements 1.3, 1.4, 1.7, 3.6, 5.2, 6.4, 8.3, 8.5, 18.2**

  - [x]* 21.4 Write property tests for credit properties (test_credit_properties.py)
    - Create `backend/tests/property/test_credit_properties.py` containing:
    - **Property 16: Credit Limit Enforcement**
    - **Property 17: Aging Analysis Bucketing**
    - **Property 18: Credit Ledger Round-Trip**
    - **Validates: Requirements 7.2, 7.3, 7.6, 7.7, 7.8, 7.9**

  - [x]* 21.5 Write property tests for round-trip properties (test_roundtrip_properties.py)
    - Create `backend/tests/property/test_roundtrip_properties.py` containing:
    - **Property 19: Barcode Encode-Decode Round-Trip**
    - **Property 20: Invoice QR Code Round-Trip**
    - **Validates: Requirements 10.6, 14.6**

  - [x]* 21.6 Write property tests for audit properties (test_audit_properties.py)
    - Create `backend/tests/property/test_audit_properties.py` containing:
    - **Property 21: Audit Snapshot Isolation**
    - **Property 22: Audit Adjustment Correctness**
    - **Property 24: Audit Trail Immutability**
    - **Validates: Requirements 11.4, 11.7, 11.8, 11.9, 15.6**

  - [x]* 21.7 Write property tests for validation properties (test_validation_properties.py)
    - Create `backend/tests/property/test_validation_properties.py` containing:
    - **Property 4: Soft Delete Preserves Data**
    - **Property 8: Password Complexity Validation**
    - **Property 9: Unique Part Number and Barcode**
    - **Property 13: Sale Line Total Calculation**
    - **Property 23: Sequential Invoice Numbers**
    - **Property 25: RBAC Endpoint Enforcement**
    - **Property 26: Low Stock Notification Trigger**
    - **Property 27: Purchase Order Total**
    - **Validates: Requirements 1.2, 2.5, 3.2, 3.3, 5.5, 5.7, 9.8, 16.1, 17.1, 18.5**

  - [x]* 21.8 Write property tests for transfer properties (test_transfer_properties.py)
    - Create `backend/tests/property/test_transfer_properties.py` containing:
    - **Property 10: Transfer Source Deduction and Destination Creation**
    - **Property 11: In-Transit Stock Unavailability**
    - **Validates: Requirements 4.5, 4.6, 4.7, 4.10, 4.12**

- [x] 22. Checkpoint - Ensure all property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 23. Frontend setup and shared infrastructure
  - [x] 23.1 Initialize Next.js project with TypeScript and Tailwind CSS
    - Create `frontend/` with Next.js 14 App Router, TypeScript, Tailwind CSS configuration
    - Create `frontend/src/lib/api.ts` with Axios client, JWT auth interceptors, token refresh logic
    - Create `frontend/src/lib/auth.ts` with JWT token storage and management
    - Create `frontend/src/lib/types.ts` with TypeScript interfaces matching backend schemas
    - Create `frontend/src/hooks/useAuth.ts` for authentication state management
    - _Requirements: 2.2, 2.3, 17.1_

  - [x] 23.2 Create shared UI components and layout
    - Create `frontend/src/components/Layout.tsx` with sidebar navigation, header, and role-based menu items
    - Create shared components: DataTable, Modal, Form, Button, Input, Select, Badge, Alert
    - Implement responsive design with Tailwind CSS
    - _Requirements: 13.4_

- [x] 24. Frontend authentication pages
  - [x] 24.1 Create login and password reset pages
    - Create `frontend/src/app/(auth)/login/page.tsx` with login form, error handling, redirect
    - Create `frontend/src/app/(auth)/reset-password/page.tsx` with reset flow
    - Implement token storage and automatic refresh
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 25. Frontend dashboard and inventory pages
  - [x] 25.1 Create dashboard page with KPI widgets
    - Create `frontend/src/app/(dashboard)/dashboard/page.tsx` with role-based KPI cards
    - Implement 5-minute auto-refresh for KPI data
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 25.2 Create inventory management pages
    - Create `frontend/src/app/(dashboard)/inventory/page.tsx` with spare parts list, search, filters
    - Create spare part detail/edit pages with all attributes
    - Create category management UI
    - Implement stock level display per location
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6_

- [x] 26. Frontend sales and customer pages
  - [x] 26.1 Create sales pages
    - Create `frontend/src/app/(dashboard)/sales/page.tsx` with sales list, create sale form
    - Implement line item addition with part search, quantity, discount
    - Implement sale confirmation flow with stock validation feedback
    - Create returns processing page
    - _Requirements: 5.1, 5.3, 5.4, 5.6, 5.7, 5.8_

  - [x] 26.2 Create customer pages with credit management
    - Create `frontend/src/app/(dashboard)/customers/page.tsx` with customer list and CRUD
    - Create customer detail page with purchase history, credit ledger, aging analysis
    - Implement payment recording and adjustment forms
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.3, 7.5_

- [x] 27. Frontend supplier, purchasing, and transfer pages
  - [x] 27.1 Create supplier and purchase order pages
    - Create `frontend/src/app/(dashboard)/suppliers/page.tsx` with supplier list and CRUD
    - Create `frontend/src/app/(dashboard)/purchases/page.tsx` with PO list, create, approve, receive flows
    - Implement GRN recording form
    - _Requirements: 8.1, 8.2, 9.1, 9.2, 9.3, 9.4, 9.6_

  - [x] 27.2 Create transfer management pages
    - Create `frontend/src/app/(dashboard)/transfers/page.tsx` with transfer list, create, approve, receive flows
    - Show transfer status with state transitions
    - _Requirements: 4.2, 4.4, 4.5, 4.6_

- [x] 28. Frontend audit, reports, and settings pages
  - [x] 28.1 Create audit pages
    - Create `frontend/src/app/(dashboard)/audits/page.tsx` with audit session list, initiate, count submission, reconciliation view, approval
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.10_

  - [x] 28.2 Create reports pages
    - Create `frontend/src/app/(dashboard)/reports/page.tsx` with report type selection, date range filters, export buttons (PDF/CSV)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 28.3 Create settings and user management pages
    - Create `frontend/src/app/(dashboard)/settings/page.tsx` with user management (Admin), notification preferences, and session management
    - _Requirements: 2.1, 16.5, 16.6, 17.6_

- [x] 29. Final checkpoint - Full system integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- Property tests validate all 27 correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- The backend uses Python with FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, and Redis
- The frontend uses Next.js 14 with TypeScript and Tailwind CSS
- All inventory and financial operations use atomic transactions with pessimistic locking
- The immutable ledger pattern means Stock_Status_Cache is always derivable from Inventory_Movement_Ledger
- Hypothesis library is used for property-based testing with minimum 100 examples per test

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["2.5", "2.6", "3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3"] },
    { "id": 5, "tasks": ["3.4", "3.5", "3.6"] },
    { "id": 6, "tasks": ["5.1", "5.2"] },
    { "id": 7, "tasks": ["6.1", "6.2"] },
    { "id": 8, "tasks": ["6.3", "6.4"] },
    { "id": 9, "tasks": ["6.5", "6.6", "7.1"] },
    { "id": 10, "tasks": ["7.2", "7.3"] },
    { "id": 11, "tasks": ["7.4", "7.5", "7.6", "7.7"] },
    { "id": 12, "tasks": ["9.1", "10.1"] },
    { "id": 13, "tasks": ["9.2", "10.2"] },
    { "id": 14, "tasks": ["9.3", "9.4", "9.5", "10.3", "10.4"] },
    { "id": 15, "tasks": ["9.6", "9.7", "10.5", "10.6", "10.7"] },
    { "id": 16, "tasks": ["9.8", "9.9", "11.1"] },
    { "id": 17, "tasks": ["11.2", "11.3"] },
    { "id": 18, "tasks": ["11.4"] },
    { "id": 19, "tasks": ["11.5", "11.6", "11.7"] },
    { "id": 20, "tasks": ["13.1"] },
    { "id": 21, "tasks": ["13.2", "14.1"] },
    { "id": 22, "tasks": ["14.2"] },
    { "id": 23, "tasks": ["14.3", "14.4", "14.5"] },
    { "id": 24, "tasks": ["15.1", "15.2"] },
    { "id": 25, "tasks": ["15.3", "16.1"] },
    { "id": 26, "tasks": ["16.2", "16.3", "17.1"] },
    { "id": 27, "tasks": ["17.2", "17.3", "18.1"] },
    { "id": 28, "tasks": ["18.2", "20.1", "20.2"] },
    { "id": 29, "tasks": ["21.1"] },
    { "id": 30, "tasks": ["21.2", "21.3", "21.4", "21.5", "21.6", "21.7", "21.8"] },
    { "id": 31, "tasks": ["23.1"] },
    { "id": 32, "tasks": ["23.2", "24.1"] },
    { "id": 33, "tasks": ["25.1", "25.2"] },
    { "id": 34, "tasks": ["26.1", "26.2"] },
    { "id": 35, "tasks": ["27.1", "27.2"] },
    { "id": 36, "tasks": ["28.1", "28.2", "28.3"] }
  ]
}
```
