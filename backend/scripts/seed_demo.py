#!/usr/bin/env python3
"""Seed connected demo data for reviewing the StockPilot UI.

Creates locations, spare parts, suppliers, opening stock (via the purchase
receive flow so cost layers / ledger / stock cache stay consistent), purchase
orders in several statuses, transfers across the state machine, and one open
audit session. Also creates a few extra users so the Settings page has rows.

Everything routes through the service layer for anything that touches stock, so
inventory valuation (FIFO cost layers), the movement ledger, and the stock cache
stay consistent — exactly as they would from the real app.

The script is idempotent: it keys demo records by well-known names/part numbers
and skips creation when they already exist, so it is safe to run repeatedly.

Usage (from inside the backend container):
    docker exec stockpilot-backend python scripts/seed_demo.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from passlib.context import CryptContext
from sqlalchemy import select, text

sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.database import async_session_factory
from app.models.user import User
from app.models.location import Location
from app.models.category import Category
from app.models.spare_part import SparePart
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.sale import PaymentType
from app.models.audit_session import AuditType
from app.services.purchase_service import PurchaseService
from app.services.transfer_service import TransferService
from app.services.audit_service import AuditService
from app.services.sales_service import SalesService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Demo definitions -------------------------------------------------------

DEMO_LOCATIONS = [
    {"name": "Main Warehouse", "type": "warehouse", "address": "12 Industrial Rd, Lagos"},
    {"name": "Downtown Shop", "type": "shop", "address": "88 Market St, Lagos"},
]

DEMO_SUPPLIERS = [
    {"name": "AutoParts Wholesale Ltd", "payment_terms": "Net 30", "email": "sales@autoparts.example"},
    {"name": "Prime Components Co", "payment_terms": "Net 15", "email": "orders@primecomponents.example"},
]

# (part_number, name, cost_price, selling_price, min_stock_level)
DEMO_PARTS = [
    ("BRK-PAD-001", "Front Brake Pad Set", Decimal("18.00"), Decimal("29.99"), Decimal("10")),
    ("OIL-FLT-002", "Engine Oil Filter", Decimal("4.50"), Decimal("8.99"), Decimal("20")),
    ("SPK-PLG-003", "Spark Plug (Iridium)", Decimal("6.00"), Decimal("11.50"), Decimal("30")),
    ("AIR-FLT-004", "Air Filter Element", Decimal("7.25"), Decimal("13.75"), Decimal("15")),
]

DEMO_USERS = [
    ("manager1", "Manager1!", "manager1@example.com", "Manager"),
    ("sales1", "Sales1!Pass", "sales1@example.com", "Salesperson"),
    ("store1", "Store1!Pass", "store1@example.com", "Storekeeper"),
]

DEMO_CUSTOMERS = [
    {"name": "Acme Motors Ltd", "phone": "+2348010000001", "email": "accounts@acmemotors.example",
     "credit_limit": Decimal("5000.00")},
]


async def get_admin_id(session) -> uuid.UUID:
    result = await session.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one_or_none()
    if admin is None:
        print("ERROR: admin user not found. Start the backend once so the initial admin is provisioned.")
        sys.exit(1)
    return admin.id


async def ensure_users() -> None:
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        for username, password, email, role in DEMO_USERS:
            exists = (await session.execute(
                select(User.id).where(User.username == username)
            )).scalar()
            if exists:
                print(f"  user '{username}' already exists — skipping")
                continue
            await session.execute(
                text("""
                    INSERT INTO users (id, username, email, password_hash, role, is_active,
                                       failed_login_attempts, must_change_password, created_at, updated_at)
                    VALUES (:id, :username, :email, :password_hash, :role, true, 0, false, :now, :now)
                """),
                {
                    "id": uuid.uuid4(),
                    "username": username,
                    "email": email,
                    "password_hash": pwd_context.hash(password),
                    "role": role,
                    "now": now,
                },
            )
            print(f"  created user '{username}' ({role}) — password: {password}")
        await session.commit()


async def ensure_locations(session, admin_id: uuid.UUID) -> dict[str, Location]:
    locations: dict[str, Location] = {}
    for spec in DEMO_LOCATIONS:
        existing = (await session.execute(
            select(Location).where(Location.name == spec["name"], Location.deleted_at.is_(None))
        )).scalar_one_or_none()
        if existing:
            locations[spec["name"]] = existing
            print(f"  location '{spec['name']}' already exists — skipping")
            continue
        loc = Location(
            name=spec["name"],
            type=spec["type"],
            address=spec["address"],
            is_active=True,
            created_by=str(admin_id),
        )
        session.add(loc)
        await session.flush()
        locations[spec["name"]] = loc
        print(f"  created location '{spec['name']}' ({spec['type']})")
    return locations


async def ensure_suppliers(session, admin_id: uuid.UUID) -> dict[str, Supplier]:
    suppliers: dict[str, Supplier] = {}
    for spec in DEMO_SUPPLIERS:
        existing = (await session.execute(
            select(Supplier).where(Supplier.name == spec["name"], Supplier.deleted_at.is_(None))
        )).scalar_one_or_none()
        if existing:
            suppliers[spec["name"]] = existing
            print(f"  supplier '{spec['name']}' already exists — skipping")
            continue
        sup = Supplier(
            name=spec["name"],
            payment_terms=spec["payment_terms"],
            email=spec["email"],
            account_status="active",
            created_by=str(admin_id),
        )
        session.add(sup)
        await session.flush()
        suppliers[spec["name"]] = sup
        print(f"  created supplier '{spec['name']}'")
    return suppliers


async def ensure_customers(session, admin_id: uuid.UUID) -> dict[str, Customer]:
    customers: dict[str, Customer] = {}
    for spec in DEMO_CUSTOMERS:
        existing = (await session.execute(
            select(Customer).where(Customer.name == spec["name"], Customer.deleted_at.is_(None))
        )).scalar_one_or_none()
        if existing:
            customers[spec["name"]] = existing
            print(f"  customer '{spec['name']}' already exists — skipping")
            continue
        cust = Customer(
            name=spec["name"],
            phone=spec["phone"],
            email=spec["email"],
            credit_limit=spec["credit_limit"],
            account_status="active",
            created_by=str(admin_id),
        )
        session.add(cust)
        await session.flush()
        customers[spec["name"]] = cust
        print(f"  created customer '{spec['name']}'")
    return customers


async def ensure_parts(session, admin_id: uuid.UUID) -> dict[str, SparePart]:
    # Reuse an existing category if the app seeded any.
    category_id = (await session.execute(
        select(Category.id).where(Category.deleted_at.is_(None)).limit(1)
    )).scalar()

    parts: dict[str, SparePart] = {}
    for part_number, name, cost, sell, min_stock in DEMO_PARTS:
        existing = (await session.execute(
            select(SparePart).where(
                SparePart.part_number == part_number, SparePart.deleted_at.is_(None)
            )
        )).scalar_one_or_none()
        if existing:
            parts[part_number] = existing
            print(f"  part '{part_number}' already exists — skipping")
            continue
        part = SparePart(
            part_number=part_number,
            name=name,
            cost_price=cost,
            selling_price=sell,
            min_stock_level=min_stock,
            category_id=category_id,
            created_by=str(admin_id),
        )
        session.add(part)
        await session.flush()
        parts[part_number] = part
        print(f"  created part '{part_number}' ({name})")
    return parts


async def po_has_demo_data(session) -> bool:
    """Detect whether the stock/PO/transfer/audit portion already ran.

    Opening stock and the workflow records are not name-keyed, so we gate them
    on whether the demo warehouse already has any purchase orders.
    """
    count = (await session.execute(text("SELECT COUNT(*) FROM purchase_orders"))).scalar()
    return bool(count and count > 0)


async def seed_workflow(session, admin_id: uuid.UUID, locations, suppliers, parts) -> None:
    warehouse = locations["Main Warehouse"]
    shop = locations["Downtown Shop"]
    supplier_a = suppliers["AutoParts Wholesale Ltd"]
    supplier_b = suppliers["Prime Components Co"]
    part_list = list(parts.values())

    purchase = PurchaseService(session, user_id=admin_id)

    # 1) RECEIVED PO — this is also the opening-stock inflow for the warehouse.
    po_recv = await purchase.create_po(
        supplier_id=supplier_a.id,
        items=[
            {"spare_part_id": p.id, "quantity_ordered": Decimal("100"), "unit_cost": p.cost_price}
            for p in part_list
        ],
        notes="Opening stock receipt",
    )
    await purchase.approve_po(po_recv.id, approved_by=admin_id)
    await purchase.receive_goods(
        po_recv.id,
        location_id=warehouse.id,
        received_by=admin_id,
        items=[
            {"po_item_id": item.id, "quantity_received": Decimal("100")}
            for item in po_recv.items
        ],
        notes="Full receipt of opening stock",
    )
    print(f"  received PO {str(po_recv.id)[:8]} — warehouse stocked (100 each of {len(part_list)} parts)")

    # 2) APPROVED PO (awaiting goods).
    po_appr = await purchase.create_po(
        supplier_id=supplier_b.id,
        items=[{"spare_part_id": part_list[0].id, "quantity_ordered": Decimal("40"), "unit_cost": part_list[0].cost_price}],
        notes="Restock brake pads",
    )
    await purchase.approve_po(po_appr.id, approved_by=admin_id)
    print(f"  approved PO {str(po_appr.id)[:8]} (awaiting receipt)")

    # 3) DRAFT PO.
    po_draft = await purchase.create_po(
        supplier_id=supplier_b.id,
        items=[{"spare_part_id": part_list[1].id, "quantity_ordered": Decimal("60"), "unit_cost": part_list[1].cost_price}],
        notes="Draft order — pending review",
    )
    print(f"  draft PO {str(po_draft.id)[:8]}")

    # Flush purchase side effects (cost layers + stock cache) before transfers
    # consume from them.
    await session.flush()

    transfer = TransferService(session)

    # 4) PENDING transfer (warehouse -> shop).
    t_pending = await transfer.create_transfer(
        spare_part_id=part_list[0].id,
        source_location_id=warehouse.id,
        destination_location_id=shop.id,
        quantity=Decimal("10"),
        requested_by=admin_id,
    )
    print(f"  pending transfer {str(t_pending.id)[:8]}")

    # 5) IN_TRANSIT transfer (create + approve moves it to in-transit).
    t_transit = await transfer.create_transfer(
        spare_part_id=part_list[1].id,
        source_location_id=warehouse.id,
        destination_location_id=shop.id,
        quantity=Decimal("15"),
        requested_by=admin_id,
    )
    await transfer.approve_transfer(t_transit.id, approved_by=admin_id)
    print(f"  in-transit transfer {str(t_transit.id)[:8]}")

    # 6) RECEIVED transfer (create + approve + receive).
    t_recv = await transfer.create_transfer(
        spare_part_id=part_list[2].id,
        source_location_id=warehouse.id,
        destination_location_id=shop.id,
        quantity=Decimal("20"),
        requested_by=admin_id,
    )
    await transfer.approve_transfer(t_recv.id, approved_by=admin_id)
    await transfer.receive_transfer(t_recv.id, received_by=admin_id)
    print(f"  received transfer {str(t_recv.id)[:8]}")

    # 7) Open audit session on the warehouse (stays INITIATED).
    audit = AuditService(session)
    audit_session = await audit.initiate_audit(
        location_id=warehouse.id,
        audit_type=AuditType.FULL_STOCK_COUNT,
        initiated_by=admin_id,
    )
    print(f"  initiated audit {str(audit_session.id)[:8]} (open, full stock count)")


async def sales_already_seeded(session) -> bool:
    """Sales are gated separately from the PO workflow so they can be seeded on
    a later run (e.g. after the PO/transfer workflow already exists)."""
    count = (await session.execute(
        text("SELECT COUNT(*) FROM sales WHERE status <> 'DRAFT'")
    )).scalar()
    return bool(count and count > 0)


async def seed_sales(session, admin_id: uuid.UUID, locations, parts, customers) -> None:
    warehouse = locations["Main Warehouse"]
    part_list = list(parts.values())
    customer = customers["Acme Motors Ltd"]

    # Ensure any prior stock movements are flushed before sales consume FIFO
    # layers from the warehouse.
    await session.flush()

    sales = SalesService(session, user_id=admin_id)

    # Confirmed CASH sale (walk-in, no customer) from the warehouse.
    cash_sale = await sales.create_sale(
        customer_id=None,
        location_id=warehouse.id,
        payment_type=PaymentType.CASH,
        items=[
            {"spare_part_id": part_list[0].id, "quantity": Decimal("2"), "unit_price": part_list[0].selling_price},
            {"spare_part_id": part_list[1].id, "quantity": Decimal("3"), "unit_price": part_list[1].selling_price},
        ],
    )
    await sales.confirm_sale(cash_sale.id)
    print(f"  confirmed CASH sale {str(cash_sale.id)[:8]}")

    # Confirmed CREDIT sale for the customer (records a credit-ledger debit).
    credit_sale = await sales.create_sale(
        customer_id=customer.id,
        location_id=warehouse.id,
        payment_type=PaymentType.CREDIT,
        items=[
            {"spare_part_id": part_list[2].id, "quantity": Decimal("5"), "unit_price": part_list[2].selling_price},
        ],
    )
    await sales.confirm_sale(credit_sale.id)
    print(f"  confirmed CREDIT sale {str(credit_sale.id)[:8]} for '{customer.name}'")


async def main() -> None:
    print("Seeding demo data...")

    print("Users:")
    await ensure_users()

    async with async_session_factory() as session:
        admin_id = await get_admin_id(session)

        print("Locations:")
        locations = await ensure_locations(session, admin_id)
        print("Suppliers:")
        suppliers = await ensure_suppliers(session, admin_id)
        print("Customers:")
        customers = await ensure_customers(session, admin_id)
        print("Spare parts:")
        parts = await ensure_parts(session, admin_id)
        await session.commit()

        if await po_has_demo_data(session):
            print("Workflow data (POs/transfers/audit) already present — skipping to keep idempotent.")
        else:
            print("Workflow (stock, purchase orders, transfers, audit):")
            await seed_workflow(session, admin_id, locations, suppliers, parts)
            await session.commit()

        if await sales_already_seeded(session):
            print("Sales already present — skipping to keep idempotent.")
        else:
            print("Sales (cash + credit):")
            await seed_sales(session, admin_id, locations, parts, customers)
            await session.commit()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
