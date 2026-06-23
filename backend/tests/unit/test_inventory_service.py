"""Unit tests for the inventory service (spare parts CRUD and search).

Tests cover:
- Create spare part with validation
- Read spare part by ID
- List spare parts with pagination
- Update spare part with uniqueness checks
- Soft-delete spare part
- Search spare parts by various criteria

Satisfies Requirements: 3.1, 3.2, 3.4, 3.5
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.schemas.spare_part import SparePartCreate, SparePartUpdate
from app.services.inventory_service import (
    CategoryNotFoundError,
    DuplicateBarcodeError,
    DuplicatePartNumberError,
    InventoryService,
    SparePartNotFoundError,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_execute_result(scalar_value=None, scalars_list=None, scalar_count=None):
    """Create a mock result object that mimics SQLAlchemy's execute result.

    Args:
        scalar_value: Value to return from result.scalar_one_or_none()
        scalars_list: Value to return from result.scalars().all()
        scalar_count: Value to return from result.scalar()
    """
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    if scalar_count is not None:
        result.scalar = MagicMock(return_value=scalar_count)
    if scalars_list is not None:
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=scalars_list)
        result.scalars = MagicMock(return_value=mock_scalars)
    return result


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def inventory_service(mock_db):
    """Create an InventoryService with a mock database session."""
    return InventoryService(db=mock_db)


@pytest.fixture
def sample_category_id():
    """Return a sample category UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_spare_part_data(sample_category_id):
    """Return sample data for creating a spare part."""
    return SparePartCreate(
        part_number="SP-001",
        barcode="8901234567890",
        name="Brake Pad Set - Front",
        description="High-quality front brake pads",
        brand="Bosch",
        category_id=sample_category_id,
        subcategory_id=None,
        vehicle_compatibility=["Toyota Camry 2018-2023", "Honda Accord 2020-2023"],
        unit_of_measure="PCS",
        cost_price=Decimal("25.50"),
        selling_price=Decimal("45.00"),
        min_stock_level=Decimal("10"),
        max_stock_level=Decimal("100"),
        reorder_quantity=Decimal("50"),
    )


def _make_mock_spare_part(
    part_number="SP-001",
    barcode="8901234567890",
    name="Brake Pad Set",
    deleted_at=None,
):
    """Helper to create a mock SparePart object."""
    mock_part = MagicMock()
    mock_part.id = uuid.uuid4()
    mock_part.part_number = part_number
    mock_part.barcode = barcode
    mock_part.name = name
    mock_part.deleted_at = deleted_at
    mock_part.soft_delete = MagicMock()
    return mock_part


# =============================================================================
# Create Tests
# =============================================================================


class TestCreateSparePart:
    """Tests for InventoryService.create_spare_part."""

    @pytest.mark.asyncio
    async def test_create_spare_part_success(
        self, inventory_service, mock_db, sample_spare_part_data, sample_category_id
    ):
        """Test successful creation of a spare part."""
        # Mock queries in order:
        # 1. _validate_unique_part_number -> None (no duplicate)
        # 2. _validate_unique_barcode -> None (no duplicate)
        # 3. _validate_category_exists -> category_id (exists)
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=None),  # no dup part_number
                _make_execute_result(scalar_value=None),  # no dup barcode
                _make_execute_result(scalar_value=sample_category_id),  # category exists
            ]
        )

        await inventory_service.create_spare_part(
            data=sample_spare_part_data, created_by="user-123"
        )

        # Verify add was called
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_spare_part_duplicate_part_number(
        self, inventory_service, mock_db, sample_spare_part_data
    ):
        """Test that creating a spare part with duplicate part_number raises error."""
        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=uuid.uuid4())
        )

        with pytest.raises(DuplicatePartNumberError):
            await inventory_service.create_spare_part(data=sample_spare_part_data)

    @pytest.mark.asyncio
    async def test_create_spare_part_duplicate_barcode(
        self, inventory_service, mock_db, sample_spare_part_data
    ):
        """Test that creating a spare part with duplicate barcode raises error."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=None),  # no dup part_number
                _make_execute_result(scalar_value=uuid.uuid4()),  # dup barcode
            ]
        )

        with pytest.raises(DuplicateBarcodeError):
            await inventory_service.create_spare_part(data=sample_spare_part_data)

    @pytest.mark.asyncio
    async def test_create_spare_part_category_not_found(
        self, inventory_service, mock_db, sample_spare_part_data
    ):
        """Test that creating a spare part with invalid category raises error."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=None),  # no dup part_number
                _make_execute_result(scalar_value=None),  # no dup barcode
                _make_execute_result(scalar_value=None),  # category NOT found
            ]
        )

        with pytest.raises(CategoryNotFoundError):
            await inventory_service.create_spare_part(data=sample_spare_part_data)

    @pytest.mark.asyncio
    async def test_create_spare_part_without_barcode(
        self, inventory_service, mock_db, sample_category_id
    ):
        """Test creating spare part without barcode skips barcode uniqueness check."""
        data = SparePartCreate(
            part_number="SP-002",
            barcode=None,
            name="Oil Filter",
            category_id=sample_category_id,
            cost_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
        )

        # Only 2 calls: validate part_number + validate category (no barcode check)
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=None),  # no dup part_number
                _make_execute_result(scalar_value=sample_category_id),  # category exists
            ]
        )

        await inventory_service.create_spare_part(data=data)
        mock_db.add.assert_called_once()


# =============================================================================
# Read Tests
# =============================================================================


class TestGetSparePart:
    """Tests for InventoryService.get_spare_part."""

    @pytest.mark.asyncio
    async def test_get_spare_part_success(self, inventory_service, mock_db):
        """Test retrieving an existing spare part by ID."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=mock_part)
        )

        result = await inventory_service.get_spare_part(spare_part_id)
        assert result == mock_part

    @pytest.mark.asyncio
    async def test_get_spare_part_not_found(self, inventory_service, mock_db):
        """Test that getting a non-existent spare part raises error."""
        spare_part_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        with pytest.raises(SparePartNotFoundError):
            await inventory_service.get_spare_part(spare_part_id)


class TestListSpareParts:
    """Tests for InventoryService.list_spare_parts."""

    @pytest.mark.asyncio
    async def test_list_spare_parts_with_results(self, inventory_service, mock_db):
        """Test listing spare parts returns paginated results."""
        mock_parts = [_make_mock_spare_part(f"SP-{i:03d}") for i in range(3)]

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=3),  # count query
                _make_execute_result(scalars_list=mock_parts),  # list query
            ]
        )

        parts, total = await inventory_service.list_spare_parts(page=1, page_size=20)
        assert len(parts) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_list_spare_parts_empty(self, inventory_service, mock_db):
        """Test listing spare parts when no results exist."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=0),  # count query
                _make_execute_result(scalars_list=[]),  # list query
            ]
        )

        parts, total = await inventory_service.list_spare_parts(page=1, page_size=20)
        assert len(parts) == 0
        assert total == 0


# =============================================================================
# Update Tests
# =============================================================================


class TestUpdateSparePart:
    """Tests for InventoryService.update_spare_part."""

    @pytest.mark.asyncio
    async def test_update_spare_part_name_only(self, inventory_service, mock_db):
        """Test successful partial update of a spare part (name only, no uniqueness check needed)."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(part_number="SP-001")
        mock_part.id = spare_part_id

        # Only one execute call: get_spare_part
        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=mock_part)
        )

        update_data = SparePartUpdate(name="Updated Brake Pad Set")

        result = await inventory_service.update_spare_part(
            spare_part_id=spare_part_id,
            data=update_data,
            updated_by="user-456",
        )

        assert result == mock_part
        mock_db.flush.assert_awaited()
        mock_db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_spare_part_not_found(self, inventory_service, mock_db):
        """Test that updating a non-existent spare part raises error."""
        spare_part_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        update_data = SparePartUpdate(name="Updated Name")

        with pytest.raises(SparePartNotFoundError):
            await inventory_service.update_spare_part(
                spare_part_id=spare_part_id, data=update_data
            )

    @pytest.mark.asyncio
    async def test_update_spare_part_duplicate_part_number(
        self, inventory_service, mock_db
    ):
        """Test that changing part_number to an existing one raises error."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(part_number="SP-001")
        mock_part.id = spare_part_id

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=mock_part),  # get_spare_part
                _make_execute_result(scalar_value=uuid.uuid4()),  # dup part_number found
            ]
        )

        update_data = SparePartUpdate(part_number="SP-EXISTING")

        with pytest.raises(DuplicatePartNumberError):
            await inventory_service.update_spare_part(
                spare_part_id=spare_part_id, data=update_data
            )


# =============================================================================
# Delete Tests
# =============================================================================


class TestDeleteSparePart:
    """Tests for InventoryService.delete_spare_part."""

    @pytest.mark.asyncio
    async def test_delete_spare_part_success(self, inventory_service, mock_db):
        """Test successful soft-delete of a spare part."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=mock_part)
        )

        result = await inventory_service.delete_spare_part(
            spare_part_id=spare_part_id, deleted_by="user-789"
        )

        mock_part.soft_delete.assert_called_once_with(deleted_by="user-789")
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_spare_part_not_found(self, inventory_service, mock_db):
        """Test that deleting a non-existent spare part raises error."""
        spare_part_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        with pytest.raises(SparePartNotFoundError):
            await inventory_service.delete_spare_part(spare_part_id=spare_part_id)


# =============================================================================
# Search Tests
# =============================================================================


class TestSearchSpareParts:
    """Tests for InventoryService.search_spare_parts."""

    @pytest.mark.asyncio
    async def test_search_with_general_query(self, inventory_service, mock_db):
        """Test search with a general query term."""
        mock_parts = [_make_mock_spare_part("SP-001", name="Brake Pad")]

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=1),  # count
                _make_execute_result(scalars_list=mock_parts),  # results
            ]
        )

        parts, total = await inventory_service.search_spare_parts(q="Brake")
        assert total == 1
        assert len(parts) == 1

    @pytest.mark.asyncio
    async def test_search_by_barcode(self, inventory_service, mock_db):
        """Test search by exact barcode match."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=1),
                _make_execute_result(scalars_list=[_make_mock_spare_part()]),
            ]
        )

        parts, total = await inventory_service.search_spare_parts(
            barcode="8901234567890"
        )
        assert total == 1

    @pytest.mark.asyncio
    async def test_search_by_category_id(self, inventory_service, mock_db):
        """Test search by category ID."""
        cat_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=2),
                _make_execute_result(
                    scalars_list=[
                        _make_mock_spare_part("SP-001"),
                        _make_mock_spare_part("SP-002"),
                    ]
                ),
            ]
        )

        parts, total = await inventory_service.search_spare_parts(category_id=cat_id)
        assert total == 2
        assert len(parts) == 2

    @pytest.mark.asyncio
    async def test_search_no_results(self, inventory_service, mock_db):
        """Test search returning no results."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=0),
                _make_execute_result(scalars_list=[]),
            ]
        )

        parts, total = await inventory_service.search_spare_parts(q="nonexistent")
        assert total == 0
        assert len(parts) == 0

    @pytest.mark.asyncio
    async def test_search_by_vehicle_compatibility(self, inventory_service, mock_db):
        """Test search by vehicle compatibility text."""
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_count=1),
                _make_execute_result(scalars_list=[_make_mock_spare_part()]),
            ]
        )

        parts, total = await inventory_service.search_spare_parts(
            vehicle_compatibility="Toyota Camry"
        )
        assert total == 1


# =============================================================================
# Schema Tests
# =============================================================================


class TestSparePartSchemas:
    """Tests for Pydantic schema validation."""

    def test_create_schema_valid(self):
        """Test valid create schema passes validation."""
        data = SparePartCreate(
            part_number="SP-001",
            name="Brake Pad",
            category_id=uuid.uuid4(),
            cost_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
        )
        assert data.part_number == "SP-001"
        assert data.unit_of_measure == "PCS"
        assert data.min_stock_level == Decimal("0")

    def test_create_schema_requires_part_number(self):
        """Test that part_number is required."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SparePartCreate(
                name="Brake Pad",
                category_id=uuid.uuid4(),
                cost_price=Decimal("10.00"),
                selling_price=Decimal("20.00"),
            )

    def test_create_schema_requires_name(self):
        """Test that name is required."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SparePartCreate(
                part_number="SP-001",
                category_id=uuid.uuid4(),
                cost_price=Decimal("10.00"),
                selling_price=Decimal("20.00"),
            )

    def test_create_schema_rejects_negative_price(self):
        """Test that negative prices are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SparePartCreate(
                part_number="SP-001",
                name="Brake Pad",
                category_id=uuid.uuid4(),
                cost_price=Decimal("-1.00"),
                selling_price=Decimal("20.00"),
            )

    def test_update_schema_all_optional(self):
        """Test that all fields in update schema are optional."""
        data = SparePartUpdate()
        assert data.part_number is None
        assert data.name is None
        assert data.cost_price is None

    def test_update_schema_partial(self):
        """Test partial update schema with only some fields."""
        data = SparePartUpdate(name="Updated Name", cost_price=Decimal("30.00"))
        assert data.name == "Updated Name"
        assert data.cost_price == Decimal("30.00")
        assert data.part_number is None
