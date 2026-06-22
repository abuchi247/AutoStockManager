"""Unit tests for the StockStatusCache model, stock service, and stock router.

Tests cover:
- Model structure (columns, constraints)
- Instance creation
- Composite unique index definition (Requirement 18.8)
- StockService logic
- Stock router endpoint structure
- Pydantic schema validation
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.stock_status_cache import StockStatusCache
from app.services.stock_service import LocationNotFoundError, StockService


# =============================================================================
# Model Structure Tests
# =============================================================================


class TestStockStatusCacheModel:
    """Tests for StockStatusCache model column definitions and constraints."""

    def test_tablename(self):
        """Verify the table name is 'stock_status_cache'."""
        assert StockStatusCache.__tablename__ == "stock_status_cache"

    def test_spare_part_id_column(self):
        """Verify spare_part_id column is defined as non-nullable UUID."""
        col = StockStatusCache.__table__.columns["spare_part_id"]
        assert not col.nullable

    def test_location_id_column(self):
        """Verify location_id column is defined as non-nullable UUID."""
        col = StockStatusCache.__table__.columns["location_id"]
        assert not col.nullable

    def test_current_quantity_column(self):
        """Verify current_quantity column is non-nullable Numeric."""
        col = StockStatusCache.__table__.columns["current_quantity"]
        assert not col.nullable

    def test_last_reconciled_at_column(self):
        """Verify last_reconciled_at is nullable DateTime."""
        col = StockStatusCache.__table__.columns["last_reconciled_at"]
        assert col.nullable

    def test_updated_at_column(self):
        """Verify updated_at column exists and is non-nullable."""
        col = StockStatusCache.__table__.columns["updated_at"]
        assert not col.nullable

    def test_id_column_is_primary_key(self):
        """Verify the id column is a UUID primary key."""
        col = StockStatusCache.__table__.columns["id"]
        assert col.primary_key

    def test_composite_unique_index_exists(self):
        """Verify composite unique index on (spare_part_id, location_id).

        Satisfies Requirement 18.8: THE ERP_System SHALL maintain a composite
        unique index on the Stock_Status_Cache table for spare_part_id and
        location_id columns.
        """
        table = StockStatusCache.__table__
        # Check indexes for the unique composite index
        found = False
        for index in table.indexes:
            col_names = {col.name for col in index.columns}
            if col_names == {"spare_part_id", "location_id"} and index.unique:
                found = True
                break
        assert found, "Composite unique index on (spare_part_id, location_id) not found"

    def test_composite_unique_index_named_correctly(self):
        """Verify the composite unique index has the expected name."""
        table = StockStatusCache.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "uix_stock_status_cache_part_location" in index_names


# =============================================================================
# Instance Tests
# =============================================================================


class TestStockStatusCacheInstance:
    """Tests for StockStatusCache instance creation."""

    def test_instance_creation(self):
        """Verify instance can be created with required fields."""
        part_id = uuid.uuid4()
        loc_id = uuid.uuid4()
        cache_entry = StockStatusCache(
            spare_part_id=part_id,
            location_id=loc_id,
            current_quantity=Decimal("100.0000"),
        )
        assert cache_entry.spare_part_id == part_id
        assert cache_entry.location_id == loc_id
        assert cache_entry.current_quantity == Decimal("100.0000")
        assert cache_entry.last_reconciled_at is None

    def test_instance_with_last_reconciled(self):
        """Verify instance creation with last_reconciled_at set."""
        now = datetime.now(timezone.utc)
        cache_entry = StockStatusCache(
            spare_part_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            current_quantity=Decimal("50.5000"),
            last_reconciled_at=now,
        )
        assert cache_entry.last_reconciled_at == now

    def test_default_current_quantity_is_zero(self):
        """Verify default current_quantity column default is Decimal('0').
        
        Note: Column defaults are applied by the database on insert,
        not at Python instantiation time without a session.
        """
        col = StockStatusCache.__table__.columns["current_quantity"]
        # The column has a default defined
        assert col.default is not None
        assert col.default.arg == Decimal("0")


# =============================================================================
# Service Tests
# =============================================================================


class TestStockService:
    """Tests for StockService custom exceptions."""

    def test_location_not_found_error(self):
        """Verify LocationNotFoundError stores location_id and message."""
        loc_id = uuid.uuid4()
        error = LocationNotFoundError(location_id=loc_id)
        assert error.location_id == loc_id
        assert str(loc_id) in error.message

    def test_location_not_found_error_is_exception(self):
        """Verify LocationNotFoundError is an Exception subclass."""
        loc_id = uuid.uuid4()
        error = LocationNotFoundError(location_id=loc_id)
        assert isinstance(error, Exception)


# =============================================================================
# Router Tests
# =============================================================================


class TestStockRouter:
    """Tests for stock router endpoint registration."""

    def test_router_prefix(self):
        """Verify the router uses /api/v1/stock prefix."""
        from app.routers.stock import router
        assert router.prefix == "/api/v1/stock"

    def test_router_tags(self):
        """Verify the router uses 'Stock' tag."""
        from app.routers.stock import router
        assert "Stock" in router.tags

    def test_get_stock_at_location_route_exists(self):
        """Verify GET /locations/{location_id} route is registered on the app."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert "/api/v1/stock/locations/{location_id}" in routes


# =============================================================================
# Schema Tests
# =============================================================================


class TestStockSchemas:
    """Tests for stock Pydantic schemas."""

    def test_stock_item_response_fields(self):
        """Verify StockItemResponse has expected fields."""
        from app.schemas.stock import StockItemResponse
        fields = StockItemResponse.model_fields
        assert "id" in fields
        assert "spare_part_id" in fields
        assert "location_id" in fields
        assert "current_quantity" in fields
        assert "last_reconciled_at" in fields
        assert "spare_part_name" in fields
        assert "spare_part_number" in fields

    def test_stock_location_response_fields(self):
        """Verify StockLocationResponse has expected fields."""
        from app.schemas.stock import StockLocationResponse
        fields = StockLocationResponse.model_fields
        assert "location_id" in fields
        assert "location_name" in fields
        assert "data" in fields
        assert "meta" in fields

    def test_stock_item_response_from_dict(self):
        """Verify StockItemResponse can be constructed from a dict."""
        from app.schemas.stock import StockItemResponse
        item_id = uuid.uuid4()
        part_id = uuid.uuid4()
        loc_id = uuid.uuid4()
        resp = StockItemResponse(
            id=item_id,
            spare_part_id=part_id,
            location_id=loc_id,
            current_quantity=42.5,
            last_reconciled_at=None,
            spare_part_name="Brake Pad",
            spare_part_number="BP-001",
        )
        assert resp.id == item_id
        assert resp.current_quantity == 42.5
        assert resp.spare_part_name == "Brake Pad"

    def test_stock_location_response_construction(self):
        """Verify StockLocationResponse can be constructed."""
        from app.schemas.stock import StockLocationResponse
        loc_id = uuid.uuid4()
        resp = StockLocationResponse(
            location_id=loc_id,
            location_name="Main Warehouse",
            data=[],
            meta={"page": 1, "total": 0},
        )
        assert resp.location_id == loc_id
        assert resp.location_name == "Main Warehouse"
        assert resp.data == []
