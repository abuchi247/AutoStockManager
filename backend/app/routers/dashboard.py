"""Dashboard router for KPI widget endpoints.

Provides the following endpoint:
- GET /api/v1/dashboard/kpis - Get dashboard KPIs (role-based content)

All authenticated users can access this endpoint. The returned KPIs
are filtered based on the user's role:
- Salesperson: sees only sales KPIs
- Storekeeper: sees sales + inventory KPIs
- Manager/Admin: sees all KPIs

Satisfies Requirements: 13.1, 13.2, 13.4
"""

from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.report import DashboardKPIResponse, TopSellingProductSchema
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get(
    "/kpis",
    response_model=DashboardKPIResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard KPIs",
    description="Retrieve role-based KPI data for the dashboard. All authenticated users can access this endpoint.",
)
async def get_dashboard_kpis(
    db: DbSession,
    current_user: CurrentUser,
) -> DashboardKPIResponse:
    """Get dashboard KPI data based on user role.

    Requirements:
    - 13.1: KPI widgets for sales, receivables, stock, POs, top products
    - 13.2: All KPI data loads within 3 seconds
    - 13.4: Role-based KPI visibility
    """
    service = DashboardService(db=db)
    kpi_data = await service.get_kpis(user_role=current_user.role)

    # Convert KPIData to response schema
    kpi_dict = kpi_data.to_dict()

    # Build top selling products list if present
    top_products = None
    if kpi_dict.get("top_selling_products"):
        top_products = [
            TopSellingProductSchema(
                spare_part_id=p["spare_part_id"],
                part_name=p["part_name"],
                part_number=p["part_number"],
                total_quantity_sold=p["total_quantity_sold"],
            )
            for p in kpi_dict["top_selling_products"]
        ]

    return DashboardKPIResponse(
        total_sales_today=kpi_dict["total_sales_today"],
        total_sales_month=kpi_dict["total_sales_month"],
        outstanding_receivables=kpi_dict.get("outstanding_receivables"),
        low_stock_count=kpi_dict.get("low_stock_count"),
        pending_po_count=kpi_dict.get("pending_po_count"),
        top_selling_products=top_products,
    )
