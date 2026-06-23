"""Barcode management router.

Provides endpoints for barcode generation, lookup, and management:
- GET    /api/v1/spare-parts/{id}/barcode         - Get barcode image for a spare part
- POST   /api/v1/spare-parts/{id}/barcode/generate - Generate system barcode for a part
- POST   /api/v1/spare-parts/{id}/barcode/assign   - Assign manufacturer barcode
- GET    /api/v1/barcodes/lookup                   - Lookup spare part by barcode scan
- POST   /api/v1/barcodes/decode                   - Decode barcode metadata

Satisfies Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.barcode import (
    BarcodeAssignRequest,
    BarcodeDecodeResponse,
    BarcodeGenerateResponse,
    BarcodeInfoResponse,
    BarcodeLookupResponse,
)
from app.services.barcode_service import (
    BarcodeAlreadyExistsError,
    BarcodeNotFoundError,
    BarcodeService,
    InvalidBarcodeError,
    SparePartNotFoundError,
)
from app.utils.barcode_generator import BarcodeGenerationError

router = APIRouter(tags=["Barcodes"])


def _get_barcode_service(db) -> BarcodeService:
    """Create a BarcodeService instance."""
    return BarcodeService(db=db)


# =============================================================================
# Barcode Image Endpoint
# =============================================================================


@router.get(
    "/api/v1/spare-parts/{spare_part_id}/barcode",
    summary="Get barcode image for a spare part",
    description="Returns the barcode image as SVG or PNG. Generates a system barcode if none exists.",
    responses={
        200: {
            "content": {
                "image/svg+xml": {},
                "image/png": {},
            },
            "description": "Barcode image",
        },
        404: {"description": "Spare part not found"},
    },
)
async def get_barcode_image(
    spare_part_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    format: str = Query(
        default="svg",
        pattern="^(svg|png)$",
        description="Image format: svg or png",
    ),
    include_text: bool = Query(
        default=True,
        description="Include human-readable text below the barcode",
    ),
) -> Response:
    """Get the barcode image for a spare part.

    Returns the barcode as an SVG or PNG image. If the part doesn't have
    a barcode assigned, a system barcode is generated automatically.

    Satisfies Requirements:
    - 10.4: Generate barcode labels in printable format
    - 10.5: Encode system-generated barcodes in Code 128 format
    """
    service = _get_barcode_service(db)

    try:
        image_bytes, content_type = await service.get_barcode_image(
            spare_part_id=spare_part_id,
            format=format,
            include_text=include_text,
        )
        await db.commit()
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=barcode-{spare_part_id}.{format}",
            },
        )
    except SparePartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )
    except BarcodeGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Barcode generation failed: {e.message}",
        )


# =============================================================================
# Barcode Generation Endpoint
# =============================================================================


@router.post(
    "/api/v1/spare-parts/{spare_part_id}/barcode/generate",
    response_model=BarcodeGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a system barcode for a spare part",
    description="Generate and assign a Code 128 system barcode to a spare part.",
    responses={
        404: {"description": "Spare part not found"},
        409: {"description": "Barcode already exists"},
    },
)
async def generate_barcode(
    spare_part_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
    overwrite: bool = Query(
        default=False,
        description="Replace existing barcode if True",
    ),
) -> BarcodeGenerateResponse:
    """Generate a system barcode for a spare part.

    Creates a unique Code 128 barcode with ASM- prefix and assigns it
    to the spare part.

    Satisfies Requirement 10.1: Generate unique system barcodes for parts
    without manufacturer barcode.
    """
    service = _get_barcode_service(db)

    try:
        barcode_value = await service.generate_barcode_for_part(
            spare_part_id=spare_part_id,
            overwrite=overwrite,
        )
        await db.commit()
        return BarcodeGenerateResponse(
            spare_part_id=spare_part_id,
            barcode=barcode_value,
            barcode_type="system",
            message="System barcode generated successfully",
        )
    except SparePartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )
    except BarcodeAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Spare part already has a barcode. Use overwrite=true to replace.",
        )


# =============================================================================
# Barcode Assignment Endpoint
# =============================================================================


@router.post(
    "/api/v1/spare-parts/{spare_part_id}/barcode/assign",
    response_model=BarcodeInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign a manufacturer barcode to a spare part",
    description="Assign a manufacturer-provided barcode to a spare part.",
    responses={
        400: {"description": "Invalid barcode value"},
        404: {"description": "Spare part not found"},
        409: {"description": "Barcode already in use"},
    },
)
async def assign_barcode(
    spare_part_id: UUID,
    request: BarcodeAssignRequest,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> BarcodeInfoResponse:
    """Assign a manufacturer-provided barcode to a spare part.

    Validates the barcode value for Code 128 compatibility and ensures
    uniqueness before assignment.

    Satisfies Requirement 10.2: Support storing both manufacturer and
    system-generated barcodes.
    """
    service = _get_barcode_service(db)

    try:
        barcode_value = await service.assign_manufacturer_barcode(
            spare_part_id=spare_part_id,
            barcode_value=request.barcode,
        )
        await db.commit()

        # Re-fetch the spare part to get full details
        spare_part = await service.lookup_by_barcode(barcode_value)
        decoded = service.decode_barcode(barcode_value)

        return BarcodeInfoResponse(
            spare_part_id=spare_part.id,
            barcode=barcode_value,
            barcode_type=decoded["type"],
            part_number=spare_part.part_number,
            part_name=spare_part.name,
        )
    except SparePartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )
    except InvalidBarcodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except BarcodeAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This barcode is already assigned to another spare part.",
        )


# =============================================================================
# Barcode Lookup Endpoint
# =============================================================================


@router.get(
    "/api/v1/barcodes/lookup",
    response_model=BarcodeLookupResponse,
    status_code=status.HTTP_200_OK,
    summary="Look up a spare part by barcode",
    description="Scan/lookup a spare part by its barcode value. Target: <500ms response.",
    responses={
        404: {"description": "No spare part found with this barcode"},
    },
)
async def lookup_barcode(
    db: DbSession,
    current_user: CurrentUser,
    barcode: str = Query(
        min_length=1,
        max_length=255,
        description="The barcode value to look up",
    ),
) -> BarcodeLookupResponse:
    """Look up a spare part by barcode scan.

    Performs an indexed query for fast retrieval. The barcode field has a
    partial unique index for efficient lookups.

    Satisfies Requirement 10.3: Barcode scan lookup returns part record
    within 500ms.
    """
    service = _get_barcode_service(db)

    try:
        spare_part = await service.lookup_by_barcode(barcode)
        decoded = service.decode_barcode(barcode)

        return BarcodeLookupResponse(
            spare_part_id=spare_part.id,
            part_number=spare_part.part_number,
            barcode=spare_part.barcode,
            name=spare_part.name,
            brand=spare_part.brand,
            selling_price=float(spare_part.selling_price),
            unit_of_measure=spare_part.unit_of_measure,
            barcode_type=decoded["type"],
        )
    except BarcodeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No spare part found with barcode '{barcode}'",
        )


# =============================================================================
# Barcode Decode Endpoint
# =============================================================================


@router.get(
    "/api/v1/barcodes/decode",
    response_model=BarcodeDecodeResponse,
    status_code=status.HTTP_200_OK,
    summary="Decode barcode metadata",
    description="Decode a barcode value to determine its type and extract metadata.",
)
async def decode_barcode(
    current_user: CurrentUser,
    barcode: str = Query(
        min_length=1,
        max_length=255,
        description="The barcode value to decode",
    ),
) -> BarcodeDecodeResponse:
    """Decode a barcode value to determine its type and metadata.

    Identifies whether the barcode is system-generated (ASM- prefix) or
    manufacturer-provided and extracts available metadata.

    Satisfies Requirement 10.2: Support storing both manufacturer and
    system-generated barcodes.
    """
    service = BarcodeService(db=None)  # No DB needed for decode
    decoded = service.decode_barcode(barcode)

    return BarcodeDecodeResponse(
        value=decoded["value"],
        type=decoded["type"],
        part_number_hint=decoded["part_number_hint"],
    )
