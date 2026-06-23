"""Reports router for generating business reports.

Provides the following endpoints:
- GET /api/v1/reports/sales             - Generate sales report
- GET /api/v1/reports/inventory         - Generate inventory report
- GET /api/v1/reports/customers         - Generate customer report
- GET /api/v1/reports/suppliers         - Generate supplier report
- GET /api/v1/reports/financial-summary - Generate financial summary

All endpoints are restricted to Manager and Admin roles.
Supports JSON, CSV, and PDF export formats.

Satisfies Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7
"""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.report import (
    CustomerReportResponse,
    CustomerReportRowSchema,
    FinancialSummaryResponse,
    InventoryReportResponse,
    InventoryReportRowSchema,
    SalesReportResponse,
    SalesReportRowSchema,
    SupplierReportResponse,
    SupplierReportRowSchema,
)
from app.services.report_service import (
    DateRange,
    ReportService,
    SalesReportFilters,
)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def _get_report_service(db: AsyncSession) -> ReportService:
    """Create a ReportService instance."""
    return ReportService(db=db)


# =============================================================================
# Sales Report
# =============================================================================


@router.get(
    "/sales",
    summary="Generate sales report",
    description="Generate a sales report with optional filters. Manager and Admin only. Supports JSON, CSV, and PDF formats.",
)
async def get_sales_report(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    start_date: date = Query(
        default=None,
        description="Start date for the report (defaults to 30 days ago)",
    ),
    end_date: date = Query(
        default=None,
        description="End date for the report (defaults to today)",
    ),
    location_id: Optional[UUID] = Query(default=None, description="Filter by location"),
    salesperson_id: Optional[UUID] = Query(default=None, description="Filter by salesperson"),
    customer_id: Optional[UUID] = Query(default=None, description="Filter by customer"),
    category_id: Optional[UUID] = Query(default=None, description="Filter by category"),
    format: str = Query(default="json", description="Export format: json, csv, or pdf"),
):
    """Generate a sales report.

    Requirements:
    - 12.1: Sales reports filterable by date range, location, salesperson, customer, category
    - 12.6: Support export in PDF and CSV formats
    - 12.7: Date range filtering with minimum granularity of one day
    """
    # Default date range: last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    service = _get_report_service(db)
    filters = SalesReportFilters(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        location_id=location_id,
        salesperson_id=salesperson_id,
        customer_id=customer_id,
        category_id=category_id,
    )

    report = await service.generate_sales_report(filters)

    if format == "csv":
        csv_content = service.export_sales_report_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=sales_report.csv"},
        )
    elif format == "pdf":
        pdf_content = service.export_sales_report_pdf(report)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=sales_report.pdf"},
        )

    # JSON format
    return SalesReportResponse(
        start_date=start_date,
        end_date=end_date,
        location_id=location_id,
        salesperson_id=salesperson_id,
        customer_id=customer_id,
        category_id=category_id,
        rows=[
            SalesReportRowSchema(
                sale_id=row.sale_id,
                invoice_number=row.invoice_number,
                sale_date=row.sale_date,
                customer_name=row.customer_name,
                location_id=row.location_id,
                total_amount=row.total_amount,
                discount_total=row.discount_total,
                tax_amount=row.tax_amount,
                cost_of_goods_sold=row.cost_of_goods_sold,
                gross_margin=row.gross_margin,
            )
            for row in report.rows
        ],
        total_sales=report.total_sales,
        total_cogs=report.total_cogs,
        total_gross_margin=report.total_gross_margin,
        total_discount=report.total_discount,
        sale_count=report.sale_count,
    )


# =============================================================================
# Inventory Report
# =============================================================================


@router.get(
    "/inventory",
    summary="Generate inventory report",
    description="Generate an inventory report with stock levels and valuation. Manager and Admin only.",
)
async def get_inventory_report(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    location_id: Optional[UUID] = Query(default=None, description="Filter by location"),
    category_id: Optional[UUID] = Query(default=None, description="Filter by category"),
    format: str = Query(default="json", description="Export format: json, csv, or pdf"),
):
    """Generate an inventory report.

    Requirements:
    - 12.2: Inventory reports with stock levels, valuation, slow-moving items, below reorder
    - 12.6: Support export in PDF and CSV formats
    """
    service = _get_report_service(db)
    report = await service.generate_inventory_report(
        location_id=location_id,
        category_id=category_id,
    )

    if format == "csv":
        csv_content = service.export_inventory_report_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory_report.csv"},
        )
    elif format == "pdf":
        pdf_content = service.export_inventory_report_pdf(report)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=inventory_report.pdf"},
        )

    # JSON format
    return InventoryReportResponse(
        location_id=location_id,
        category_id=category_id,
        rows=[
            InventoryReportRowSchema(
                spare_part_id=row.spare_part_id,
                part_number=row.part_number,
                name=row.name,
                brand=row.brand,
                category_id=row.category_id,
                location_id=row.location_id,
                current_quantity=row.current_quantity,
                unit_cost=row.unit_cost,
                stock_value=row.stock_value,
                min_stock_level=row.min_stock_level,
                is_below_reorder=row.is_below_reorder,
                last_movement_date=row.last_movement_date,
            )
            for row in report.rows
        ],
        total_stock_value=report.total_stock_value,
        below_reorder_count=report.below_reorder_count,
        slow_moving_count=report.slow_moving_count,
        total_items=report.total_items,
    )


# =============================================================================
# Customer Report
# =============================================================================


@router.get(
    "/customers",
    summary="Generate customer report",
    description="Generate a customer report with purchase history and aging. Manager and Admin only.",
)
async def get_customer_report(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    start_date: date = Query(
        default=None,
        description="Start date for the report (defaults to 30 days ago)",
    ),
    end_date: date = Query(
        default=None,
        description="End date for the report (defaults to today)",
    ),
    customer_id: Optional[UUID] = Query(default=None, description="Filter by specific customer"),
    format: str = Query(default="json", description="Export format: json, csv, or pdf"),
):
    """Generate a customer report.

    Requirements:
    - 12.3: Customer reports with purchase history, outstanding balances, aging
    - 12.6: Support export in PDF and CSV formats
    - 12.7: Date range filtering with minimum granularity of one day
    """
    # Default date range: last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    service = _get_report_service(db)
    date_range = DateRange(start_date=start_date, end_date=end_date)
    report = await service.generate_customer_report(
        date_range=date_range,
        customer_id=customer_id,
    )

    if format == "csv":
        csv_content = service.export_customer_report_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=customer_report.csv"},
        )
    elif format == "pdf":
        pdf_content = service.export_customer_report_pdf(report)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=customer_report.pdf"},
        )

    # JSON format
    return CustomerReportResponse(
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        rows=[
            CustomerReportRowSchema(
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                total_purchases=row.total_purchases,
                purchase_count=row.purchase_count,
                outstanding_balance=row.outstanding_balance,
                current=row.current,
                days_30=row.days_30,
                days_60=row.days_60,
                days_90=row.days_90,
                days_120_plus=row.days_120_plus,
            )
            for row in report.rows
        ],
        total_outstanding=report.total_outstanding,
        total_purchases=report.total_purchases,
        customer_count=report.customer_count,
    )


# =============================================================================
# Supplier Report
# =============================================================================


@router.get(
    "/suppliers",
    summary="Generate supplier report",
    description="Generate a supplier report with purchase history and aging. Manager and Admin only.",
)
async def get_supplier_report(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    start_date: date = Query(
        default=None,
        description="Start date for the report (defaults to 30 days ago)",
    ),
    end_date: date = Query(
        default=None,
        description="End date for the report (defaults to today)",
    ),
    supplier_id: Optional[UUID] = Query(default=None, description="Filter by specific supplier"),
    format: str = Query(default="json", description="Export format: json, csv, or pdf"),
):
    """Generate a supplier report.

    Requirements:
    - 12.4: Supplier reports with purchase history, outstanding balances, aging
    - 12.6: Support export in PDF and CSV formats
    - 12.7: Date range filtering with minimum granularity of one day
    """
    # Default date range: last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    service = _get_report_service(db)
    date_range = DateRange(start_date=start_date, end_date=end_date)
    report = await service.generate_supplier_report(
        date_range=date_range,
        supplier_id=supplier_id,
    )

    if format == "csv":
        csv_content = service.export_supplier_report_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=supplier_report.csv"},
        )
    elif format == "pdf":
        pdf_content = service.export_supplier_report_pdf(report)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=supplier_report.pdf"},
        )

    # JSON format
    return SupplierReportResponse(
        start_date=start_date,
        end_date=end_date,
        supplier_id=supplier_id,
        rows=[
            SupplierReportRowSchema(
                supplier_id=row.supplier_id,
                supplier_name=row.supplier_name,
                total_purchases=row.total_purchases,
                purchase_count=row.purchase_count,
                outstanding_balance=row.outstanding_balance,
                current=row.current,
                days_30=row.days_30,
                days_60=row.days_60,
                days_90=row.days_90,
                days_120_plus=row.days_120_plus,
            )
            for row in report.rows
        ],
        total_outstanding=report.total_outstanding,
        total_purchases=report.total_purchases,
        supplier_count=report.supplier_count,
    )


# =============================================================================
# Financial Summary
# =============================================================================


@router.get(
    "/financial-summary",
    summary="Generate financial summary",
    description="Generate a financial summary report. Manager and Admin only.",
)
async def get_financial_summary(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    start_date: date = Query(
        default=None,
        description="Start date for the report (defaults to 30 days ago)",
    ),
    end_date: date = Query(
        default=None,
        description="End date for the report (defaults to today)",
    ),
    format: str = Query(default="json", description="Export format: json, csv, or pdf"),
):
    """Generate a financial summary.

    Requirements:
    - 12.5: Financial summary with sales revenue, COGS, gross margin, receivables, payables
    - 12.6: Support export in PDF and CSV formats
    - 12.7: Date range filtering with minimum granularity of one day
    """
    # Default date range: last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    service = _get_report_service(db)
    date_range = DateRange(start_date=start_date, end_date=end_date)
    report = await service.generate_financial_summary(date_range=date_range)

    if format == "csv":
        csv_content = service.export_financial_summary_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=financial_summary.csv"},
        )
    elif format == "pdf":
        pdf_content = service.export_financial_summary_pdf(report)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=financial_summary.pdf"},
        )

    # JSON format
    return FinancialSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        total_sales_revenue=report.total_sales_revenue,
        cost_of_goods_sold=report.cost_of_goods_sold,
        gross_margin=report.gross_margin,
        gross_margin_percentage=report.gross_margin_percentage,
        accounts_receivable=report.accounts_receivable,
        accounts_payable=report.accounts_payable,
        sale_count=report.sale_count,
        purchase_count=report.purchase_count,
    )
