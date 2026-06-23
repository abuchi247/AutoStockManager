"""Barcode service for spare parts barcode management.

Provides business logic for barcode generation, lookup, and management
including both manufacturer-provided and system-generated barcodes.

Satisfies Requirements:
- 10.1: Generate unique system barcodes for parts without manufacturer barcode
- 10.2: Support storing both manufacturer and system-generated barcodes
- 10.3: Barcode scan lookup returns part record within 500ms
- 10.4: Generate barcode labels in printable format (standard label sizes)
- 10.5: Encode system-generated barcodes in Code 128 format
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spare_part import SparePart
from app.utils.barcode_generator import (
    BarcodeGenerationError,
    decode_barcode_value,
    generate_barcode_png,
    generate_barcode_svg,
    generate_system_barcode_value,
    validate_barcode_value,
)


# =============================================================================
# Custom Exceptions
# =============================================================================


class SparePartNotFoundError(Exception):
    """Raised when a spare part with the given ID is not found."""

    def __init__(self, spare_part_id: UUID):
        self.message = f"Spare part with ID '{spare_part_id}' not found"
        super().__init__(self.message)


class BarcodeNotFoundError(Exception):
    """Raised when no spare part matches the given barcode."""

    def __init__(self, barcode_value: str):
        self.message = f"No spare part found with barcode '{barcode_value}'"
        super().__init__(self.message)


class BarcodeAlreadyExistsError(Exception):
    """Raised when a spare part already has a barcode assigned."""

    def __init__(self, spare_part_id: UUID):
        self.message = f"Spare part '{spare_part_id}' already has a barcode assigned"
        super().__init__(self.message)


class InvalidBarcodeError(Exception):
    """Raised when a barcode value is invalid for Code 128 encoding."""

    def __init__(self, barcode_value: str):
        self.message = f"Barcode value '{barcode_value}' is not valid for Code 128 encoding"
        super().__init__(self.message)


# =============================================================================
# Barcode Service
# =============================================================================


class BarcodeService:
    """Service handling barcode generation, lookup, and management.

    Supports both manufacturer-provided and system-generated barcodes.
    System-generated barcodes use Code 128 format with an ASM- prefix.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the barcode service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Barcode Generation
    # -------------------------------------------------------------------------

    async def generate_barcode_for_part(
        self, spare_part_id: UUID, overwrite: bool = False
    ) -> str:
        """Generate a system barcode for a spare part that doesn't have one.

        Creates a unique Code 128 barcode value and assigns it to the spare part.

        Args:
            spare_part_id: UUID of the spare part to generate a barcode for.
            overwrite: If True, replace existing barcode. Default False.

        Returns:
            The generated barcode value string.

        Raises:
            SparePartNotFoundError: If the spare part doesn't exist.
            BarcodeAlreadyExistsError: If the part already has a barcode and overwrite is False.

        Satisfies Requirement 10.1: Generate unique system barcodes for parts
        without manufacturer barcode.
        """
        spare_part = await self._get_spare_part(spare_part_id)

        if spare_part.barcode and not overwrite:
            raise BarcodeAlreadyExistsError(spare_part_id)

        # Generate unique barcode value
        barcode_value = generate_system_barcode_value(spare_part.part_number)

        # Ensure uniqueness in database
        while await self._barcode_exists(barcode_value):
            barcode_value = generate_system_barcode_value(spare_part.part_number)

        # Assign barcode to spare part
        spare_part.barcode = barcode_value
        await self.db.flush()

        return barcode_value

    async def get_barcode_image(
        self,
        spare_part_id: UUID,
        format: str = "svg",
        include_text: bool = True,
    ) -> tuple[bytes, str]:
        """Get the barcode image for a spare part.

        Generates a barcode image from the part's barcode value.
        If the part has no barcode, generates a system barcode first.

        Args:
            spare_part_id: UUID of the spare part.
            format: Image format - "svg" or "png". Default "svg".
            include_text: Whether to include human-readable text. Default True.

        Returns:
            Tuple of (image_bytes, content_type).

        Raises:
            SparePartNotFoundError: If the spare part doesn't exist.
            BarcodeGenerationError: If barcode image generation fails.

        Satisfies Requirements:
        - 10.4: Generate barcode labels in printable format
        - 10.5: Encode system-generated barcodes in Code 128 format
        """
        spare_part = await self._get_spare_part(spare_part_id)

        # If no barcode exists, generate one
        if not spare_part.barcode:
            await self.generate_barcode_for_part(spare_part_id)
            await self.db.refresh(spare_part)

        barcode_value = spare_part.barcode

        if format.lower() == "png":
            image_bytes = generate_barcode_png(barcode_value, include_text=include_text)
            content_type = "image/png"
        else:
            image_bytes = generate_barcode_svg(barcode_value, include_text=include_text)
            content_type = "image/svg+xml"

        return image_bytes, content_type

    # -------------------------------------------------------------------------
    # Barcode Lookup
    # -------------------------------------------------------------------------

    async def lookup_by_barcode(self, barcode_value: str) -> SparePart:
        """Look up a spare part by its barcode value.

        Performs an indexed query on the barcode field for fast retrieval.
        Target: return within 500ms (Requirement 10.3).

        Args:
            barcode_value: The barcode string to search for.

        Returns:
            The matching SparePart instance.

        Raises:
            BarcodeNotFoundError: If no active spare part has this barcode.

        Satisfies Requirement 10.3: Barcode scan lookup returns part record
        within 500ms.
        """
        stmt = select(SparePart).filter(
            SparePart.barcode == barcode_value,
            SparePart.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        spare_part = result.scalar_one_or_none()

        if spare_part is None:
            raise BarcodeNotFoundError(barcode_value)

        return spare_part

    # -------------------------------------------------------------------------
    # Barcode Decoding
    # -------------------------------------------------------------------------

    def decode_barcode(self, barcode_value: str) -> dict:
        """Decode a barcode value and determine its type.

        Identifies whether a barcode is system-generated or manufacturer-provided
        and extracts available metadata.

        Args:
            barcode_value: The barcode string to decode.

        Returns:
            Dictionary with barcode metadata (type, value, part_number_hint).

        Satisfies Requirement 10.2: Support storing both manufacturer and
        system-generated barcodes.
        """
        return decode_barcode_value(barcode_value)

    # -------------------------------------------------------------------------
    # Barcode Assignment
    # -------------------------------------------------------------------------

    async def assign_manufacturer_barcode(
        self, spare_part_id: UUID, barcode_value: str
    ) -> str:
        """Assign a manufacturer-provided barcode to a spare part.

        Validates the barcode value and ensures uniqueness before assignment.

        Args:
            spare_part_id: UUID of the spare part.
            barcode_value: The manufacturer-provided barcode string.

        Returns:
            The assigned barcode value.

        Raises:
            SparePartNotFoundError: If the spare part doesn't exist.
            InvalidBarcodeError: If the barcode value is not valid for Code 128.
            BarcodeAlreadyExistsError: If another part already uses this barcode.

        Satisfies Requirement 10.2: Support storing both manufacturer and
        system-generated barcodes.
        """
        if not validate_barcode_value(barcode_value):
            raise InvalidBarcodeError(barcode_value)

        spare_part = await self._get_spare_part(spare_part_id)

        # Check if barcode is already used by another part
        if await self._barcode_exists(barcode_value, exclude_id=spare_part_id):
            raise BarcodeAlreadyExistsError(spare_part_id)

        spare_part.barcode = barcode_value
        await self.db.flush()

        return barcode_value

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    async def _get_spare_part(self, spare_part_id: UUID) -> SparePart:
        """Retrieve a spare part by ID, raising error if not found."""
        stmt = select(SparePart).filter(
            SparePart.id == spare_part_id,
            SparePart.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        spare_part = result.scalar_one_or_none()

        if spare_part is None:
            raise SparePartNotFoundError(spare_part_id)

        return spare_part

    async def _barcode_exists(
        self, barcode_value: str, exclude_id: Optional[UUID] = None
    ) -> bool:
        """Check if a barcode value already exists in the database."""
        stmt = select(SparePart.id).filter(
            SparePart.barcode == barcode_value,
            SparePart.deleted_at.is_(None),
        )
        if exclude_id:
            stmt = stmt.filter(SparePart.id != exclude_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
