"""Business settings router for managing company profile.

Provides the following endpoints:
- GET  /api/v1/business-settings  - Get current business settings
- PUT  /api/v1/business-settings  - Update business settings (Admin only)

Business settings are used on invoices, receipts, and reports.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.business_settings import BusinessSettings
from app.models.user import User, UserRole
from app.schemas.business_settings import (
    BusinessSettingsResponse,
    BusinessSettingsUpdate,
)

router = APIRouter(prefix="/api/v1/business-settings", tags=["Business Settings"])


async def _get_or_create_settings(db: AsyncSession) -> BusinessSettings:
    """Get the single business settings row, creating it if it doesn't exist."""
    result = await db.execute(select(BusinessSettings).limit(1))
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = BusinessSettings(business_name="My Business")
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    return settings


@router.get(
    "",
    response_model=BusinessSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get business settings",
    description="Retrieve the current business profile settings. Accessible by all authenticated users.",
)
async def get_business_settings(
    db: DbSession,
    current_user: CurrentUser,
) -> BusinessSettingsResponse:
    """Get current business settings."""
    settings = await _get_or_create_settings(db)
    await db.commit()
    return BusinessSettingsResponse.model_validate(settings)


@router.put(
    "",
    response_model=BusinessSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update business settings",
    description="Update business profile settings. Admin only.",
)
async def update_business_settings(
    request: BusinessSettingsUpdate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.ADMIN)
    ),
) -> BusinessSettingsResponse:
    """Update business settings. Admin only."""
    settings = await _get_or_create_settings(db)

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_by = str(current_user.id)

    await db.commit()
    await db.refresh(settings)
    return BusinessSettingsResponse.model_validate(settings)
