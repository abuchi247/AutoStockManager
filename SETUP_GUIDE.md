# StockPilot — Setup & Operations Guide (SOP)

A step-by-step guide for business owners setting up the system for the first time. Follow each phase in order.

---

## Phase 1: Start the System

```bash
cd /Users/abuchiobiegbu/Desktop/StockPilot
docker compose up --build -d
```

Wait 30 seconds, then get your admin password:

```bash
docker logs stockpilot-backend 2>&1 | grep "Temporary Password"
```

Open http://localhost:3000 and log in:
- **Username:** `admin`
- **Password:** (from the logs above)
- You'll be asked to set a new password — choose something strong (8+ chars, uppercase, lowercase, digit)

---

## Phase 2: Configure Your Business Profile (Admin)

**Where:** Settings → Business Profile tab

Do this FIRST — it controls what appears on every invoice.

| Field | What to enter | Example |
|-------|---------------|---------|
| Business Name | Your registered business name | Chidi Auto Parts Ltd |
| Email | Business email | info@chidiautoparts.com |
| Tax ID | TIN or VAT number | TIN-12345678 |
| Website | (optional) | www.chidiautoparts.com |
| Address | Full physical address | 15 Broad Street, Lagos Island, Lagos |
| Phone Numbers | Click "Add phone number" for each | Main: 08012345678, WhatsApp: 09087654321 |
| Bank Accounts | Click "Add bank account" for each | First Bank / 0123456789 / Chidi Auto Parts Ltd |
| Logo | Upload PNG or JPEG (max 500KB) | Your company logo |
| Invoice Footer | Payment terms or thank-you note | "Thank you for your patronage. Net 30 days." |

Click **Save Business Settings** when done.

---

## Phase 3: Create Locations (Admin)

**Where:** Locations → Add Location

You need at least ONE location before you can add stock. Create one per physical place you store/sell parts.

| Location Name | Type | Purpose |
|---------------|------|---------|
| Main Warehouse | Warehouse | Where bulk stock is stored |
| Ikeja Shop | Shop | Retail outlet where customers buy |
| Abuja Branch | Shop | Second retail outlet (if you have one) |

---

## Phase 4: Review Categories (Already Done Automatically)

**Where:** Categories

The system auto-creates 10 parent categories with 35 subcategories on first startup:

- Brakes (Brake Pads, Brake Discs, Brake Fluid)
- Filters (Oil Filters, Air Filters, Fuel Filters, Cabin Filters)
- Engine Parts (Pistons, Gaskets, Timing Belts, Spark Plugs)
- Electrical (Batteries, Alternators, Starters, Sensors)
- Suspension (Shock Absorbers, Springs, Control Arms)
- Body Parts (Bumpers, Fenders, Mirrors, Lights)
- Transmission (Clutch, Gearbox, CV Joints)
- Cooling (Radiators, Water Pumps, Thermostats, Hoses)
- Exhaust (Mufflers, Catalytic Converters, Exhaust Pipes)
- Fuel System (Fuel Pumps, Injectors, Fuel Lines)

Add any custom categories your business needs that aren't covered.

---

## Phase 5: Add Your First Spare Parts (Admin or Storekeeper)

**Where:** Inventory → Add Part

Add 3–5 parts to test with:

| Field | Example Part 1 | Example Part 2 |
|-------|----------------|----------------|
| Part Number | (auto-generated) | (auto-generated) |
| Name | Front Brake Pad Set | Oil Filter |
| Brand | Bosch | Mann |
| Category | Brakes → Brake Pads | Filters → Oil Filters |
| Unit of Measure | Set | PCS |
| Cost Price | 5000 | 1500 |
| Selling Price | 8500 | 3000 |
| Min Stock Level | 10 | 20 |
| Initial Stock Location | Main Warehouse | Main Warehouse |
| Initial Stock Quantity | 50 | 100 |

**Important:** Selling price must be ≥ cost price (the system enforces this).

---

## Phase 6: Create Staff Accounts (Admin)

**Where:** Settings → User Management → Create User

Create one account per role to test with:

| Username | Role | What they can do |
|----------|------|------------------|
| `manager1` | Manager | Approvals, reports, returns, profit view, supplier/PO management |
| `sales1` | Salesperson | Create sales, manage customers, record payments, generate invoices |
| `store1` | Storekeeper | Add parts, adjust stock, transfers, receive goods, audits |

**Password for all:** Use a temp password like `TempPass1!` — each user must change it on first login.

### What each role CAN and CANNOT do:

**Manager (sees everything except user management):**
- ✅ Approve purchase orders and transfers
- ✅ Process sales returns
- ✅ View profit summary and all reports
- ✅ Manage suppliers and purchase orders
- ✅ Credit adjustments
- ❌ Cannot create/edit users
- ❌ Cannot change business settings

**Salesperson (sales and customers only):**
- ✅ Create, confirm, and cancel sales
- ✅ Create and manage customers
- ✅ Record customer payments
- ✅ Generate and download invoices
- ✅ View inventory (read-only)
- ❌ Cannot adjust stock
- ❌ Cannot view reports or profit
- ❌ Cannot access suppliers, purchases, transfers, audits, categories, locations, settings

**Storekeeper (inventory and warehouse only):**
- ✅ Add and edit spare parts
- ✅ Adjust stock quantities
- ✅ Create and receive transfers
- ✅ Start and submit audits
- ✅ Receive purchase order goods (GRN)
- ✅ Manage locations
- ❌ Cannot make sales or manage customers
- ❌ Cannot view reports or profit
- ❌ Cannot access suppliers, purchases, categories, settings

---

## Phase 7: Test the Sales Workflow (as Salesperson)

Log out and log in as `sales1`.

### 7a. Add a customer

**Where:** Customers → Add Customer

| Field | Value |
|-------|-------|
| Name | Adekunle Motors |
| Phone | 08033445566 |
| Email | adekunle@motors.com |
| Credit Limit | 500000 |

### 7b. Create a cash sale

**Where:** Sales → Create Sale

1. Customer: Walk-in (cash customer)
2. Location: Ikeja Shop
3. Payment Type: Cash
4. Search "Brake" → add "Front Brake Pad Set" → quantity 2
5. Click **Save & Confirm**
6. The sale is confirmed, stock is deducted, invoice number is generated

### 7c. Create a credit sale

1. Customer: Adekunle Motors
2. Location: Ikeja Shop
3. Payment Type: Credit
4. Add "Oil Filter" → quantity 5
5. Amount Paid: 5000 (partial payment at checkout)
6. Click **Save & Confirm**
7. Check: customer's balance increased by (3000 × 5) − 5000 = 10,000

### 7d. Generate and download an invoice

1. Open the confirmed credit sale
2. Click **Generate Invoice** (choose A4 format)
3. Click **Download Invoice** — verify your business name, bank accounts, and logo appear

### 7e. Record a customer payment

1. Go to Customers → click "Adekunle Motors"
2. Open the **Credit Ledger** tab
3. Click **Record Payment** → enter 5000
4. Verify: balance reduced from 10,000 to 5,000

---

## Phase 8: Test the Purchase Workflow (as Manager)

Log out and log in as `manager1`.

### 8a. Add a supplier

**Where:** Suppliers → Add Supplier

| Field | Value |
|-------|-------|
| Name | Bosch Nigeria |
| Contact Person | Mr. Okafor |
| Phone | 08099887766 |
| Payment Terms | Net 30 |

### 8b. Create and approve a purchase order

**Where:** Purchases → Create PO

1. Supplier: Bosch Nigeria
2. Add line item: Front Brake Pad Set, Qty: 100, Unit Cost: 4500
3. Click **Create PO** (saves as Draft)
4. Open the draft PO → click **Approve**

### 8c. Receive goods (as Storekeeper)

Log out and log in as `store1`.

1. Go to Purchases → open the Approved PO
2. Click **Receive Goods**
3. Location: Main Warehouse
4. Qty received: 100
5. Click **Confirm Receipt**
6. Verify: Main Warehouse stock for Front Brake Pad Set increased by 100

---

## Phase 9: Test Transfers (as Storekeeper)

Still logged in as `store1`.

**Where:** Transfers → Create Transfer

1. Part: Front Brake Pad Set
2. From: Main Warehouse
3. To: Ikeja Shop
4. Quantity: 20
5. Save

Log in as `manager1`:
- Open the Pending transfer → click **Approve**

Log in as `store1`:
- Open the Approved transfer → click **Receive**
- Verify: 20 units moved from Warehouse to Shop

---

## Phase 10: Test Returns (as Manager)

Log in as `manager1`.

1. Go to Sales → open the confirmed cash sale from step 7b
2. Click **Process Return**
3. Select "Front Brake Pad Set" → quantity 1
4. Click **Process Return**
5. Verify: stock restored, sale shows "Returned" with a Return Summary

---

## Phase 11: Check Reports and Profit (as Manager or Admin)

Log in as `admin` or `manager1`.

### Dashboard
- Verify the **Profit Summary** widget shows Revenue, COGS, Gross Profit, and Margin %
- Try different period filters (This Month, 3M, 6M, 1Y, All Time)
- Check Top 5 Products and Top 5 Customers

### Reports
**Where:** Reports

- **Sales Report** — see the sales you just made
- **Inventory Report** — see current stock levels and values
- **Customer Report** — see Adekunle Motors' balance and aging
- **Supplier Report** — see Bosch Nigeria's outstanding balance
- **Financial Summary** — see gross margin calculation

---

## Phase 12: Test Access Control

Verify these are blocked (user gets redirected to Dashboard):

| Logged in as | Try to access | Expected |
|-------------|---------------|----------|
| `sales1` | /reports | Redirected to Dashboard |
| `sales1` | /suppliers | Redirected to Dashboard |
| `sales1` | /settings | Redirected to Dashboard |
| `sales1` | /transfers | Redirected to Dashboard |
| `store1` | /sales | Redirected to Dashboard |
| `store1` | /customers | Redirected to Dashboard |
| `store1` | /reports | Redirected to Dashboard |
| `store1` | /settings | Redirected to Dashboard |

Verify these ARE accessible:

| Logged in as | Page | Expected |
|-------------|------|----------|
| ALL roles | /profile | See your own profile, change password |
| ALL roles | /dashboard | See role-appropriate KPIs |
| ALL roles | /inventory | View stock levels |
| ALL roles | /notifications | See your notifications |

---

## Phase 13: Test Inventory Audit (as Storekeeper + Manager)

Log in as `store1`:

1. Go to Audits → **Start Audit**
2. Type: Cycle Count
3. Location: Main Warehouse
4. The system snapshots current stock
5. Enter your physical count for each part listed
6. Click **Submit for Approval**

Log in as `manager1`:
1. Open the pending audit → review variances
2. Click **Approve** — stock adjusts to match your count

---

## Quick Reference: Testing Checklist

| # | Feature | Test | Pass? |
|---|---------|------|-------|
| 1 | Login | Admin can log in | ☐ |
| 2 | Password change | First login forces password change | ☐ |
| 3 | Business Profile | Logo, phones, bank accounts save correctly | ☐ |
| 4 | Locations | Can create Warehouse and Shop | ☐ |
| 5 | Categories | 45 categories pre-loaded | ☐ |
| 6 | Add Part | Part created with auto-generated number | ☐ |
| 7 | Pricing validation | Selling price < cost price is blocked | ☐ |
| 8 | Initial stock | Stock added to location on part creation | ☐ |
| 9 | Cash sale | Sale confirmed, stock deducted, invoice generated | ☐ |
| 10 | Credit sale | Customer balance increases correctly | ☐ |
| 11 | Partial payment | Amount paid at checkout reduces balance | ☐ |
| 12 | Invoice PDF | Shows logo, bank accounts, QR code | ☐ |
| 13 | Customer payment | Balance reduces in credit ledger | ☐ |
| 14 | Add supplier | Supplier appears in list | ☐ |
| 15 | Purchase order | PO created, approved, received | ☐ |
| 16 | GRN | Stock increases at receiving location | ☐ |
| 17 | Transfer | Stock moves between locations | ☐ |
| 18 | Sales return | Stock restored, credit note generated | ☐ |
| 19 | Profit summary | Shows revenue, COGS, margin (Admin/Manager) | ☐ |
| 20 | Reports | All 5 report types generate correctly | ☐ |
| 21 | Access control | Salesperson blocked from /reports | ☐ |
| 22 | Access control | Storekeeper blocked from /sales | ☐ |
| 23 | Profile | All roles can view profile and change password | ☐ |
| 24 | Notifications | Low stock alert appears when stock drops | ☐ |
| 25 | Audit | Cycle count with variance reconciliation | ☐ |

---

## Resetting Everything (Start Fresh)

If you need to start over completely:

```bash
docker compose down -v          # Deletes all data
docker compose up --build -d    # Rebuilds and starts fresh
docker logs stockpilot-backend 2>&1 | grep "Temporary Password"
```

This gives you a clean database with only the admin account and default categories.

---

## Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Redirected to login unexpectedly | Session expired (Redis restart) | Log in again with your password |
| "No items found" after creating | Search field has old text | Clear the search box |
| Selling price rejected | Price is below cost price | Set selling ≥ cost |
| Can't access a page | Your role doesn't have permission | Ask Admin to check your role |
| Password rejected | Doesn't meet complexity rules | Use 8+ chars, uppercase, lowercase, digit |
