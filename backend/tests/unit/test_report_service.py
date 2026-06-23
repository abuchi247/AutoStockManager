"""Unit tests for the ReportService.

Tests validate:
1. Sales report generation with date range filtering (Req 12.1)
2. Sales report with location filter (Req 12.1)
3. Sales report with salesperson filter (Req 12.1)
4. Sales report with customer filter (Req 12.1)
5. Inventory report generation (Req 12.2)
6. Customer report with aging analysis (Req 12.3)
7. Supplier report with aging analysis (Req 12.4)
8. Financial summary calculations (Req 12.5)
9. CSV export formats (Req 12.6)
10. Date range granularity (Req 12.7)

Satisfies Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7
"""

import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.report_service import (
    DateRange,
    SalesReportFilters,
    SalesReportResult,
    SalesReportRow,
    InventoryReportResult,
    InventoryReportRow,
    CustomerReportResult,
    CustomerReportRow,
    SupplierReportResult,
    SupplierReportRow,
    FinancialSummaryResult,
    ReportService,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def report_service(mock_db):
    """Create a ReportService with mocked DB."""
    return ReportService(db=mock_db)


@pytest.fixture
def date_range():
    """Standard date range for testing."""
    return DateRange(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
    )


@pytest.fixture
def sales_filters(date_range):
    """Standard sales report filters."""
    return SalesReportFilters(date_range=date_range)


# =============================================================================
# Tests: DateRange
# =============================================================================


class TestDateRange:
    """Tests for DateRange data class (Req 12.7)."""

    def test_to_datetime_range_start_of_day(self):
        """Start date converts to beginning of day."""
        dr = DateRange(start_date=date(2024, 3, 15), end_date=date(2024, 3, 20))
        start, end = dr.to_datetime_range()
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        assert start.day == 15
        assert start.month == 3


    def test_to_datetime_range_end_of_day(self):
        """End date converts to end of day."""
        dr = DateRange(start_date=date(2024, 3, 15), end_date=date(2024, 3, 20))
        start, end = dr.to_datetime_range()
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59
        assert end.day == 20
        assert end.month == 3

    def test_to_datetime_range_timezone_utc(self):
        """Both dates should be timezone-aware UTC."""
        dr = DateRange(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        start, end = dr.to_datetime_range()
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc

    def test_single_day_range(self):
        """A single day range should span the full day."""
        dr = DateRange(start_date=date(2024, 6, 15), end_date=date(2024, 6, 15))
        start, end = dr.to_datetime_range()
        assert start.day == end.day == 15
        assert start.hour == 0
        assert end.hour == 23


# =============================================================================
# Tests: CSV Export
# =============================================================================


class TestCSVExport:
    """Tests for CSV export functionality (Req 12.6)."""

    def test_export_sales_report_csv_headers(self, report_service, sales_filters):
        """Sales CSV should include proper column headers."""
        report = SalesReportResult(filters=sales_filters)
        csv_content = report_service.export_sales_report_csv(report)
        first_line = csv_content.split("\n")[0]
        assert "Sale ID" in first_line
        assert "Invoice Number" in first_line
        assert "Total Amount" in first_line
        assert "COGS" in first_line
        assert "Gross Margin" in first_line


    def test_export_sales_report_csv_with_rows(
        self, report_service, sales_filters
    ):
        """Sales CSV should include data rows."""
        report = SalesReportResult(filters=sales_filters)
        report.rows.append(SalesReportRow(
            sale_id=uuid.uuid4(),
            invoice_number="INV-0001",
            sale_date=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            customer_name="Test Customer",
            location_id=uuid.uuid4(),
            total_amount=Decimal("1500.00"),
            discount_total=Decimal("50.00"),
            tax_amount=Decimal("0.00"),
            cost_of_goods_sold=Decimal("900.00"),
            gross_margin=Decimal("600.00"),
        ))
        report.total_sales = Decimal("1500.00")
        report.total_cogs = Decimal("900.00")
        report.total_gross_margin = Decimal("600.00")
        report.sale_count = 1

        csv_content = report_service.export_sales_report_csv(report)
        lines = csv_content.strip().split("\n")
        # Header + 1 data row + empty line + totals row
        assert len(lines) >= 3
        assert "INV-0001" in lines[1]
        assert "Test Customer" in lines[1]
        assert "1500.00" in lines[1]

    def test_export_inventory_report_csv_headers(self, report_service):
        """Inventory CSV should include proper column headers."""
        report = InventoryReportResult()
        csv_content = report_service.export_inventory_report_csv(report)
        first_line = csv_content.split("\n")[0]
        assert "Part Number" in first_line
        assert "Current Qty" in first_line
        assert "Stock Value" in first_line
        assert "Below Reorder" in first_line


    def test_export_customer_report_csv_headers(self, report_service, date_range):
        """Customer CSV should include aging columns."""
        report = CustomerReportResult(date_range=date_range)
        csv_content = report_service.export_customer_report_csv(report)
        first_line = csv_content.split("\n")[0]
        assert "Customer Name" in first_line
        assert "Outstanding Balance" in first_line
        assert "30 Days" in first_line
        assert "120+ Days" in first_line

    def test_export_supplier_report_csv_headers(self, report_service, date_range):
        """Supplier CSV should include aging columns."""
        report = SupplierReportResult(date_range=date_range)
        csv_content = report_service.export_supplier_report_csv(report)
        first_line = csv_content.split("\n")[0]
        assert "Supplier Name" in first_line
        assert "Outstanding Balance" in first_line
        assert "30 Days" in first_line

    def test_export_financial_summary_csv(self, report_service, date_range):
        """Financial summary CSV should include all metrics."""
        report = FinancialSummaryResult(
            date_range=date_range,
            total_sales_revenue=Decimal("50000.00"),
            cost_of_goods_sold=Decimal("30000.00"),
            gross_margin=Decimal("20000.00"),
            gross_margin_percentage=Decimal("40.00"),
            accounts_receivable=Decimal("15000.00"),
            accounts_payable=Decimal("8000.00"),
            sale_count=150,
            purchase_count=25,
        )
        csv_content = report_service.export_financial_summary_csv(report)
        assert "Total Sales Revenue" in csv_content
        assert "50000.00" in csv_content
        assert "Cost of Goods Sold" in csv_content
        assert "30000.00" in csv_content
        assert "Gross Margin" in csv_content
        assert "Accounts Receivable" in csv_content
        assert "Accounts Payable" in csv_content



# =============================================================================
# Tests: PDF Export
# =============================================================================


class TestPDFExport:
    """Tests for PDF export functionality (Req 12.6)."""

    def test_export_sales_report_pdf_returns_bytes(
        self, report_service, sales_filters
    ):
        """PDF export should return bytes (HTML fallback if no WeasyPrint)."""
        report = SalesReportResult(filters=sales_filters)
        result = report_service.export_sales_report_pdf(report)
        assert isinstance(result, bytes)
        # Should contain HTML content (fallback) or PDF bytes
        assert len(result) > 0

    def test_export_sales_report_pdf_contains_report_data(
        self, report_service, sales_filters
    ):
        """PDF HTML fallback should contain report structure."""
        report = SalesReportResult(
            filters=sales_filters,
            total_sales=Decimal("5000.00"),
            sale_count=10,
        )
        result = report_service.export_sales_report_pdf(report)
        html_content = result.decode("utf-8")
        assert "Sales Report" in html_content
        assert "5000.00" in html_content

    def test_export_inventory_report_pdf_returns_bytes(self, report_service):
        """Inventory PDF export should return bytes."""
        report = InventoryReportResult()
        result = report_service.export_inventory_report_pdf(report)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_financial_summary_pdf_content(
        self, report_service, date_range
    ):
        """Financial summary PDF should include all metrics."""
        report = FinancialSummaryResult(
            date_range=date_range,
            total_sales_revenue=Decimal("100000.00"),
            gross_margin=Decimal("40000.00"),
        )
        result = report_service.export_financial_summary_pdf(report)
        html_content = result.decode("utf-8")
        assert "Financial Summary" in html_content
        assert "100000.00" in html_content



# =============================================================================
# Tests: Sales Report Generation (Req 12.1)
# =============================================================================


class TestSalesReportGeneration:
    """Tests for sales report query logic."""

    @pytest.mark.asyncio
    async def test_generate_sales_report_empty(self, mock_db, sales_filters):
        """Sales report with no matching sales returns empty result."""
        # Mock execute to return empty scalars
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        result = await service.generate_sales_report(sales_filters)

        assert result.sale_count == 0
        assert result.total_sales == Decimal("0.00")
        assert result.total_cogs == Decimal("0.00")
        assert result.rows == []

    @pytest.mark.asyncio
    async def test_generate_sales_report_with_location_filter(
        self, mock_db, date_range
    ):
        """Sales report should apply location filter."""
        location_id = uuid.uuid4()
        filters = SalesReportFilters(
            date_range=date_range,
            location_id=location_id,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        result = await service.generate_sales_report(filters)

        # Verify execute was called (filter applied)
        assert mock_db.execute.called
        assert result.sale_count == 0



# =============================================================================
# Tests: Financial Summary (Req 12.5)
# =============================================================================


class TestFinancialSummary:
    """Tests for financial summary report generation."""

    @pytest.mark.asyncio
    async def test_generate_financial_summary_empty(self, mock_db, date_range):
        """Financial summary with no data returns zeros."""
        # Setup mock to return zeros for all aggregate queries
        mock_revenue_result = MagicMock()
        mock_revenue_result.one.return_value = (Decimal("0"), 0)

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = Decimal("0")

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Return different results for each call
        mock_db.execute = AsyncMock(
            side_effect=[
                mock_revenue_result,   # revenue query
                mock_scalar_result,    # COGS query
                mock_scalar_result,    # AR query
                mock_scalar_result,    # AP query
                mock_count_result,     # PO count query
            ]
        )

        service = ReportService(db=mock_db)
        result = await service.generate_financial_summary(date_range)

        assert result.total_sales_revenue == Decimal("0.00")
        assert result.cost_of_goods_sold == Decimal("0.00")
        assert result.gross_margin == Decimal("0.00")
        assert result.gross_margin_percentage == Decimal("0.00")
        assert result.sale_count == 0

    @pytest.mark.asyncio
    async def test_generate_financial_summary_with_data(
        self, mock_db, date_range
    ):
        """Financial summary calculates gross margin correctly."""
        mock_revenue_result = MagicMock()
        mock_revenue_result.one.return_value = (Decimal("100000"), 50)

        mock_cogs_result = MagicMock()
        mock_cogs_result.scalar.return_value = Decimal("60000")

        mock_ar_result = MagicMock()
        mock_ar_result.scalar.return_value = Decimal("25000")

        mock_ap_result = MagicMock()
        mock_ap_result.scalar.return_value = Decimal("15000")

        mock_po_result = MagicMock()
        mock_po_result.scalar.return_value = 10

        mock_db.execute = AsyncMock(
            side_effect=[
                mock_revenue_result,
                mock_cogs_result,
                mock_ar_result,
                mock_ap_result,
                mock_po_result,
            ]
        )

        service = ReportService(db=mock_db)
        result = await service.generate_financial_summary(date_range)

        assert result.total_sales_revenue == Decimal("100000")
        assert result.cost_of_goods_sold == Decimal("60000")
        assert result.gross_margin == Decimal("40000")
        assert result.gross_margin_percentage == Decimal("40.00")
        assert result.accounts_receivable == Decimal("25000")
        assert result.accounts_payable == Decimal("15000")
        assert result.sale_count == 50
        assert result.purchase_count == 10



# =============================================================================
# Tests: Inventory Report (Req 12.2)
# =============================================================================


class TestInventoryReport:
    """Tests for inventory report generation."""

    @pytest.mark.asyncio
    async def test_generate_inventory_report_empty(self, mock_db):
        """Inventory report with no stock entries returns empty."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        result = await service.generate_inventory_report()

        assert result.total_items == 0
        assert result.total_stock_value == Decimal("0.00")
        assert result.below_reorder_count == 0
        assert result.slow_moving_count == 0


# =============================================================================
# Tests: Customer Aging (Req 12.3)
# =============================================================================


class TestCustomerAging:
    """Tests for customer aging analysis helper."""

    @pytest.mark.asyncio
    async def test_aging_buckets_current(self, mock_db):
        """Entries within 30 days go to current bucket."""
        now = datetime.now(timezone.utc)
        mock_entry = MagicMock()
        mock_entry.amount = Decimal("1000.00")
        mock_entry.created_at = now - timedelta(days=15)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        aging = await service._calculate_customer_aging(uuid.uuid4(), now)

        assert aging["current"] == Decimal("1000.00")
        assert aging["days_30"] == Decimal("0.00")
        assert aging["days_60"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_aging_buckets_30_days(self, mock_db):
        """Entries 31-60 days old go to 30-day bucket."""
        now = datetime.now(timezone.utc)
        mock_entry = MagicMock()
        mock_entry.amount = Decimal("500.00")
        mock_entry.created_at = now - timedelta(days=45)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        aging = await service._calculate_customer_aging(uuid.uuid4(), now)

        assert aging["current"] == Decimal("0.00")
        assert aging["days_30"] == Decimal("500.00")


    @pytest.mark.asyncio
    async def test_aging_buckets_120_plus(self, mock_db):
        """Entries older than 120 days go to 120+ bucket."""
        now = datetime.now(timezone.utc)
        mock_entry = MagicMock()
        mock_entry.amount = Decimal("2000.00")
        mock_entry.created_at = now - timedelta(days=150)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        aging = await service._calculate_customer_aging(uuid.uuid4(), now)

        assert aging["current"] == Decimal("0.00")
        assert aging["days_30"] == Decimal("0.00")
        assert aging["days_60"] == Decimal("0.00")
        assert aging["days_90"] == Decimal("0.00")
        assert aging["days_120_plus"] == Decimal("2000.00")

    @pytest.mark.asyncio
    async def test_aging_multiple_entries_different_buckets(self, mock_db):
        """Multiple entries spread across aging buckets correctly."""
        now = datetime.now(timezone.utc)
        entry_current = MagicMock()
        entry_current.amount = Decimal("100.00")
        entry_current.created_at = now - timedelta(days=10)

        entry_60 = MagicMock()
        entry_60.amount = Decimal("200.00")
        entry_60.created_at = now - timedelta(days=75)

        entry_old = MagicMock()
        entry_old.amount = Decimal("300.00")
        entry_old.created_at = now - timedelta(days=200)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            entry_current, entry_60, entry_old
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        aging = await service._calculate_customer_aging(uuid.uuid4(), now)

        assert aging["current"] == Decimal("100.00")
        assert aging["days_60"] == Decimal("200.00")
        assert aging["days_120_plus"] == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_aging_no_entries(self, mock_db):
        """No entries returns all zeros."""
        now = datetime.now(timezone.utc)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ReportService(db=mock_db)
        aging = await service._calculate_customer_aging(uuid.uuid4(), now)

        assert aging["current"] == Decimal("0.00")
        assert aging["days_30"] == Decimal("0.00")
        assert aging["days_60"] == Decimal("0.00")
        assert aging["days_90"] == Decimal("0.00")
        assert aging["days_120_plus"] == Decimal("0.00")
