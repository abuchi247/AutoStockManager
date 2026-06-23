"""Invoice router for invoice generation and retrieval endpoints.

Provides the following endpoints:
- GET    /api/v1/invoices/{id}/pdf         - Download invoice PDF by ID
- POST   /api/v1/invoices/generate         - Generate invoice for a sale
- GET    /api/v1/invoices/by-sale/{sale_id} - Get invoice by sale ID

Satisfies Requirements: 14.5
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.invoice import InvoiceGenerateRequest, InvoiceResponse
from app.services.invoice_service import (
    InvoiceAlreadyExistsError,
    InvoiceNotFoundError,
    InvoiceService,
    SaleNotConfirmedError,
    SaleNotFoundError,
)

router = APIRouter(prefix="/api/v1/invoices", tags=["Invoices"])


def _get_invoice_service(db: AsyncSession) -> InvoiceService:
    """Create an InvoiceService instance."""
    return InvoiceService(db=db)


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/generate",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate invoice for a sale",
    description="Generate a PDF invoice for a confirmed sale. Supports A4 and THERMAL formats.",
    responses={
        400: {"description": "Sale not confirmed or validation error"},
        404: {"description": "Sale not found"},
        409: {"description": "Invoice already exists for this sale/format"},
    },
)
async def generate_invoice(
    request: InvoiceGenerateRequest,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> InvoiceResponse:
    """Generate a PDF invoice for a confirmed sale.

    Requirements:
    - 14.1: PDF invoices with company logo, details, line items, totals
    - 14.2: Support A4 and thermal formats
    - 14.3: Embed QR code with invoice number and total
    - 14.4: Embed barcode for scanning
    - 14.5: Store generated PDF for future retrieval
    """
    service = _get_invoice_service(db)

    try:
        invoice = await service.generate_invoice_pdf(
            sale_id=request.sale_id,
            format=request.format,
            overwrite=request.overwrite,
        )
        await db.commit()
        await db.refresh(invoice)
        return InvoiceResponse.model_validate(invoice)
    except SaleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except SaleNotConfirmedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except InvoiceAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/by-sale/{sale_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get invoice by sale ID",
    description="Retrieve invoice metadata by sale ID and optional format filter.",
    responses={
        404: {"description": "Invoice not found for the given sale"},
    },
)
async def get_invoice_by_sale(
    sale_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
    format: str = Query(default="A4", description="Invoice format: A4 or THERMAL"),
) -> InvoiceResponse:
    """Get invoice metadata by sale ID.

    Requirements:
    - 14.5: Store generated PDF for future retrieval
    """
    service = _get_invoice_service(db)

    invoice = await service.get_invoice_by_sale(sale_id=sale_id, format=format)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice not found for sale '{sale_id}' in format '{format}'",
        )

    return InvoiceResponse.model_validate(invoice)


@router.get(
    "/{invoice_id}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download invoice PDF",
    description="Download the PDF file for an invoice by its ID.",
    responses={
        404: {"description": "Invoice not found"},
    },
)
async def download_invoice_pdf(
    invoice_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> Response:
    """Download invoice PDF by invoice ID.

    Returns the raw PDF binary with appropriate content-type header
    for browser download/display.

    Requirements:
    - 14.5: Store generated PDF for future retrieval
    """
    service = _get_invoice_service(db)

    try:
        invoice = await service.get_invoice_by_id(invoice_id)
    except InvoiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID '{invoice_id}' not found",
        )

    filename = f"invoice_{invoice.invoice_number}.pdf"

    return Response(
        content=invoice.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
