# Requirements Document

## Introduction

The Auto Spare Parts ERP System is a comprehensive enterprise resource planning solution designed for automotive spare parts distributors and retailers. The system digitizes inventory management, sales processing, customer credit management, supplier management, purchasing, and reporting — replacing manual spreadsheets and paper records with a scalable, auditable platform.

The system supports 1,000–10,000 spare parts across multiple warehouse/store locations, 5–20 concurrent users, 20–100 daily sales transactions, and multi-year transaction history exceeding 100,000 sales records. The architecture is future-ready for multi-company, multi-currency, general ledger integration, e-commerce, and mobile applications.

Technology stack: Python FastAPI backend with SQLAlchemy 2.0 and PostgreSQL, Next.js frontend with TypeScript and Tailwind CSS, JWT-based authentication, Docker deployment, PDF invoice generation, and barcode support.

## Glossary

- **ERP_System**: The Auto Spare Parts ERP application encompassing all modules
- **User_Manager**: The module responsible for user authentication, authorization, and role management
- **Inventory_Manager**: The module responsible for spare parts master data and stock level tracking
- **Location_Manager**: The module responsible for multi-location inventory, transfers, and movement ledger
- **Sales_Manager**: The module responsible for processing sales transactions and generating invoices
- **Customer_Manager**: The module responsible for customer profiles, purchase history, and credit management
- **Credit_Ledger**: The module responsible for tracking customer credit transactions, balances, and aging analysis
- **Supplier_Manager**: The module responsible for supplier profiles, purchase history, and outstanding balances
- **Purchase_Manager**: The module responsible for purchase orders and goods receipt processing
- **Barcode_Manager**: The module responsible for barcode generation, printing, and scanning
- **Audit_Manager**: The module responsible for inventory audits, cycle counts, and variance tracking
- **Report_Manager**: The module responsible for generating sales, inventory, customer, supplier, and financial reports
- **Dashboard_Manager**: The module responsible for executive dashboard and KPI widget display
- **Invoice_Manager**: The module responsible for PDF invoice generation in A4 and thermal formats
- **Audit_Trail**: The module responsible for recording all critical system events with full context
- **Notification_Manager**: The module responsible for alerts on low stock, credit limits, overdue accounts, and pending approvals
- **Security_Manager**: The module responsible for JWT authentication, RBAC enforcement, rate limiting, and session management
- **Admin**: A user role with full system access including configuration and user management
- **Manager**: A user role with access to approvals, reports, and operational oversight
- **Salesperson**: A user role limited to sales processing, customer lookup, and invoice generation
- **Storekeeper**: A user role limited to inventory operations, stock counts, and transfer management
- **Spare_Part**: A product record containing part number, barcode, brand, category, vehicle compatibility, pricing, and stock levels
- **Inventory_Movement_Ledger**: A chronological record of every stock quantity change with source, destination, reason, and reference
- **Customer_Credit_Ledger**: A chronological record of all credit transactions including sales, payments, adjustments, and returns
- **Purchase_Order**: A document tracking the lifecycle of a supplier order through draft, approved, ordered, received, and cancelled states
- **Goods_Receipt_Note**: A document recording the physical receipt of goods against a purchase order
- **Soft_Delete**: A deletion method that marks records as inactive without physical removal from the database
- **Aging_Analysis**: A report categorizing outstanding balances by time periods (current, 30, 60, 90, 120+ days)
- **Cost_Layer**: A record representing the cost and remaining unconsumed quantity of a specific batch of inventory received at a given unit cost
- **FIFO**: First-In, First-Out inventory valuation method where the oldest cost layers are consumed first when calculating cost of goods sold
- **In_Transit**: An inventory state representing stock that has been dispatched from a source location but not yet received at the destination location
- **Stock_Status_Cache**: A materialized table maintaining the current aggregated stock quantity per Spare_Part per location for performant read operations
- **Pessimistic_Lock**: A database-level lock (SELECT FOR UPDATE) that prevents concurrent modification of the same record until the holding transaction completes

## Requirements

### Requirement 1: Accounting Foundation

**User Story:** As a business owner, I want all financial transactions to be auditable and support future accounting integration, so that the system can scale to a full general ledger without data migration.

#### Acceptance Criteria

1. THE ERP_System SHALL include id, created_at, updated_at, created_by, and updated_by columns on every database table
2. WHEN a financial record is deleted, THE ERP_System SHALL perform a Soft_Delete by setting a deleted_at timestamp and deleted_by user reference instead of physically removing the record
3. THE ERP_System SHALL maintain accounts receivable balances derived from the Customer_Credit_Ledger
4. THE ERP_System SHALL maintain accounts payable balances derived from supplier purchase and payment records
5. WHEN a sale is completed, THE ERP_System SHALL calculate cost of goods sold using the FIFO inventory valuation method by consuming the oldest available Cost_Layers first
6. THE ERP_System SHALL track inventory valuation by maintaining unit cost on each stock movement record
7. WHEN a financial transaction is recorded, THE ERP_System SHALL store a double-entry reference linking the debit and credit sides for future general ledger integration
8. THE ERP_System SHALL maintain Cost_Layers per Spare_Part per location, where each Cost_Layer records the unit cost, original quantity received, and remaining unconsumed quantity
9. WHEN a Goods_Receipt_Note is confirmed, THE ERP_System SHALL create a new Cost_Layer for each line item recording the unit cost and received quantity at the receiving location
10. WHEN cost of goods sold is calculated for a sale, THE ERP_System SHALL consume quantities from Cost_Layers in chronological order of receipt date starting with the oldest layer with remaining quantity

### Requirement 2: User Management and Authentication

**User Story:** As an administrator, I want to manage user accounts with role-based access control, so that each user has appropriate permissions for their job function.

#### Acceptance Criteria

1. THE User_Manager SHALL support four roles: Admin, Manager, Salesperson, and Storekeeper
2. WHEN a user logs in with valid credentials, THE Security_Manager SHALL issue a JWT access token with a configurable expiration time and a refresh token with a longer expiration time
3. WHEN a JWT access token expires, THE Security_Manager SHALL allow the user to obtain a new access token using a valid refresh token without re-entering credentials
4. WHEN a user requests a password reset, THE User_Manager SHALL generate a time-limited reset token and invalidate any previous reset tokens for that user
5. THE User_Manager SHALL enforce password complexity requirements including minimum length of 8 characters, at least one uppercase letter, one lowercase letter, and one digit
6. WHEN a user performs any create, update, or delete operation, THE Audit_Trail SHALL record the user identity, action type, timestamp, affected entity, and old and new values
7. THE Security_Manager SHALL hash all passwords using bcrypt with a minimum cost factor of 12 before storage
8. WHEN more than 5 failed login attempts occur for a single user account within 15 minutes, THE Security_Manager SHALL lock the account for 30 minutes

### Requirement 3: Inventory Management

**User Story:** As a storekeeper, I want to manage a master catalog of spare parts with detailed attributes, so that I can quickly find parts and track stock accurately.

#### Acceptance Criteria

1. THE Inventory_Manager SHALL store each Spare_Part with the following attributes: part number, barcode, name, description, brand, category, subcategory, vehicle compatibility list, unit of measure, cost price, selling price, minimum stock level, maximum stock level, and reorder quantity
2. THE Inventory_Manager SHALL enforce unique constraints on part number and barcode within the system
3. WHEN a Spare_Part stock level falls below the minimum stock level, THE Notification_Manager SHALL generate a low stock alert
4. THE Inventory_Manager SHALL support hierarchical categorization with categories and subcategories for spare parts
5. WHEN a user searches for a Spare_Part, THE Inventory_Manager SHALL support search by part number, barcode, name, brand, category, and vehicle compatibility
6. THE Inventory_Manager SHALL maintain current stock quantity per Spare_Part per location derived from the Inventory_Movement_Ledger
7. THE Inventory_Manager SHALL support the FIFO inventory valuation method where Cost_Layers are consumed in chronological order of goods receipt date

### Requirement 4: Multi-Location Inventory

**User Story:** As a manager, I want to track inventory across multiple warehouses and store locations, so that I can optimize stock distribution and fulfill orders from the nearest location.

#### Acceptance Criteria

1. THE Location_Manager SHALL support defining multiple storage locations including warehouses and retail branches
2. WHEN stock moves between locations, THE Location_Manager SHALL require a transfer request specifying source location, destination location, Spare_Part, and quantity
3. WHILE a transfer request is in pending status, THE Location_Manager SHALL reserve the specified quantity at the source location to prevent overselling
4. THE Location_Manager SHALL support the following transfer states: pending, approved, in-transit, received, and cancelled
5. WHEN a Manager or Admin approves a transfer request, THE Location_Manager SHALL deduct quantity from the source location and record it in the In_Transit state by creating appropriate entries in the Inventory_Movement_Ledger
6. WHEN a transfer is received at the destination, THE Location_Manager SHALL deduct quantity from the In_Transit state and add it to the destination location by creating appropriate entries in the Inventory_Movement_Ledger
7. WHILE stock is in In_Transit state, THE Location_Manager SHALL NOT make that stock available for sale at either the source or the destination location
8. WHEN any stock quantity change occurs, THE Location_Manager SHALL record an entry in the Inventory_Movement_Ledger with timestamp, location, Spare_Part, quantity change, reason, reference document, and user
9. IF a transfer request specifies a quantity exceeding available stock at the source location, THEN THE Location_Manager SHALL reject the transfer request with an insufficient stock error
10. WHEN a transfer is received at the destination location, THE Location_Manager SHALL create a new Cost_Layer at the destination location using the unit cost from the originating Cost_Layer at the source location
11. WHEN a transfer consumes quantity from a source location, THE Location_Manager SHALL deduct the transferred quantity from the source location Cost_Layers using FIFO order
12. THE Location_Manager SHALL NOT move or modify Cost_Layers at the source location; instead it SHALL consume from source layers and create corresponding new layers at the destination

### Requirement 5: Sales Management

**User Story:** As a salesperson, I want to process sales transactions efficiently, so that I can serve customers quickly and maintain accurate inventory records.

#### Acceptance Criteria

1. WHEN creating a sale, THE Sales_Manager SHALL require selection of a customer, addition of one or more line items with Spare_Part, quantity, and optional discount, and specification of payment type as cash or credit
2. WHEN a sale is confirmed, THE Sales_Manager SHALL reduce stock quantity at the selling location for each line item by recording entries in the Inventory_Movement_Ledger
3. WHEN a cash sale is confirmed, THE Sales_Manager SHALL record the payment amount and mark the sale as fully paid
4. WHEN a credit sale is confirmed, THE Credit_Ledger SHALL record a debit entry against the customer account for the sale total
5. WHEN a sale is confirmed, THE Invoice_Manager SHALL generate a unique sequential invoice number for the transaction
6. IF a sale line item specifies a quantity exceeding available stock at the selling location, THEN THE Sales_Manager SHALL reject the line item with an insufficient stock error
7. WHEN a sale is confirmed, THE Sales_Manager SHALL calculate the line item total as quantity multiplied by unit price minus discount amount for each line item
8. THE Sales_Manager SHALL support sales returns by creating a return transaction that reverses inventory and financial entries
9. WHEN a sale is confirmed, THE Sales_Manager SHALL acquire a Pessimistic_Lock on the location-specific stock records for each line item before performing stock validation and deduction
10. THE Sales_Manager SHALL perform stock validation and stock deduction within the same database transaction to prevent race conditions
11. IF concurrent transactions target the same stock record simultaneously, THEN THE Sales_Manager SHALL allow only one transaction to succeed and SHALL return an insufficient stock error to the other transactions
12. WHEN a sales return is processed, THE Sales_Manager SHALL create a new Cost_Layer at the return location using the unit cost recorded on the original sale line item
13. WHEN a sales return creates a new Cost_Layer, THE Sales_Manager SHALL set the Cost_Layer timestamp to the return processing date rather than the original receipt date
14. THE Sales_Manager SHALL NOT modify or re-open any previously consumed or closed Cost_Layers when processing a return

### Requirement 6: Customer Management

**User Story:** As a salesperson, I want to maintain customer profiles with complete purchase and payment history, so that I can provide personalized service and manage credit relationships.

#### Acceptance Criteria

1. THE Customer_Manager SHALL store customer profiles with: name, phone number, email, address, tax identification number, credit limit, and account status
2. THE Customer_Manager SHALL maintain a complete purchase history for each customer including all sales transactions, dates, amounts, and payment status
3. WHEN a customer payment is received, THE Credit_Ledger SHALL record a credit entry against the customer account reducing the outstanding balance
4. THE Customer_Manager SHALL calculate the current customer balance as the sum of all debit and credit entries in the Customer_Credit_Ledger for that customer

### Requirement 7: Customer Credit Ledger

**User Story:** As a manager, I want a complete ledger of all customer credit transactions, so that I can monitor outstanding balances, enforce credit limits, and follow up on overdue accounts.

#### Acceptance Criteria

1. THE Credit_Ledger SHALL record entries for the following transaction types: sale, payment, adjustment, and return
2. WHEN a credit sale would cause the customer outstanding balance to exceed the customer credit limit, THE Credit_Ledger SHALL reject the transaction with a credit limit exceeded error
3. THE Credit_Ledger SHALL calculate aging analysis for each customer categorizing outstanding amounts into current, 1–30 days, 31–60 days, 61–90 days, and over 90 days overdue
4. WHEN a customer has any balance in the over 90 days overdue category, THE Notification_Manager SHALL generate an overdue customer alert
5. THE Credit_Ledger SHALL support manual adjustments with a required reason field and Manager or Admin authorization
6. FOR ALL entries in the Customer_Credit_Ledger, parsing then printing then parsing the ledger balance SHALL produce an equivalent balance (round-trip property)
7. THE Credit_Ledger SHALL enforce credit limit validation at the database transaction layer whenever a debit entry is written to the Customer_Credit_Ledger regardless of the entry source
8. WHEN a manual adjustment increases a customer outstanding balance, THE Credit_Ledger SHALL enforce credit limit validation and reject the adjustment if the resulting balance would exceed the customer credit limit
9. THE Credit_Ledger SHALL validate credit limits at transaction confirmation time rather than at draft creation time to account for concurrent transactions

### Requirement 8: Supplier Management

**User Story:** As a purchasing manager, I want to manage supplier profiles and track outstanding balances, so that I can maintain supplier relationships and manage cash flow.

#### Acceptance Criteria

1. THE Supplier_Manager SHALL store supplier profiles with: name, contact person, phone number, email, address, tax identification number, payment terms, and account status
2. THE Supplier_Manager SHALL maintain a complete purchase history for each supplier including all purchase orders, goods receipts, dates, and amounts
3. THE Supplier_Manager SHALL calculate the current supplier balance as the sum of all purchase and payment entries for that supplier
4. THE Supplier_Manager SHALL calculate supplier aging analysis categorizing outstanding amounts into current, 1–30 days, 31–60 days, 61–90 days, and over 90 days overdue
5. WHEN a supplier payment is recorded, THE Supplier_Manager SHALL reduce the outstanding balance for that supplier by the payment amount

### Requirement 9: Purchasing

**User Story:** As a purchasing manager, I want to create and track purchase orders through their lifecycle, so that I can manage procurement efficiently and maintain accurate stock records.

#### Acceptance Criteria

1. THE Purchase_Manager SHALL support the following Purchase_Order states: draft, approved, ordered, partially received, received, and cancelled
2. WHEN a Purchase_Order is created, THE Purchase_Manager SHALL set the initial state to draft
3. WHEN a Manager or Admin approves a Purchase_Order, THE Purchase_Manager SHALL transition the state from draft to approved
4. WHEN goods are received against a Purchase_Order, THE Purchase_Manager SHALL create a Goods_Receipt_Note recording the received quantities per line item
5. WHEN a Goods_Receipt_Note is confirmed, THE Location_Manager SHALL add the received quantities to the specified location by recording entries in the Inventory_Movement_Ledger
6. WHEN a Goods_Receipt_Note is confirmed, THE Purchase_Manager SHALL update the Purchase_Order state to partially received or received based on whether all line items have been fully received
7. IF a Purchase_Order in ordered or partially received state is cancelled, THEN THE Purchase_Manager SHALL require a cancellation reason and Manager or Admin authorization
8. THE Purchase_Manager SHALL track the Purchase_Order total as the sum of line item quantities multiplied by unit costs

### Requirement 10: Barcode Management

**User Story:** As a storekeeper, I want to generate, print, and scan barcodes for spare parts, so that I can speed up inventory operations and reduce data entry errors.

#### Acceptance Criteria

1. THE Barcode_Manager SHALL generate unique system barcodes for Spare_Parts that do not have a manufacturer barcode
2. THE Barcode_Manager SHALL support storing both manufacturer-provided barcodes and system-generated barcodes for the same Spare_Part
3. WHEN a barcode is scanned, THE Barcode_Manager SHALL look up and return the associated Spare_Part record within 500 milliseconds
4. THE Barcode_Manager SHALL generate barcode labels in a printable format supporting standard label sizes
5. WHEN a system barcode is generated, THE Barcode_Manager SHALL encode the barcode in Code 128 format
6. FOR ALL generated barcodes, encoding then decoding the barcode value SHALL produce the original Spare_Part identifier (round-trip property)

### Requirement 11: Inventory Audits

**User Story:** As a storekeeper, I want to conduct cycle counts and full stock counts, so that I can identify and correct discrepancies between physical stock and system records.

#### Acceptance Criteria

1. THE Audit_Manager SHALL support two audit types: cycle count for a subset of Spare_Parts, and full stock count for all Spare_Parts at a location
2. WHEN an audit is initiated, THE Audit_Manager SHALL create an audit session recording the audit type, location, date, and assigned users
3. WHEN a count is submitted for a Spare_Part, THE Audit_Manager SHALL calculate the variance as the difference between the counted quantity and the system quantity
4. WHEN an audit session is completed and variances are approved by a Manager or Admin, THE Audit_Manager SHALL create adjustment entries in the Inventory_Movement_Ledger to align system quantities with counted quantities
5. THE Audit_Manager SHALL maintain a history of all audit sessions with their variances and adjustment records
6. WHILE an audit session is in progress for a location, THE Audit_Manager SHALL flag any stock movements at that location as requiring re-count verification
7. WHEN an audit session is initiated, THE Audit_Manager SHALL capture a snapshot of system quantities for all Spare_Parts included in the audit at that exact timestamp
8. WHEN a variance is calculated, THE Audit_Manager SHALL compare the physical count against the snapshot quantity captured at audit initiation rather than the current system quantity
9. THE Audit_Manager SHALL exclude any Inventory_Movement_Ledger entries created after the audit snapshot timestamp from the initial variance calculation
10. THE Audit_Manager SHALL provide a reconciliation view showing all post-snapshot stock movements at the audited location for auditor review

### Requirement 12: Reporting

**User Story:** As a business owner, I want comprehensive reports on sales, inventory, customers, suppliers, and financial performance, so that I can make informed business decisions.

#### Acceptance Criteria

1. THE Report_Manager SHALL generate sales reports filterable by date range, location, salesperson, customer, and product category
2. THE Report_Manager SHALL generate inventory reports showing current stock levels, stock valuation, slow-moving items, and items below reorder level
3. THE Report_Manager SHALL generate customer reports showing purchase history, outstanding balances, and aging analysis
4. THE Report_Manager SHALL generate supplier reports showing purchase history, outstanding balances, and aging analysis
5. THE Report_Manager SHALL generate financial summary reports showing total sales revenue, cost of goods sold, gross margin, accounts receivable, and accounts payable for a specified period
6. WHEN a report is generated, THE Report_Manager SHALL support export in PDF and CSV formats
7. THE Report_Manager SHALL support date range filtering on all time-based reports with a minimum granularity of one day

### Requirement 13: Dashboard

**User Story:** As a manager, I want an executive dashboard with key performance indicators, so that I can monitor business health at a glance.

#### Acceptance Criteria

1. THE Dashboard_Manager SHALL display the following KPI widgets: total sales today, total sales this month, total outstanding receivables, low stock item count, pending purchase orders count, and top selling products for the current month
2. WHEN a user accesses the dashboard, THE Dashboard_Manager SHALL load all KPI data within 3 seconds for the default date range
3. THE Dashboard_Manager SHALL refresh KPI data automatically every 5 minutes without requiring a page reload
4. THE Dashboard_Manager SHALL restrict KPI visibility based on user role where Salesperson sees only sales KPIs and Manager and Admin see all KPIs

### Requirement 14: Invoice Management

**User Story:** As a salesperson, I want to generate and print professional invoices, so that customers receive clear documentation of their purchases.

#### Acceptance Criteria

1. THE Invoice_Manager SHALL generate PDF invoices containing: company logo, company details, invoice number, invoice date, customer details, line items with part number, description, quantity, unit price, discount, and line total, subtotal, tax amount, grand total, payment terms, and payment status
2. THE Invoice_Manager SHALL support two print formats: A4 full-page and thermal receipt (80mm width)
3. THE Invoice_Manager SHALL embed a QR code on each invoice containing the invoice number and total amount for verification
4. THE Invoice_Manager SHALL embed the invoice barcode for scanning and lookup
5. WHEN an invoice PDF is generated, THE Invoice_Manager SHALL store the PDF document for future retrieval
6. FOR ALL generated invoices, parsing the QR code embedded in the invoice SHALL produce the original invoice number and total amount (round-trip property)

### Requirement 15: Audit Trail

**User Story:** As an administrator, I want a complete audit trail of all critical system events, so that I can investigate issues, ensure compliance, and maintain accountability.

#### Acceptance Criteria

1. WHEN a critical event occurs, THE Audit_Trail SHALL record the following fields: timestamp, user identity, action type, affected entity type, affected entity identifier, old values, and new values
2. THE Audit_Trail SHALL classify the following as critical events: user login and logout, record creation, record update, record deletion, approval actions, payment transactions, and stock adjustments
3. THE Audit_Trail SHALL retain all records for a minimum of 7 years without automatic purging
4. WHEN an audit trail record is created, THE Audit_Trail SHALL store old values and new values as structured data enabling field-level change comparison
5. THE Audit_Trail SHALL support querying by user, entity type, entity identifier, action type, and date range
6. THE Audit_Trail SHALL be append-only and no user including Admin SHALL be able to modify or delete audit trail records

### Requirement 16: Notifications

**User Story:** As a manager, I want to receive alerts for critical business events, so that I can take timely action on low stock, overdue accounts, and pending approvals.

#### Acceptance Criteria

1. WHEN a Spare_Part stock level falls below the configured minimum stock level, THE Notification_Manager SHALL generate a low stock notification for Storekeeper and Manager roles
2. WHEN a customer outstanding balance exceeds the configured credit limit, THE Notification_Manager SHALL generate a credit limit exceeded notification for Manager and Admin roles
3. WHEN a customer has any balance overdue by more than 90 days, THE Notification_Manager SHALL generate an overdue customer notification for Manager and Admin roles
4. WHEN a transfer request or Purchase_Order is pending approval for more than 24 hours, THE Notification_Manager SHALL generate a pending approval reminder for Manager and Admin roles
5. THE Notification_Manager SHALL store all notifications with read and unread status per user
6. THE Notification_Manager SHALL support marking notifications as read individually or in bulk

### Requirement 17: Security and Access Control

**User Story:** As an administrator, I want comprehensive security controls, so that the system protects sensitive business data and prevents unauthorized access.

#### Acceptance Criteria

1. THE Security_Manager SHALL enforce role-based access control on every API endpoint based on the user role
2. THE Security_Manager SHALL apply rate limiting of 100 requests per minute per authenticated user and 20 requests per minute per unauthenticated IP address
3. THE Security_Manager SHALL maintain a session registry tracking all active refresh tokens per user
4. WHEN a user logs out, THE Security_Manager SHALL invalidate the current refresh token and remove the session from the session registry
5. THE Security_Manager SHALL record login history including timestamp, IP address, user agent, and login success or failure status
6. WHEN an Admin revokes a user session, THE Security_Manager SHALL immediately invalidate all refresh tokens for that user
7. THE Security_Manager SHALL enforce HTTPS for all API communications in production deployments
8. THE Security_Manager SHALL set secure HTTP headers including Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, and Strict-Transport-Security on all responses

### Requirement 18: Performance and Data Integrity

**User Story:** As a system administrator, I want the system to maintain data integrity under concurrent access and deliver fast query responses, so that users experience reliable performance during peak operations.

#### Acceptance Criteria

1. THE ERP_System SHALL maintain a Stock_Status_Cache table tracking current_quantity per Spare_Part per location
2. WHEN a new entry is appended to the Inventory_Movement_Ledger, THE ERP_System SHALL atomically update the Stock_Status_Cache within the same database transaction
3. WHEN stock quantity is queried for display or validation, THE ERP_System SHALL read from the Stock_Status_Cache for performance
4. THE ERP_System SHALL perform periodic reconciliation between the Stock_Status_Cache and the full Inventory_Movement_Ledger to detect and correct drift
5. WHEN a Soft_Delete is performed, THE ERP_System SHALL use partial unique indexes to ensure soft-deleted records do not conflict with unique constraints on active records
6. IF a reconciliation detects a mismatch between the Stock_Status_Cache and the Inventory_Movement_Ledger totals, THEN THE ERP_System SHALL log the discrepancy, correct the cache, and generate an alert for Admin users
7. THE ERP_System SHALL maintain a partial unique index on spare_parts for part_number and barcode columns restricted to records WHERE deleted_at IS NULL
8. THE ERP_System SHALL maintain a composite unique index on the Stock_Status_Cache table for spare_part_id and location_id columns
9. THE ERP_System SHALL maintain a composite index on the Inventory_Movement_Ledger for spare_part_id, location_id, and created_at columns to support cache reconciliation and audit snapshot queries
10. THE ERP_System SHALL maintain a partial composite index on cost_layers for spare_part_id, location_id, and created_at columns restricted to records WHERE remaining_quantity is greater than zero
