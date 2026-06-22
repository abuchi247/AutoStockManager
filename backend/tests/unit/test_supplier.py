"""Unit tests for the Supplier model, service, and router.

Tests cover:
- Supplier model creation and field validation
- SupplierService CRUD operations
- SupplierService balance and aging calculations
- Supplier router endpoints
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.supplier import Supplier, SupplierAccountStatus
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierListResponse,
    SupplierBalanceResponse,
)
from app.services.supplier_service import (
    SupplierService,
    SupplierNotFoundError,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestSupplierModel:
    """Tests for the Supplier SQLAlchemy model."""

    def test_supplier_creation_with_required_fields(self):
        """Supplier can be created with only the required name field."""
        supplier = Supplier(name="AutoParts Global Ltd")
        assert supplier.name == "AutoParts Global Ltd"
        # Note: column default is applied by the database on INSERT,
        # so we test explicit instantiation with account_status
        supplier_with_status = Supplier(
            name="AutoParts Global Ltd",
            account_status=SupplierAccountStatus.ACTIVE.value,
        )
        assert supplier_with_status.account_status == SupplierAccountStatus.ACTIVE.value

    def test_supplier_creation_with_all_fields(self):
        """Supplier can be created with all fields populated."""
        supplier = Supplier(
            name="AutoParts Global Ltd",
            contact_person="John Doe",
            phone="+234 801 234 5678",
            email="sales@autopartsglobal.com",
            address="456 Industrial Avenue, Lagos",
            tax_id="TIN-87654321",
            payment_terms="Net 30",
            account_status=SupplierAccountStatus.ACTIVE.value,
        )
        assert supplier.name == "AutoParts Global Ltd"
        assert supplier.contact_person == "John Doe"
        assert supplier.phone == "+234 801 234 5678"
        assert supplier.email == "sales@autopartsglobal.com"
        assert supplier.address == "456 Industrial Avenue, Lagos"
        assert supplier.tax_id == "TIN-87654321"
        assert supplier.payment_terms == "Net 30"
        assert supplier.account_status == SupplierAccountStatus.ACTIVE.value

    def test_supplier_nullable_fields_default_to_none(self):
        """Optional fields default to None when not provided."""
        supplier = Supplier(name="Test Supplier")
        assert supplier.contact_person is None
        assert supplier.phone is None
        assert supplier.email is None
        assert supplier.address is None
        assert supplier.tax_id is None
        assert supplier.payment_terms is None

    def test_supplier_account_status_enum_values(self):
        """SupplierAccountStatus enum has the expected values."""
        assert SupplierAccountStatus.ACTIVE.value == "active"
        assert SupplierAccountStatus.SUSPENDED.value == "suspended"
        assert SupplierAccountStatus.CLOSED.value == "closed"

    def test_supplier_tablename(self):
        """Supplier model uses the correct table name."""
        assert Supplier.__tablename__ == "suppliers"

    def test_supplier_repr(self):
        """Supplier __repr__ contains key attributes."""
        supplier = Supplier(name="Test Supplier")
        supplier.id = uuid4()
        repr_str = repr(supplier)
        assert "Test Supplier" in repr_str
        assert "Supplier" in repr_str


# =============================================================================
# Schema Tests
# =============================================================================


class TestSupplierSchemas:
    """Tests for Pydantic supplier schemas."""

    def test_supplier_create_minimal(self):
        """SupplierCreate with only required name field."""
        schema = SupplierCreate(name="Test Supplier")
        assert schema.name == "Test Supplier"
        assert schema.account_status == "active"
        assert schema.contact_person is None
        assert schema.phone is None
        assert schema.email is None
        assert schema.address is None
        assert schema.tax_id is None
        assert schema.payment_terms is None

    def test_supplier_create_all_fields(self):
        """SupplierCreate with all fields populated."""
        schema = SupplierCreate(
            name="AutoParts Global Ltd",
            contact_person="John Doe",
            phone="+234 801 234 5678",
            email="sales@autopartsglobal.com",
            address="456 Industrial Avenue, Lagos",
            tax_id="TIN-87654321",
            payment_terms="Net 30",
            account_status="active",
        )
        assert schema.name == "AutoParts Global Ltd"
        assert schema.contact_person == "John Doe"
        assert schema.payment_terms == "Net 30"

    def test_supplier_create_invalid_account_status(self):
        """SupplierCreate rejects invalid account status."""
        with pytest.raises(Exception):
            SupplierCreate(name="Test", account_status="invalid")

    def test_supplier_create_valid_statuses(self):
        """SupplierCreate accepts all valid account statuses."""
        for status in ["active", "suspended", "closed"]:
            schema = SupplierCreate(name="Test", account_status=status)
            assert schema.account_status == status

    def test_supplier_update_partial(self):
        """SupplierUpdate can include partial fields."""
        schema = SupplierUpdate(name="New Name")
        assert schema.name == "New Name"
        assert schema.phone is None
        assert schema.account_status is None

    def test_supplier_update_account_status_validation(self):
        """SupplierUpdate rejects invalid account status."""
        with pytest.raises(Exception):
            SupplierUpdate(account_status="bogus")

    def test_supplier_response_from_attributes(self):
        """SupplierResponse can be created from ORM attributes."""
        supplier_id = uuid4()
        response = SupplierResponse(
            id=supplier_id,
            name="Test Supplier",
            contact_person="John",
            phone="+234 801 234 5678",
            email="test@test.com",
            address="123 Street",
            tax_id="TIN-123",
            payment_terms="Net 30",
            account_status="active",
            created_at=None,
            updated_at=None,
            created_by=None,
            updated_by=None,
        )
        assert response.id == supplier_id
        assert response.name == "Test Supplier"
        assert response.payment_terms == "Net 30"

    def test_supplier_balance_response(self):
        """SupplierBalanceResponse schema validation."""
        supplier_id = uuid4()
        response = SupplierBalanceResponse(
            supplier_id=supplier_id,
            supplier_name="Test Supplier",
            total_balance=Decimal("5000.00"),
            aging={
                "current": "1000.00",
                "days_1_30": "2000.00",
                "days_31_60": "1000.00",
                "days_61_90": "500.00",
                "days_over_90": "500.00",
            },
        )
        assert response.total_balance == Decimal("5000.00")
        assert response.supplier_name == "Test Supplier"


# =============================================================================
# Service Tests
# =============================================================================


class TestSupplierService:
    """Tests for SupplierService business logic."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock async database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create a SupplierService with a mock db session."""
        return SupplierService(db=mock_db)

    @pytest.mark.asyncio
    async def test_create_supplier(self, service, mock_db):
        """create_supplier adds supplier to db and flushes."""
        data = SupplierCreate(
            name="New Supplier",
            contact_person="Jane",
            phone="+123",
            email="jane@test.com",
            payment_terms="Net 60",
        )

        async def mock_refresh(obj):
            obj.id = uuid4()

        mock_db.refresh = mock_refresh

        result = await service.create_supplier(data=data, created_by="user-1")

        mock_db.add.assert_called_once()
        assert result.name == "New Supplier"
        assert result.contact_person == "Jane"
        assert result.payment_terms == "Net 60"
        assert result.created_by == "user-1"

    @pytest.mark.asyncio
    async def test_get_supplier_not_found(self, service, mock_db):
        """get_supplier raises SupplierNotFoundError for missing supplier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(SupplierNotFoundError):
            await service.get_supplier(uuid4())

    @pytest.mark.asyncio
    async def test_get_supplier_found(self, service, mock_db):
        """get_supplier returns existing supplier."""
        supplier_id = uuid4()
        mock_supplier = Supplier(name="Found Supplier")
        mock_supplier.id = supplier_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_supplier
        mock_db.execute.return_value = mock_result

        result = await service.get_supplier(supplier_id)
        assert result.name == "Found Supplier"

    @pytest.mark.asyncio
    async def test_list_suppliers(self, service, mock_db):
        """list_suppliers returns paginated results with total count."""
        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock list query
        supplier1 = Supplier(name="Supplier A")
        supplier2 = Supplier(name="Supplier B")
        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [supplier1, supplier2]
        mock_list_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_list_result]

        suppliers, total = await service.list_suppliers(page=1, page_size=20)
        assert total == 2
        assert len(suppliers) == 2
        assert suppliers[0].name == "Supplier A"

    @pytest.mark.asyncio
    async def test_update_supplier(self, service, mock_db):
        """update_supplier applies partial updates."""
        supplier_id = uuid4()
        existing_supplier = Supplier(
            name="Old Name",
            phone="+123",
            account_status="active",
        )
        existing_supplier.id = supplier_id

        # Mock get_supplier
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_supplier
        mock_db.execute.return_value = mock_result

        data = SupplierUpdate(name="New Name", payment_terms="Net 45")
        result = await service.update_supplier(
            supplier_id=supplier_id, data=data, updated_by="user-2"
        )

        assert result.name == "New Name"
        assert result.payment_terms == "Net 45"
        assert result.updated_by == "user-2"

    @pytest.mark.asyncio
    async def test_delete_supplier(self, service, mock_db):
        """delete_supplier performs soft delete."""
        supplier_id = uuid4()
        existing_supplier = Supplier(name="To Delete")
        existing_supplier.id = supplier_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_supplier
        mock_db.execute.return_value = mock_result

        result = await service.delete_supplier(
            supplier_id=supplier_id, deleted_by="admin-1"
        )

        assert result.deleted_at is not None
        assert result.deleted_by == "admin-1"

    @pytest.mark.asyncio
    async def test_calculate_balance(self, service, mock_db):
        """calculate_balance returns Decimal zero (placeholder)."""
        supplier_id = uuid4()
        existing_supplier = Supplier(name="Balance Test")
        existing_supplier.id = supplier_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_supplier
        mock_db.execute.return_value = mock_result

        balance = await service.calculate_balance(supplier_id)
        assert balance == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_calculate_aging(self, service, mock_db):
        """calculate_aging returns aging buckets (placeholder)."""
        supplier_id = uuid4()
        existing_supplier = Supplier(name="Aging Test")
        existing_supplier.id = supplier_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_supplier
        mock_db.execute.return_value = mock_result

        aging = await service.calculate_aging(supplier_id)
        assert "current" in aging
        assert "days_1_30" in aging
        assert "days_31_60" in aging
        assert "days_61_90" in aging
        assert "days_over_90" in aging
        assert "total" in aging
        assert aging["total"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_calculate_balance_not_found(self, service, mock_db):
        """calculate_balance raises error for non-existent supplier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(SupplierNotFoundError):
            await service.calculate_balance(uuid4())
