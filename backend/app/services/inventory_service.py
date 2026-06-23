"""Inventory service implementing spare parts CRUD and search operations.

Provides create, read, update, and soft-delete operations for spare parts,
as well as search functionality across multiple attributes.

Satisfies Requirements:
- 3.1: Store spare parts with all required attributes
- 3.2: Enforce unique constraints on part_number and barcode
- 3.4: Support hierarchical categorization
- 3.5: Search by part_number, barcode, name, brand, category, vehicle_compatibility
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.spare_part import SparePart
from app.schemas.spare_part import SparePartCreate, SparePartUpdate


# =============================================================================
# Custom Exceptions
# =============================================================================


class DuplicatePartNumberError(Exception):
    """Raised when a part_number already exists for an active spare part."""

    def __init__(self, part_number: str):
        self.message = f"Part number '{part_number}' already exists"
        super().__init__(self.message)


class DuplicateBarcodeError(Exception):
    """Raised when a barcode already exists for an active spare part."""

    def __init__(self, barcode: str):
        self.message = f"Barcode '{barcode}' already exists"
        super().__init__(self.message)


class SparePartNotFoundError(Exception):
    """Raised when a spare part with the given ID is not found."""

    def __init__(self, spare_part_id: UUID):
        self.message = f"Spare part with ID '{spare_part_id}' not found"
        super().__init__(self.message)


class CategoryNotFoundError(Exception):
    """Raised when a referenced category does not exist."""

    def __init__(self, category_id: UUID):
        self.message = f"Category with ID '{category_id}' not found"
        super().__init__(self.message)


# =============================================================================
# Inventory Service
# =============================================================================


class InventoryService:
    """Service handling spare parts CRUD and search operations.

    All methods operate on non-deleted (active) records only, respecting
    the soft-delete pattern used throughout the ERP system.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the inventory service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    async def create_spare_part(
        self, data: SparePartCreate, created_by: Optional[str] = None
    ) -> SparePart:
        """Create a new spare part record.

        Validates uniqueness of part_number and barcode (Requirement 3.2),
        and verifies the referenced category exists (Requirement 3.4).

        Args:
            data: Validated spare part creation data.
            created_by: User identifier performing the creation.

        Returns:
            The newly created SparePart instance.

        Raises:
            DuplicatePartNumberError: If part_number already exists.
            DuplicateBarcodeError: If barcode already exists.
            CategoryNotFoundError: If the referenced category doesn't exist.
        """
        # Check unique part_number among active records
        await self._validate_unique_part_number(data.part_number)

        # Check unique barcode among active records (if provided)
        if data.barcode:
            await self._validate_unique_barcode(data.barcode)

        # Validate category exists
        await self._validate_category_exists(data.category_id)

        # Validate subcategory exists (if provided)
        if data.subcategory_id:
            await self._validate_category_exists(data.subcategory_id)

        spare_part = SparePart(
            part_number=data.part_number,
            barcode=data.barcode,
            name=data.name,
            description=data.description,
            brand=data.brand,
            category_id=data.category_id,
            subcategory_id=data.subcategory_id,
            vehicle_compatibility=data.vehicle_compatibility,
            unit_of_measure=data.unit_of_measure,
            cost_price=data.cost_price,
            selling_price=data.selling_price,
            min_stock_level=data.min_stock_level,
            max_stock_level=data.max_stock_level,
            reorder_quantity=data.reorder_quantity,
            created_by=created_by,
        )
        self.db.add(spare_part)
        await self.db.flush()
        await self.db.refresh(spare_part)
        return spare_part

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_spare_part(self, spare_part_id: UUID) -> SparePart:
        """Retrieve a single spare part by ID.

        Args:
            spare_part_id: UUID of the spare part to retrieve.

        Returns:
            The SparePart instance.

        Raises:
            SparePartNotFoundError: If no active spare part with that ID exists.
        """
        stmt = select(SparePart).filter(
            SparePart.id == spare_part_id,
            SparePart.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        spare_part = result.scalar_one_or_none()

        if spare_part is None:
            raise SparePartNotFoundError(spare_part_id)

        return spare_part

    async def list_spare_parts(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SparePart], int]:
        """List spare parts with pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of spare parts, total count).
        """
        # Count total active spare parts
        count_stmt = select(func.count(SparePart.id)).filter(
            SparePart.deleted_at.is_(None)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(SparePart)
            .filter(SparePart.deleted_at.is_(None))
            .order_by(SparePart.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        spare_parts = list(result.scalars().all())

        return spare_parts, total

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    async def update_spare_part(
        self,
        spare_part_id: UUID,
        data: SparePartUpdate,
        updated_by: Optional[str] = None,
    ) -> SparePart:
        """Update an existing spare part's attributes.

        Only non-None fields in the update data are applied. Validates
        uniqueness of part_number and barcode if changed (Requirement 3.2).

        Args:
            spare_part_id: UUID of the spare part to update.
            data: Validated partial update data.
            updated_by: User identifier performing the update.

        Returns:
            The updated SparePart instance.

        Raises:
            SparePartNotFoundError: If no active spare part with that ID exists.
            DuplicatePartNumberError: If new part_number already exists.
            DuplicateBarcodeError: If new barcode already exists.
            CategoryNotFoundError: If the new category doesn't exist.
        """
        spare_part = await self.get_spare_part(spare_part_id)

        # Validate uniqueness if part_number is being changed
        if data.part_number is not None and data.part_number != spare_part.part_number:
            await self._validate_unique_part_number(data.part_number)

        # Validate uniqueness if barcode is being changed
        if data.barcode is not None and data.barcode != spare_part.barcode:
            await self._validate_unique_barcode(data.barcode)

        # Validate category if being changed
        if data.category_id is not None:
            await self._validate_category_exists(data.category_id)

        # Validate subcategory if being changed
        if data.subcategory_id is not None:
            await self._validate_category_exists(data.subcategory_id)

        # Apply updates for non-None fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(spare_part, field, value)

        if updated_by:
            spare_part.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(spare_part)
        return spare_part

    # -------------------------------------------------------------------------
    # Soft Delete
    # -------------------------------------------------------------------------

    async def delete_spare_part(
        self, spare_part_id: UUID, deleted_by: Optional[str] = None
    ) -> SparePart:
        """Soft-delete a spare part (Requirement 1.2).

        Marks the record with deleted_at and deleted_by timestamps instead
        of physically removing it from the database.

        Args:
            spare_part_id: UUID of the spare part to delete.
            deleted_by: User identifier performing the deletion.

        Returns:
            The soft-deleted SparePart instance.

        Raises:
            SparePartNotFoundError: If no active spare part with that ID exists.
        """
        spare_part = await self.get_spare_part(spare_part_id)
        spare_part.soft_delete(deleted_by=deleted_by)
        await self.db.flush()
        return spare_part

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search_spare_parts(
        self,
        q: Optional[str] = None,
        part_number: Optional[str] = None,
        barcode: Optional[str] = None,
        name: Optional[str] = None,
        brand: Optional[str] = None,
        category_id: Optional[UUID] = None,
        vehicle_compatibility: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SparePart], int]:
        """Search spare parts with multiple filter criteria.

        Satisfies Requirement 3.5: Search by part_number, barcode, name,
        brand, category, and vehicle_compatibility.

        Args:
            q: General search term (matches part_number, barcode, name, brand).
            part_number: Filter by partial part number match.
            barcode: Filter by exact barcode match.
            name: Filter by partial name match.
            brand: Filter by brand name (partial match).
            category_id: Filter by category UUID (includes subcategory matches).
            vehicle_compatibility: Filter by vehicle compatibility text.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of matching spare parts, total count).
        """
        base_filter = SparePart.deleted_at.is_(None)

        # Build dynamic filters
        filters = [base_filter]

        if q:
            search_term = f"%{q}%"
            filters.append(
                or_(
                    SparePart.part_number.ilike(search_term),
                    SparePart.barcode.ilike(search_term),
                    SparePart.name.ilike(search_term),
                    SparePart.brand.ilike(search_term),
                )
            )

        if part_number:
            filters.append(SparePart.part_number.ilike(f"%{part_number}%"))

        if barcode:
            filters.append(SparePart.barcode == barcode)

        if name:
            filters.append(SparePart.name.ilike(f"%{name}%"))

        if brand:
            filters.append(SparePart.brand.ilike(f"%{brand}%"))

        if category_id:
            filters.append(
                or_(
                    SparePart.category_id == category_id,
                    SparePart.subcategory_id == category_id,
                )
            )

        if vehicle_compatibility:
            # Search within JSON array using cast to text for ILIKE
            filters.append(
                SparePart.vehicle_compatibility.cast(String).ilike(
                    f"%{vehicle_compatibility}%"
                )
            )

        # Count total matches
        count_stmt = select(func.count(SparePart.id)).filter(*filters)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(SparePart)
            .filter(*filters)
            .order_by(SparePart.name.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        spare_parts = list(result.scalars().all())

        return spare_parts, total

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    async def _validate_unique_part_number(
        self, part_number: str, exclude_id: Optional[UUID] = None
    ) -> None:
        """Validate that part_number is unique among active records."""
        stmt = select(SparePart.id).filter(
            SparePart.part_number == part_number,
            SparePart.deleted_at.is_(None),
        )
        if exclude_id:
            stmt = stmt.filter(SparePart.id != exclude_id)

        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise DuplicatePartNumberError(part_number)

    async def _validate_unique_barcode(
        self, barcode: str, exclude_id: Optional[UUID] = None
    ) -> None:
        """Validate that barcode is unique among active records."""
        stmt = select(SparePart.id).filter(
            SparePart.barcode == barcode,
            SparePart.deleted_at.is_(None),
        )
        if exclude_id:
            stmt = stmt.filter(SparePart.id != exclude_id)

        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise DuplicateBarcodeError(barcode)

    async def _validate_category_exists(self, category_id: UUID) -> None:
        """Validate that a category with the given ID exists and is active."""
        stmt = select(Category.id).filter(
            Category.id == category_id,
            Category.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise CategoryNotFoundError(category_id)
