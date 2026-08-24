"""Business settings router for managing company profile.

Provides the following endpoints:
- GET  /api/v1/business-settings  - Get current business settings (any role)
- PUT  /api/v1/business-settings  - Update business settings (Admin only)

phones and bank_accounts are stored as JSONB arrays.
The legacy scalar columns (phone, bank_name, bank_account_number,
bank_account_name) are no longer written — migration 0009 moved any
existing data into the arrays.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.services.permission_service import require_permission
from app.models.business_settings import BusinessSettings
from app.models.user import User, UserRole
from app.schemas.business_settings import (
    BusinessSettingsResponse,
    BusinessSettingsUpdate,
)

router = APIRouter(prefix="/api/v1/business-settings", tags=["Business Settings"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_list(value: object) -> list:
    """Ensure a value from JSONB storage is always a plain Python list."""
    if isinstance(value, list):
        return value
    return []


async def _get_or_create_settings(db: AsyncSession) -> BusinessSettings:
    """Get the single business settings row, creating it if it doesn't exist."""
    result = await db.execute(select(BusinessSettings).limit(1))
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = BusinessSettings(
            business_name="My Business",
            phones=[],
            bank_accounts=[],
        )
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    return settings


def _to_response(settings: BusinessSettings) -> BusinessSettingsResponse:
    """Build a validated response from the ORM object.

    Ensures JSONB columns are always returned as lists and each element
    is validated through the Pydantic sub-models.
    """
    return BusinessSettingsResponse(
        id=settings.id,
        business_name=settings.business_name,
        address=settings.address,
        email=settings.email,
        tax_id=settings.tax_id,
        website=settings.website,
        logo_base64=settings.logo_base64,
        invoice_footer=settings.invoice_footer,
        phones=_coerce_list(settings.phones),
        bank_accounts=_coerce_list(settings.bank_accounts),
        updated_at=settings.updated_at,
        updated_by=settings.updated_by,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=BusinessSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get business settings",
    description="Retrieve the current business profile. Accessible by all authenticated users.",
)
async def get_business_settings(
    db: DbSession,
    current_user: CurrentUser,
) -> BusinessSettingsResponse:
    """Get current business settings."""
    settings = await _get_or_create_settings(db)
    await db.commit()
    return _to_response(settings)


@router.put(
    "",
    response_model=BusinessSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update business settings",
    description=(
        "Update business profile settings. Admin only. "
        "Supports up to 10 phone numbers and 10 bank accounts."
    ),
)
async def update_business_settings(
    request: BusinessSettingsUpdate,
    db: DbSession,
    current_user: User = Depends(require_permission("system_settings")),
) -> BusinessSettingsResponse:
    """Update business settings. Admin only."""
    settings = await _get_or_create_settings(db)

    update_data = request.model_dump(exclude_unset=True)

    # Process logo: resize for invoice rendering compatibility
    if "logo_base64" in update_data and update_data["logo_base64"]:
        update_data["logo_base64"] = _process_logo(update_data["logo_base64"])

    # Serialize Pydantic sub-models to plain dicts before storing in JSONB
    if "phones" in update_data and update_data["phones"] is not None:
        update_data["phones"] = [
            p.model_dump() if hasattr(p, "model_dump") else dict(p)
            for p in update_data["phones"]
        ]

    if "bank_accounts" in update_data and update_data["bank_accounts"] is not None:
        update_data["bank_accounts"] = [
            b.model_dump() if hasattr(b, "model_dump") else dict(b)
            for b in update_data["bank_accounts"]
        ]

    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_by = str(current_user.id)

    await db.commit()
    await db.refresh(settings)
    return _to_response(settings)


# ---------------------------------------------------------------------------
# Logo processing helper
# ---------------------------------------------------------------------------

def _process_logo(logo_data: str) -> str:
    """Resize the uploaded logo to max 200×200 px and return a PNG data URL.

    Strips any existing data-URL prefix, decodes, resizes with Pillow
    (LANCZOS), saves as PNG, and returns a clean data URL ready for
    WeasyPrint. Falls back to the original string on any error.
    """
    import base64
    import io

    try:
        raw_b64 = logo_data.split(",", 1)[1] if ("," in logo_data and logo_data.startswith("data:")) else logo_data
        image_bytes = base64.b64decode(raw_b64)

        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.thumbnail((200, 200), Image.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        output.seek(0)
        return f"data:image/png;base64,{base64.b64encode(output.read()).decode()}"

    except Exception:
        return logo_data
