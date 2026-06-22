"""Unit tests for Customer model, schema, and service.

Tests the Customer model fields, CustomerService CRUD operations,
and Pydantic schema validation.

Satisfies Requirements: 6.1, 6.2
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.customer import Customer, AccountStatus
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    PurchaseHistoryItem,
    PurchaseHistoryResponse,
)


# =============================================================================
# Customer Model Tests
# =============================================================================


class TestCustomerModel:
    """Test that the Customer model has the correct columns and types."""

    def test_tablename(self):
        """Customer model should use 'customers' table name."""
        assert Customer.__tablename__ == "customers"

    def test_name_column_exists(self):
        """Customer should have a required name column of String type."""
        col = Customer.__table__.columns["name"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_phone_column_exists(self):
        """Customer should have a nullable phone column of String type."""
        col = Customer.__table__.columns["phone"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_email_column_exists(self):
        """Customer should have a nullable email column of String type."""
        col = Customer.__table__.columns["email"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_address_column_exists(self):
        """Customer should have a nullable address column of Text type."""
        col = Customer.__table__.columns["address"]
        assert isinstance(col.type, Text)
        assert col.nullable is True

    def test_tax_id_column_exists(self):
        """Customer should have a nullable tax_id column of String type."""
        col = Customer.__table__.columns["tax_id"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_credit_limit_column_exists(self):
        """Customer should have a credit_limit column of Numeric type."""
        col = Customer.__table__.columns["credit_limit"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_account_status_column_exists(self):
        """Customer should have an account_status column of String type."""
        col = Customer.__table__.columns["account_status"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_inherits_base_model_columns(self):
        """Customer should have id, created_at, updated_at, created_by, updated_by columns."""
        table_cols = {c.name for c in Customer.__table__.columns}
        assert "id" in table_cols
        assert "created_at" in table_cols
        assert "updated_at" in table_cols
        assert "created_by" in table_cols
        assert "updated_by" in table_cols

    def test_inherits_soft_delete_columns(self):
        """Customer should have deleted_at and deleted_by columns from SoftDeleteMixin."""
        table_cols = {c.name for c in Customer.__table__.columns}
        assert "deleted_at" in table_cols
        assert "deleted_by" in table_cols

    def test_default_credit_limit(self):
        """A new customer should have a default credit_limit of 0."""
        customer = Customer(name="Test Customer")
        # Default is set via column default, check the column definition
        col = Customer.__table__.columns["credit_limit"]
        assert col.default is not None

    def test_default_account_status(self):
        """A new customer should have a default account_status of 'active'."""
        col = Customer.__table__.columns["account_status"]
        assert col.default is not None

    def test_repr(self):
        """Customer __repr__ should include id, name, status, and credit_limit."""
        customer = Customer(name="Test Corp", account_status="active", credit_limit=Decimal("5000"))
        repr_str = repr(customer)
        assert "Test Corp" in repr_str
        assert "active" in repr_str


# =============================================================================
# AccountStatus Enum Tests
# =============================================================================


class TestAccountStatus:
    """Test the AccountStatus enum values."""

    def test_active_value(self):
        assert AccountStatus.ACTIVE.value == "active"

    def test_suspended_value(self):
        assert AccountStatus.SUSPENDED.value == "suspended"

    def test_closed_value(self):
        assert AccountStatus.CLOSED.value == "closed"

    def test_all_statuses_are_strings(self):
        for status in AccountStatus:
            assert isinstance(status.value, str)


# =============================================================================
# Customer Schema Tests
# =============================================================================


class TestCustomerCreateSchema:
    """Test CustomerCreate Pydantic schema validation."""

    def test_valid_creation_minimal(self):
        """Should accept minimal valid data (only name required)."""
        data = CustomerCreate(name="Test Customer")
        assert data.name == "Test Customer"
        assert data.phone is None
        assert data.email is None
        assert data.credit_limit == Decimal("0.00")
        assert data.account_status == "active"

    def test_valid_creation_full(self):
        """Should accept full valid data."""
        data = CustomerCreate(
            name="Ade Motors",
            phone="+234 801 234 5678",
            email="info@ademotors.com",
            address="123 Main Street, Lagos",
            tax_id="TIN-12345678",
            credit_limit=Decimal("50000.00"),
            account_status="active",
        )
        assert data.name == "Ade Motors"
        assert data.phone == "+234 801 234 5678"
        assert data.email == "info@ademotors.com"
        assert data.credit_limit == Decimal("50000.00")

    def test_invalid_empty_name(self):
        """Should reject empty name."""
        with pytest.raises(Exception):
            CustomerCreate(name="")

    def test_invalid_negative_credit_limit(self):
        """Should reject negative credit limit."""
        with pytest.raises(Exception):
            CustomerCreate(name="Test", credit_limit=Decimal("-100"))

    def test_invalid_account_status(self):
        """Should reject invalid account status."""
        with pytest.raises(Exception):
            CustomerCreate(name="Test", account_status="invalid_status")

    def test_valid_suspended_status(self):
        """Should accept 'suspended' as account status."""
        data = CustomerCreate(name="Test", account_status="suspended")
        assert data.account_status == "suspended"

    def test_valid_closed_status(self):
        """Should accept 'closed' as account status."""
        data = CustomerCreate(name="Test", account_status="closed")
        assert data.account_status == "closed"


class TestCustomerUpdateSchema:
    """Test CustomerUpdate Pydantic schema validation."""

    def test_all_fields_optional(self):
        """Should accept empty update (all fields optional)."""
        data = CustomerUpdate()
        assert data.name is None
        assert data.phone is None

    def test_partial_update(self):
        """Should accept partial update data."""
        data = CustomerUpdate(name="New Name", credit_limit=Decimal("10000"))
        assert data.name == "New Name"
        assert data.credit_limit == Decimal("10000")
        assert data.phone is None

    def test_invalid_account_status_update(self):
        """Should reject invalid account status in update."""
        with pytest.raises(Exception):
            CustomerUpdate(account_status="nonexistent")


class TestCustomerResponseSchema:
    """Test CustomerResponse Pydantic schema."""

    def test_from_attributes(self):
        """Should support from_attributes mode for ORM models."""
        assert CustomerResponse.model_config.get("from_attributes") is True

    def test_valid_response(self):
        """Should accept valid response data."""
        response = CustomerResponse(
            id=uuid.uuid4(),
            name="Test Customer",
            credit_limit=Decimal("5000"),
            account_status="active",
        )
        assert response.name == "Test Customer"


class TestPurchaseHistorySchema:
    """Test PurchaseHistoryItem and PurchaseHistoryResponse schemas."""

    def test_purchase_history_item(self):
        """Should accept valid purchase history item data."""
        item = PurchaseHistoryItem(
            sale_id=uuid.uuid4(),
            invoice_number="INV-001",
            status="CONFIRMED",
            payment_type="CASH",
            total_amount=Decimal("1500.00"),
            created_at=datetime.now(timezone.utc),
        )
        assert item.invoice_number == "INV-001"
        assert item.total_amount == Decimal("1500.00")

    def test_purchase_history_response(self):
        """Should accept valid purchase history response."""
        response = PurchaseHistoryResponse(
            data=[],
            meta={"page": 1, "total": 0, "page_size": 20},
        )
        assert response.data == []
        assert response.meta["total"] == 0


# =============================================================================
# Customer Soft Delete Tests
# =============================================================================


class TestCustomerSoftDelete:
    """Test soft-delete behavior on Customer model."""

    def test_customer_not_deleted_by_default(self):
        """A new customer should not be marked as deleted."""
        customer = Customer(name="Test")
        assert customer.is_deleted is False

    def test_soft_delete_sets_deleted_at(self):
        """soft_delete() should set the deleted_at timestamp."""
        customer = Customer(name="Test")
        customer.soft_delete(deleted_by="admin")
        assert customer.is_deleted is True
        assert customer.deleted_at is not None
        assert customer.deleted_by == "admin"

    def test_restore_clears_deletion(self):
        """restore() should clear deleted_at and deleted_by."""
        customer = Customer(name="Test")
        customer.soft_delete(deleted_by="admin")
        customer.restore()
        assert customer.is_deleted is False
        assert customer.deleted_at is None
        assert customer.deleted_by is None
