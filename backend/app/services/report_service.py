"""
Report service for the Auto Spare Parts ERP system.

Generates sales, inventory, customer, supplier, and financial summary reports
with date range filtering, location/salesperson/customer/category filters,
and export in PDF and CSV formats.

Satisfies Requirements:
- 12.1: Sales reports filterable by date range, location, salesperson, customer, category
- 12.2: Inventory reports with stock levels, valuation, slow-moving items, below reorder
- 12.3: Customer reports with purchase history, outstanding balances, aging
- 12.4: Supplier reports with purchase history, outstanding balances, aging
- 12.5: Financial summary with sales revenue, COGS, gross margin, receivables, payables
- 12.6: Support export in PDF and CSV formats
- 12.7: Date range filtering with minimum granularity of one day
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_layer import CostLayer
from app.models.customer import Customer
from app.models.customer_credit_ledger import CustomerCreditLedger
from app.models.inventory_movement_ledger import InventoryMovementLedger
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.sale import Sale, SaleItem, SaleStatus
from app.models.spare_part import SparePart
from app.models.stock_status_cache import StockStatusCache
from app.models.supplier import Supplier
from app.models.supplier_ledger import SupplierLedger


# =============================================================================
# Data Classes for Report Results
# =============================================================================


@dataclass
class DateRange:
    """Date range filter for reports (Req 12.7: minimum granularity of one day)."""

    start_date: date
    end_date: date

    def to_datetime_range(self) -> tuple[datetime, datetime]:
        """Convert date range to datetime range (start of day to end of day)."""
        start = datetime(
            self.start_date.year, self.start_date.month, self.start_date.day,
            0, 0, 0, tzinfo=timezone.utc
        )
        end = datetime(
            self.end_date.year, self.end_date.month, self.end_date.day,
            23, 59, 59, 999999, tzinfo=timezone.utc
        )
        return start, end


@dataclass
class SalesReportFilters:
    """Filters for sales reports (Req 12.1)."""

    date_range: DateRange
    location_id: Optional[uuid.UUID] = None
    salesperson_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None


@dataclass
class SalesReportRow:
    """A single row in the sales report."""

    sale_id: uuid.UUID
    invoice_number: Optional[str]
    sale_date: datetime
    customer_name: Optional[str]
    location_id: uuid.UUID
    total_amount: Decimal
    discount_total: Decimal
    tax_amount: Decimal
    cost_of_goods_sold: Decimal
    gross_margin: Decimal


@dataclass
class SalesReportResult:
    """Complete sales report result."""

    filters: SalesReportFilters
    rows: list[SalesReportRow] = field(default_factory=list)
    total_sales: Decimal = Decimal("0.00")
    total_cogs: Decimal = Decimal("0.00")
    total_gross_margin: Decimal = Decimal("0.00")
    total_discount: Decimal = Decimal("0.00")
    sale_count: int = 0


@dataclass
class InventoryReportRow:
    """A single row in the inventory report."""

    spare_part_id: uuid.UUID
    part_number: str
    name: str
    brand: Optional[str]
    category_id: uuid.UUID
    location_id: uuid.UUID
    current_quantity: Decimal
    unit_cost: Decimal
    stock_value: Decimal
    min_stock_level: Decimal
    is_below_reorder: bool
    last_movement_date: Optional[datetime] = None


@dataclass
class InventoryReportResult:
    """Complete inventory report result (Req 12.2)."""

    rows: list[InventoryReportRow] = field(default_factory=list)
    total_stock_value: Decimal = Decimal("0.00")
    below_reorder_count: int = 0
    slow_moving_count: int = 0
    total_items: int = 0


@dataclass
class CustomerReportRow:
    """A single row in the customer report (Req 12.3)."""

    customer_id: uuid.UUID
    customer_name: str
    total_purchases: Decimal
    purchase_count: int
    outstanding_balance: Decimal
    current: Decimal = Decimal("0.00")
    days_30: Decimal = Decimal("0.00")
    days_60: Decimal = Decimal("0.00")
    days_90: Decimal = Decimal("0.00")
    days_120_plus: Decimal = Decimal("0.00")


@dataclass
class CustomerReportResult:
    """Complete customer report result."""

    date_range: DateRange
    rows: list[CustomerReportRow] = field(default_factory=list)
    total_outstanding: Decimal = Decimal("0.00")
    total_purchases: Decimal = Decimal("0.00")
    customer_count: int = 0


@dataclass
class SupplierReportRow:
    """A single row in the supplier report (Req 12.4)."""

    supplier_id: uuid.UUID
    supplier_name: str
    total_purchases: Decimal
    purchase_count: int
    outstanding_balance: Decimal
    current: Decimal = Decimal("0.00")
    days_30: Decimal = Decimal("0.00")
    days_60: Decimal = Decimal("0.00")
    days_90: Decimal = Decimal("0.00")
    days_120_plus: Decimal = Decimal("0.00")


@dataclass
class SupplierReportResult:
    """Complete supplier report result."""

    date_range: DateRange
    rows: list[SupplierReportRow] = field(default_factory=list)
    total_outstanding: Decimal = Decimal("0.00")
    total_purchases: Decimal = Decimal("0.00")
    supplier_count: int = 0


@dataclass
class FinancialSummaryResult:
    """Financial summary report result (Req 12.5)."""

    date_range: DateRange
    total_sales_revenue: Decimal = Decimal("0.00")
    cost_of_goods_sold: Decimal = Decimal("0.00")
    gross_margin: Decimal = Decimal("0.00")
    gross_margin_percentage: Decimal = Decimal("0.00")
    accounts_receivable: Decimal = Decimal("0.00")
    accounts_payable: Decimal = Decimal("0.00")
    sale_count: int = 0
    purchase_count: int = 0


# =============================================================================
# Report Service
# =============================================================================


class ReportService:
    """Service for generating business reports.

    All report methods accept date ranges and optional filters, returning
    structured data that can be serialized to PDF or CSV format.
    """

    def __init__(self, db: AsyncSession):
        self.db = db


    # -------------------------------------------------------------------------
    # Sales Report (Req 12.1)
    # -------------------------------------------------------------------------

    async def generate_sales_report(
        self, filters: SalesReportFilters
    ) -> SalesReportResult:
        """Generate a sales report filtered by date range and optional filters.

        Satisfies Requirement 12.1: Sales reports filterable by date range,
        location, salesperson, customer, and product category.

        Args:
            filters: SalesReportFilters with date_range and optional filters.

        Returns:
            SalesReportResult with rows and summary totals.
        """
        start_dt, end_dt = filters.date_range.to_datetime_range()

        # Base query: confirmed sales within date range
        conditions = [
            Sale.status == SaleStatus.CONFIRMED,
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt,
        ]

        if filters.location_id:
            conditions.append(Sale.location_id == filters.location_id)
        if filters.salesperson_id:
            conditions.append(Sale.created_by == str(filters.salesperson_id))
        if filters.customer_id:
            conditions.append(Sale.customer_id == filters.customer_id)

        stmt = select(Sale).where(and_(*conditions))
        result = await self.db.execute(stmt)
        sales = result.scalars().all()

        # If category filter, we need to filter sales that contain items
        # in that category
        if filters.category_id:
            # Get spare part IDs in the category
            part_stmt = select(SparePart.id).where(
                SparePart.category_id == filters.category_id,
                SparePart.deleted_at.is_(None),
            )
            part_result = await self.db.execute(part_stmt)
            category_part_ids = set(part_result.scalars().all())

            # Filter sales that have items in this category
            filtered_sales = []
            for sale in sales:
                has_category_item = any(
                    item.spare_part_id in category_part_ids
                    for item in sale.items
                )
                if has_category_item:
                    filtered_sales.append(sale)
            sales = filtered_sales

        # Build report rows
        report = SalesReportResult(filters=filters)
        for sale in sales:
            cogs = sum(
                (item.cost_of_goods_sold or Decimal("0.00"))
                for item in sale.items
            )
            # Look up customer name
            customer_name = None
            if sale.customer_id:
                cust_stmt = select(Customer.name).where(
                    Customer.id == sale.customer_id
                )
                cust_result = await self.db.execute(cust_stmt)
                customer_name = cust_result.scalar_one_or_none()

            gross_margin = sale.total_amount - cogs
            row = SalesReportRow(
                sale_id=sale.id,
                invoice_number=sale.invoice_number,
                sale_date=sale.created_at,
                customer_name=customer_name,
                location_id=sale.location_id,
                total_amount=sale.total_amount,
                discount_total=sale.discount_total,
                tax_amount=sale.tax_amount,
                cost_of_goods_sold=cogs,
                gross_margin=gross_margin,
            )
            report.rows.append(row)

            report.total_sales += sale.total_amount
            report.total_cogs += cogs
            report.total_gross_margin += gross_margin
            report.total_discount += sale.discount_total

        report.sale_count = len(report.rows)
        return report


    # -------------------------------------------------------------------------
    # Inventory Report (Req 12.2)
    # -------------------------------------------------------------------------

    async def generate_inventory_report(
        self,
        location_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        slow_moving_days: int = 90,
    ) -> InventoryReportResult:
        """Generate an inventory report showing stock levels and valuation.

        Satisfies Requirement 12.2: Inventory reports with current stock levels,
        stock valuation, slow-moving items, and items below reorder level.

        Args:
            location_id: Optional location filter.
            category_id: Optional category filter.
            slow_moving_days: Days since last movement to consider slow-moving.

        Returns:
            InventoryReportResult with rows and summary totals.
        """
        # Get all stock cache entries with spare part info
        conditions = []
        if location_id:
            conditions.append(
                StockStatusCache.location_id == location_id
            )

        cache_stmt = select(StockStatusCache)
        if conditions:
            cache_stmt = cache_stmt.where(and_(*conditions))

        cache_result = await self.db.execute(cache_stmt)
        cache_entries = cache_result.scalars().all()

        report = InventoryReportResult()
        now = datetime.now(timezone.utc)

        for cache_entry in cache_entries:
            # Get spare part details
            part_stmt = select(SparePart).where(
                SparePart.id == cache_entry.spare_part_id,
                SparePart.deleted_at.is_(None),
            )
            part_result = await self.db.execute(part_stmt)
            part = part_result.scalar_one_or_none()
            if not part:
                continue

            # Apply category filter
            if category_id and part.category_id != category_id:
                continue

            # Calculate stock valuation from cost layers
            valuation_stmt = select(
                func.coalesce(
                    func.sum(
                        CostLayer.remaining_quantity * CostLayer.unit_cost
                    ),
                    Decimal("0"),
                )
            ).where(
                CostLayer.spare_part_id == cache_entry.spare_part_id,
                CostLayer.location_id == cache_entry.location_id,
                CostLayer.remaining_quantity > 0,
            )
            val_result = await self.db.execute(valuation_stmt)
            stock_value = val_result.scalar() or Decimal("0.00")

            # Determine weighted average unit cost
            if cache_entry.current_quantity > 0:
                unit_cost = stock_value / cache_entry.current_quantity
            else:
                unit_cost = Decimal("0.00")

            # Check last movement date for slow-moving detection
            last_move_stmt = select(
                func.max(InventoryMovementLedger.created_at)
            ).where(
                InventoryMovementLedger.spare_part_id == cache_entry.spare_part_id,
                InventoryMovementLedger.location_id == cache_entry.location_id,
            )
            last_move_result = await self.db.execute(last_move_stmt)
            last_movement_date = last_move_result.scalar_one_or_none()

            # Determine if below reorder level
            is_below_reorder = (
                cache_entry.current_quantity < Decimal(str(part.min_stock_level))
            )

            row = InventoryReportRow(
                spare_part_id=part.id,
                part_number=part.part_number,
                name=part.name,
                brand=part.brand,
                category_id=part.category_id,
                location_id=cache_entry.location_id,
                current_quantity=cache_entry.current_quantity,
                unit_cost=unit_cost,
                stock_value=stock_value,
                min_stock_level=Decimal(str(part.min_stock_level)),
                is_below_reorder=is_below_reorder,
                last_movement_date=last_movement_date,
            )
            report.rows.append(row)
            report.total_stock_value += stock_value

            if is_below_reorder:
                report.below_reorder_count += 1

            # Check if slow-moving (no movement in N days)
            if last_movement_date:
                days_since = (now - last_movement_date).days
                if days_since > slow_moving_days:
                    report.slow_moving_count += 1
            elif cache_entry.current_quantity > 0:
                # Has stock but never moved — consider slow-moving
                report.slow_moving_count += 1

        report.total_items = len(report.rows)
        return report


    # -------------------------------------------------------------------------
    # Customer Report (Req 12.3)
    # -------------------------------------------------------------------------

    async def generate_customer_report(
        self,
        date_range: DateRange,
        customer_id: Optional[uuid.UUID] = None,
    ) -> CustomerReportResult:
        """Generate a customer report with purchase history and aging.

        Satisfies Requirement 12.3: Customer reports showing purchase history,
        outstanding balances, and aging analysis.

        Args:
            date_range: Date range for purchase history filtering.
            customer_id: Optional specific customer filter.

        Returns:
            CustomerReportResult with rows and summary totals.
        """
        start_dt, end_dt = date_range.to_datetime_range()
        now = datetime.now(timezone.utc)

        # Get customers
        cust_conditions = [Customer.deleted_at.is_(None)]
        if customer_id:
            cust_conditions.append(Customer.id == customer_id)

        cust_stmt = select(Customer).where(and_(*cust_conditions))
        cust_result = await self.db.execute(cust_stmt)
        customers = cust_result.scalars().all()

        report = CustomerReportResult(date_range=date_range)

        for customer in customers:
            # Total purchases in date range
            purchase_stmt = select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")),
                func.count(Sale.id),
            ).where(
                Sale.customer_id == customer.id,
                Sale.status == SaleStatus.CONFIRMED,
                Sale.created_at >= start_dt,
                Sale.created_at <= end_dt,
            )
            purchase_result = await self.db.execute(purchase_stmt)
            purchase_row = purchase_result.one()
            total_purchases = purchase_row[0] or Decimal("0.00")
            purchase_count = purchase_row[1]

            # Outstanding balance from credit ledger
            balance_stmt = select(
                func.coalesce(
                    func.sum(CustomerCreditLedger.amount), Decimal("0")
                )
            ).where(CustomerCreditLedger.customer_id == customer.id)
            balance_result = await self.db.execute(balance_stmt)
            outstanding_balance = balance_result.scalar() or Decimal("0.00")

            # Aging analysis on outstanding debit entries
            aging = await self._calculate_customer_aging(customer.id, now)

            row = CustomerReportRow(
                customer_id=customer.id,
                customer_name=customer.name,
                total_purchases=total_purchases,
                purchase_count=purchase_count,
                outstanding_balance=outstanding_balance,
                **aging,
            )
            report.rows.append(row)
            report.total_outstanding += outstanding_balance
            report.total_purchases += total_purchases

        report.customer_count = len(report.rows)
        return report


    # -------------------------------------------------------------------------
    # Supplier Report (Req 12.4)
    # -------------------------------------------------------------------------

    async def generate_supplier_report(
        self,
        date_range: DateRange,
        supplier_id: Optional[uuid.UUID] = None,
    ) -> SupplierReportResult:
        """Generate a supplier report with purchase history and aging.

        Satisfies Requirement 12.4: Supplier reports showing purchase history,
        outstanding balances, and aging analysis.

        Args:
            date_range: Date range for purchase history filtering.
            supplier_id: Optional specific supplier filter.

        Returns:
            SupplierReportResult with rows and summary totals.
        """
        start_dt, end_dt = date_range.to_datetime_range()
        now = datetime.now(timezone.utc)

        # Get suppliers
        sup_conditions = [Supplier.deleted_at.is_(None)]
        if supplier_id:
            sup_conditions.append(Supplier.id == supplier_id)

        sup_stmt = select(Supplier).where(and_(*sup_conditions))
        sup_result = await self.db.execute(sup_stmt)
        suppliers = sup_result.scalars().all()

        report = SupplierReportResult(date_range=date_range)

        for supplier in suppliers:
            # Total purchases in date range (from supplier ledger debits)
            purchase_stmt = select(
                func.coalesce(
                    func.sum(SupplierLedger.amount), Decimal("0")
                ),
                func.count(SupplierLedger.id),
            ).where(
                SupplierLedger.supplier_id == supplier.id,
                SupplierLedger.transaction_type == "PURCHASE",
                SupplierLedger.created_at >= start_dt,
                SupplierLedger.created_at <= end_dt,
            )
            purchase_result = await self.db.execute(purchase_stmt)
            purchase_row = purchase_result.one()
            total_purchases = purchase_row[0] or Decimal("0.00")
            purchase_count = purchase_row[1]

            # Outstanding balance (sum of all ledger entries)
            balance_stmt = select(
                func.coalesce(
                    func.sum(SupplierLedger.amount), Decimal("0")
                )
            ).where(SupplierLedger.supplier_id == supplier.id)
            balance_result = await self.db.execute(balance_stmt)
            outstanding_balance = balance_result.scalar() or Decimal("0.00")

            # Aging analysis
            aging = await self._calculate_supplier_aging(supplier.id, now)

            row = SupplierReportRow(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                total_purchases=total_purchases,
                purchase_count=purchase_count,
                outstanding_balance=outstanding_balance,
                **aging,
            )
            report.rows.append(row)
            report.total_outstanding += outstanding_balance
            report.total_purchases += total_purchases

        report.supplier_count = len(report.rows)
        return report


    # -------------------------------------------------------------------------
    # Financial Summary (Req 12.5)
    # -------------------------------------------------------------------------

    async def generate_financial_summary(
        self, date_range: DateRange
    ) -> FinancialSummaryResult:
        """Generate a financial summary for the specified period.

        Satisfies Requirement 12.5: Financial summary with total sales revenue,
        COGS, gross margin, accounts receivable, and accounts payable.

        Args:
            date_range: Period for the financial summary.

        Returns:
            FinancialSummaryResult with financial metrics.
        """
        start_dt, end_dt = date_range.to_datetime_range()

        # Total sales revenue in period
        revenue_stmt = select(
            func.coalesce(func.sum(Sale.total_amount), Decimal("0")),
            func.count(Sale.id),
        ).where(
            Sale.status == SaleStatus.CONFIRMED,
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt,
        )
        revenue_result = await self.db.execute(revenue_stmt)
        revenue_row = revenue_result.one()
        total_revenue = revenue_row[0] or Decimal("0.00")
        sale_count = revenue_row[1]

        # COGS from sale items in period
        cogs_stmt = select(
            func.coalesce(func.sum(SaleItem.cost_of_goods_sold), Decimal("0"))
        ).join(
            Sale, SaleItem.sale_id == Sale.id
        ).where(
            Sale.status == SaleStatus.CONFIRMED,
            Sale.created_at >= start_dt,
            Sale.created_at <= end_dt,
        )
        cogs_result = await self.db.execute(cogs_stmt)
        total_cogs = cogs_result.scalar() or Decimal("0.00")

        # Gross margin
        gross_margin = total_revenue - total_cogs
        gross_margin_pct = (
            (gross_margin / total_revenue * Decimal("100"))
            if total_revenue > 0
            else Decimal("0.00")
        )

        # Accounts receivable (total outstanding customer balances)
        ar_stmt = select(
            func.coalesce(
                func.sum(CustomerCreditLedger.amount), Decimal("0")
            )
        )
        ar_result = await self.db.execute(ar_stmt)
        accounts_receivable = ar_result.scalar() or Decimal("0.00")

        # Accounts payable (total outstanding supplier balances)
        ap_stmt = select(
            func.coalesce(
                func.sum(SupplierLedger.amount), Decimal("0")
            )
        )
        ap_result = await self.db.execute(ap_stmt)
        accounts_payable = ap_result.scalar() or Decimal("0.00")

        # Purchase count in period
        po_stmt = select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.created_at >= start_dt,
            PurchaseOrder.created_at <= end_dt,
        )
        po_result = await self.db.execute(po_stmt)
        purchase_count = po_result.scalar() or 0

        return FinancialSummaryResult(
            date_range=date_range,
            total_sales_revenue=total_revenue,
            cost_of_goods_sold=total_cogs,
            gross_margin=gross_margin,
            gross_margin_percentage=gross_margin_pct,
            accounts_receivable=accounts_receivable,
            accounts_payable=accounts_payable,
            sale_count=sale_count,
            purchase_count=purchase_count,
        )


    # -------------------------------------------------------------------------
    # Private Helpers: Aging Analysis
    # -------------------------------------------------------------------------

    async def _calculate_customer_aging(
        self, customer_id: uuid.UUID, now: datetime
    ) -> dict[str, Decimal]:
        """Calculate aging buckets for a customer's outstanding debits.

        Returns dict with keys: current, days_30, days_60, days_90, days_120_plus.
        """
        # Get all unpaid debit entries (positive amounts = money owed)
        stmt = select(CustomerCreditLedger).where(
            CustomerCreditLedger.customer_id == customer_id,
            CustomerCreditLedger.amount > 0,
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        buckets = {
            "current": Decimal("0.00"),
            "days_30": Decimal("0.00"),
            "days_60": Decimal("0.00"),
            "days_90": Decimal("0.00"),
            "days_120_plus": Decimal("0.00"),
        }

        for entry in entries:
            days_old = (now - entry.created_at).days
            if days_old <= 30:
                buckets["current"] += entry.amount
            elif days_old <= 60:
                buckets["days_30"] += entry.amount
            elif days_old <= 90:
                buckets["days_60"] += entry.amount
            elif days_old <= 120:
                buckets["days_90"] += entry.amount
            else:
                buckets["days_120_plus"] += entry.amount

        return buckets


    async def _calculate_supplier_aging(
        self, supplier_id: uuid.UUID, now: datetime
    ) -> dict[str, Decimal]:
        """Calculate aging buckets for a supplier's outstanding balance.

        Returns dict with keys: current, days_30, days_60, days_90, days_120_plus.
        """
        # Get all purchase debit entries (positive amounts = money owed)
        stmt = select(SupplierLedger).where(
            SupplierLedger.supplier_id == supplier_id,
            SupplierLedger.amount > 0,
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        buckets = {
            "current": Decimal("0.00"),
            "days_30": Decimal("0.00"),
            "days_60": Decimal("0.00"),
            "days_90": Decimal("0.00"),
            "days_120_plus": Decimal("0.00"),
        }

        for entry in entries:
            days_old = (now - entry.created_at).days
            if days_old <= 30:
                buckets["current"] += entry.amount
            elif days_old <= 60:
                buckets["days_30"] += entry.amount
            elif days_old <= 90:
                buckets["days_60"] += entry.amount
            elif days_old <= 120:
                buckets["days_90"] += entry.amount
            else:
                buckets["days_120_plus"] += entry.amount

        return buckets


    # -------------------------------------------------------------------------
    # Export: CSV (Req 12.6)
    # -------------------------------------------------------------------------

    def export_sales_report_csv(self, report: SalesReportResult) -> str:
        """Export sales report data to CSV format.

        Args:
            report: The sales report result to export.

        Returns:
            CSV string content.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Sale ID", "Invoice Number", "Sale Date", "Customer",
            "Location ID", "Total Amount", "Discount", "Tax",
            "COGS", "Gross Margin",
        ])
        for row in report.rows:
            writer.writerow([
                str(row.sale_id),
                row.invoice_number or "",
                row.sale_date.strftime("%Y-%m-%d %H:%M:%S"),
                row.customer_name or "Walk-in",
                str(row.location_id),
                str(row.total_amount),
                str(row.discount_total),
                str(row.tax_amount),
                str(row.cost_of_goods_sold),
                str(row.gross_margin),
            ])
        # Summary row
        writer.writerow([])
        writer.writerow([
            "TOTALS", "", "", "", "",
            str(report.total_sales),
            str(report.total_discount),
            "",
            str(report.total_cogs),
            str(report.total_gross_margin),
        ])
        return output.getvalue()


    def export_inventory_report_csv(self, report: InventoryReportResult) -> str:
        """Export inventory report data to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Part Number", "Name", "Brand", "Category ID",
            "Location ID", "Current Qty", "Unit Cost",
            "Stock Value", "Min Stock Level", "Below Reorder",
            "Last Movement Date",
        ])
        for row in report.rows:
            writer.writerow([
                row.part_number,
                row.name,
                row.brand or "",
                str(row.category_id),
                str(row.location_id),
                str(row.current_quantity),
                str(row.unit_cost),
                str(row.stock_value),
                str(row.min_stock_level),
                "Yes" if row.is_below_reorder else "No",
                row.last_movement_date.strftime("%Y-%m-%d")
                if row.last_movement_date else "Never",
            ])
        writer.writerow([])
        writer.writerow([
            "SUMMARY", "", "", "", "",
            f"Items: {report.total_items}", "",
            f"Total Value: {report.total_stock_value}",
            f"Below Reorder: {report.below_reorder_count}",
            f"Slow Moving: {report.slow_moving_count}", "",
        ])
        return output.getvalue()


    def export_customer_report_csv(self, report: CustomerReportResult) -> str:
        """Export customer report data to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Customer ID", "Customer Name", "Total Purchases",
            "Purchase Count", "Outstanding Balance",
            "Current", "30 Days", "60 Days", "90 Days", "120+ Days",
        ])
        for row in report.rows:
            writer.writerow([
                str(row.customer_id),
                row.customer_name,
                str(row.total_purchases),
                str(row.purchase_count),
                str(row.outstanding_balance),
                str(row.current),
                str(row.days_30),
                str(row.days_60),
                str(row.days_90),
                str(row.days_120_plus),
            ])
        writer.writerow([])
        writer.writerow([
            "TOTALS", "", str(report.total_purchases), "",
            str(report.total_outstanding),
            "", "", "", "", "",
        ])
        return output.getvalue()

    def export_supplier_report_csv(self, report: SupplierReportResult) -> str:
        """Export supplier report data to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Supplier ID", "Supplier Name", "Total Purchases",
            "Purchase Count", "Outstanding Balance",
            "Current", "30 Days", "60 Days", "90 Days", "120+ Days",
        ])
        for row in report.rows:
            writer.writerow([
                str(row.supplier_id),
                row.supplier_name,
                str(row.total_purchases),
                str(row.purchase_count),
                str(row.outstanding_balance),
                str(row.current),
                str(row.days_30),
                str(row.days_60),
                str(row.days_90),
                str(row.days_120_plus),
            ])
        writer.writerow([])
        writer.writerow([
            "TOTALS", "", str(report.total_purchases), "",
            str(report.total_outstanding),
            "", "", "", "", "",
        ])
        return output.getvalue()


    def export_financial_summary_csv(
        self, report: FinancialSummaryResult
    ) -> str:
        """Export financial summary to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Period Start", str(report.date_range.start_date)])
        writer.writerow(["Period End", str(report.date_range.end_date)])
        writer.writerow(["Total Sales Revenue", str(report.total_sales_revenue)])
        writer.writerow(["Cost of Goods Sold", str(report.cost_of_goods_sold)])
        writer.writerow(["Gross Margin", str(report.gross_margin)])
        writer.writerow([
            "Gross Margin %", f"{report.gross_margin_percentage:.2f}%"
        ])
        writer.writerow([
            "Accounts Receivable", str(report.accounts_receivable)
        ])
        writer.writerow(["Accounts Payable", str(report.accounts_payable)])
        writer.writerow(["Number of Sales", str(report.sale_count)])
        writer.writerow([
            "Number of Purchase Orders", str(report.purchase_count)
        ])
        return output.getvalue()


    # -------------------------------------------------------------------------
    # Export: PDF (Req 12.6)
    # -------------------------------------------------------------------------

    def export_sales_report_pdf(self, report: SalesReportResult) -> bytes:
        """Export sales report to PDF format using WeasyPrint.

        Args:
            report: The sales report result to export.

        Returns:
            PDF content as bytes.
        """
        html = self._render_sales_report_html(report)
        return self._html_to_pdf(html)

    def export_inventory_report_pdf(
        self, report: InventoryReportResult
    ) -> bytes:
        """Export inventory report to PDF format."""
        html = self._render_inventory_report_html(report)
        return self._html_to_pdf(html)

    def export_customer_report_pdf(
        self, report: CustomerReportResult
    ) -> bytes:
        """Export customer report to PDF format."""
        html = self._render_customer_report_html(report)
        return self._html_to_pdf(html)

    def export_supplier_report_pdf(
        self, report: SupplierReportResult
    ) -> bytes:
        """Export supplier report to PDF format."""
        html = self._render_supplier_report_html(report)
        return self._html_to_pdf(html)

    def export_financial_summary_pdf(
        self, report: FinancialSummaryResult
    ) -> bytes:
        """Export financial summary to PDF format."""
        html = self._render_financial_summary_html(report)
        return self._html_to_pdf(html)


    # -------------------------------------------------------------------------
    # Private Helpers: HTML Rendering for PDF
    # -------------------------------------------------------------------------

    def _html_to_pdf(self, html: str) -> bytes:
        """Convert HTML to PDF using WeasyPrint.

        Falls back to returning HTML as bytes if WeasyPrint is not available.
        """
        try:
            from weasyprint import HTML
            return HTML(string=html).write_pdf()
        except ImportError:
            # WeasyPrint not installed — return HTML bytes as fallback
            return html.encode("utf-8")

    def _base_css(self) -> str:
        """Return base CSS for PDF reports."""
        return """
        <style>
            body { font-family: Arial, sans-serif; font-size: 12px; }
            h1 { color: #333; border-bottom: 2px solid #333; }
            h2 { color: #555; margin-top: 20px; }
            table { width: 100%; border-collapse: collapse; margin: 10px 0; }
            th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
            th { background-color: #f5f5f5; font-weight: bold; }
            tr:nth-child(even) { background-color: #fafafa; }
            .summary { margin-top: 20px; padding: 10px; background: #f0f0f0; }
            .right { text-align: right; }
        </style>
        """


    def _render_sales_report_html(self, report: SalesReportResult) -> str:
        """Render sales report as HTML."""
        rows_html = ""
        for row in report.rows:
            rows_html += f"""
            <tr>
                <td>{row.invoice_number or ''}</td>
                <td>{row.sale_date.strftime('%Y-%m-%d')}</td>
                <td>{row.customer_name or 'Walk-in'}</td>
                <td class="right">{row.total_amount}</td>
                <td class="right">{row.discount_total}</td>
                <td class="right">{row.cost_of_goods_sold}</td>
                <td class="right">{row.gross_margin}</td>
            </tr>"""

        return f"""
        <html><head>{self._base_css()}</head><body>
        <h1>Sales Report</h1>
        <p>Period: {report.filters.date_range.start_date} to {report.filters.date_range.end_date}</p>
        <table>
            <thead><tr>
                <th>Invoice #</th><th>Date</th><th>Customer</th>
                <th>Total</th><th>Discount</th><th>COGS</th><th>Margin</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <div class="summary">
            <p><strong>Total Sales:</strong> {report.total_sales}</p>
            <p><strong>Total COGS:</strong> {report.total_cogs}</p>
            <p><strong>Gross Margin:</strong> {report.total_gross_margin}</p>
            <p><strong>Sales Count:</strong> {report.sale_count}</p>
        </div>
        </body></html>"""


    def _render_inventory_report_html(
        self, report: InventoryReportResult
    ) -> str:
        """Render inventory report as HTML."""
        rows_html = ""
        for row in report.rows:
            rows_html += f"""
            <tr>
                <td>{row.part_number}</td>
                <td>{row.name}</td>
                <td>{row.brand or ''}</td>
                <td class="right">{row.current_quantity}</td>
                <td class="right">{row.unit_cost:.2f}</td>
                <td class="right">{row.stock_value:.2f}</td>
                <td>{'Yes' if row.is_below_reorder else 'No'}</td>
            </tr>"""

        return f"""
        <html><head>{self._base_css()}</head><body>
        <h1>Inventory Report</h1>
        <table>
            <thead><tr>
                <th>Part #</th><th>Name</th><th>Brand</th>
                <th>Qty</th><th>Unit Cost</th><th>Value</th>
                <th>Below Reorder</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <div class="summary">
            <p><strong>Total Items:</strong> {report.total_items}</p>
            <p><strong>Total Value:</strong> {report.total_stock_value:.2f}</p>
            <p><strong>Below Reorder:</strong> {report.below_reorder_count}</p>
            <p><strong>Slow Moving:</strong> {report.slow_moving_count}</p>
        </div>
        </body></html>"""


    def _render_customer_report_html(
        self, report: CustomerReportResult
    ) -> str:
        """Render customer report as HTML."""
        rows_html = ""
        for row in report.rows:
            rows_html += f"""
            <tr>
                <td>{row.customer_name}</td>
                <td class="right">{row.total_purchases}</td>
                <td class="right">{row.purchase_count}</td>
                <td class="right">{row.outstanding_balance}</td>
                <td class="right">{row.current}</td>
                <td class="right">{row.days_30}</td>
                <td class="right">{row.days_60}</td>
                <td class="right">{row.days_90}</td>
                <td class="right">{row.days_120_plus}</td>
            </tr>"""

        return f"""
        <html><head>{self._base_css()}</head><body>
        <h1>Customer Report</h1>
        <p>Period: {report.date_range.start_date} to {report.date_range.end_date}</p>
        <table>
            <thead><tr>
                <th>Customer</th><th>Purchases</th><th>Count</th>
                <th>Balance</th><th>Current</th><th>30d</th>
                <th>60d</th><th>90d</th><th>120+d</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <div class="summary">
            <p><strong>Total Customers:</strong> {report.customer_count}</p>
            <p><strong>Total Outstanding:</strong> {report.total_outstanding}</p>
            <p><strong>Total Purchases:</strong> {report.total_purchases}</p>
        </div>
        </body></html>"""


    def _render_supplier_report_html(
        self, report: SupplierReportResult
    ) -> str:
        """Render supplier report as HTML."""
        rows_html = ""
        for row in report.rows:
            rows_html += f"""
            <tr>
                <td>{row.supplier_name}</td>
                <td class="right">{row.total_purchases}</td>
                <td class="right">{row.purchase_count}</td>
                <td class="right">{row.outstanding_balance}</td>
                <td class="right">{row.current}</td>
                <td class="right">{row.days_30}</td>
                <td class="right">{row.days_60}</td>
                <td class="right">{row.days_90}</td>
                <td class="right">{row.days_120_plus}</td>
            </tr>"""

        return f"""
        <html><head>{self._base_css()}</head><body>
        <h1>Supplier Report</h1>
        <p>Period: {report.date_range.start_date} to {report.date_range.end_date}</p>
        <table>
            <thead><tr>
                <th>Supplier</th><th>Purchases</th><th>Count</th>
                <th>Balance</th><th>Current</th><th>30d</th>
                <th>60d</th><th>90d</th><th>120+d</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <div class="summary">
            <p><strong>Total Suppliers:</strong> {report.supplier_count}</p>
            <p><strong>Total Outstanding:</strong> {report.total_outstanding}</p>
            <p><strong>Total Purchases:</strong> {report.total_purchases}</p>
        </div>
        </body></html>"""

    def _render_financial_summary_html(
        self, report: FinancialSummaryResult
    ) -> str:
        """Render financial summary as HTML."""
        return f"""
        <html><head>{self._base_css()}</head><body>
        <h1>Financial Summary</h1>
        <p>Period: {report.date_range.start_date} to {report.date_range.end_date}</p>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Sales Revenue</td><td class="right">{report.total_sales_revenue}</td></tr>
            <tr><td>Cost of Goods Sold</td><td class="right">{report.cost_of_goods_sold}</td></tr>
            <tr><td>Gross Margin</td><td class="right">{report.gross_margin}</td></tr>
            <tr><td>Gross Margin %</td><td class="right">{report.gross_margin_percentage:.2f}%</td></tr>
            <tr><td>Accounts Receivable</td><td class="right">{report.accounts_receivable}</td></tr>
            <tr><td>Accounts Payable</td><td class="right">{report.accounts_payable}</td></tr>
            <tr><td>Number of Sales</td><td class="right">{report.sale_count}</td></tr>
            <tr><td>Purchase Orders</td><td class="right">{report.purchase_count}</td></tr>
        </table>
        </body></html>"""
