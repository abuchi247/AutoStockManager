"""Unit tests for PurchaseOrder and PurchaseOrderItem models."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from sqlalchemy import Numeric, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)


# =============================================================================
# PurchaseOrderStatus Enum Tests
# =============================================================================


class TestPurchaseOrderStatus:
    """Test that PurchaseOrderStatus enum supports all required states (Req 9.1)."""

    def test_draft_status_exists(self):
        """DRAFT status should be available."""
        assert PurchaseOrderStatus.DRAFT == "DRAFT"

    def test_approved_status_exists(self):
        """APPROVED status should be available."""
        assert PurchaseOrderStatus.APPROVED == "APPROVED"

    def test_ordered_status_exists(self):
        """ORDERED status should be available."""
        assert PurchaseOrderStatus.ORDERED == "ORDERED"

    def test_partially_received_status_exists(self):
        """PARTIALLY_RECEIVED status should be available."""
        assert PurchaseOrderStatus.PARTIALLY_RECEIVED == "PARTIALLY_RECEIVED"

    def test_received_status_exists(self):
        """RECEIVED status should be available."""
        assert PurchaseOrderStatus.RECEIVED == "RECEIVED"

    def test_cancelled_status_exists(self):
        """CANCELLED status should be available."""
        assert PurchaseOrderStatus.CANCELLED == "CANCELLED"

    def test_all_statuses_count(self):
        """There should be exactly 6 PO statuses."""
        assert len(PurchaseOrderStatus) == 6

    def test_status_is_string_enum(self):
        """PurchaseOrderStatus should inherit from str."""
        assert isinstance(PurchaseOrderStatus.DRAFT, str)


# =============================================================================
# PurchaseOrder Model Tests
# =============================================================================


class TestPurchaseOrderModel:
    """Test PurchaseOrder model structure and columns."""

    def test_tablename(self):
        """PurchaseOrder should map to 'purchase_orders' table."""
        assert PurchaseOrder.__tablename__ == "purchase_orders"

    def test_inherits_base_model_columns(self):
        """PurchaseOrder should have all BaseModel audit columns."""
        table = PurchaseOrder.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns
        assert "created_by" in table.columns
        assert "updated_by" in table.columns

    def test_supplier_id_column(self):
        """PurchaseOrder should have a supplier_id UUID FK column."""
        col = PurchaseOrder.__table__.columns["supplier_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        # Check FK reference
        fk = list(col.foreign_keys)
        assert len(fk) == 1
        assert fk[0].target_fullname == "suppliers.id"

    def test_status_column(self):
        """PurchaseOrder should have a status enum column."""
        col = PurchaseOrder.__table__.columns["status"]
        assert col.nullable is False

    def test_status_default_is_draft(self):
        """PurchaseOrder status column should default to DRAFT (Req 9.2)."""
        col = PurchaseOrder.__table__.columns["status"]
        assert col.default.arg == PurchaseOrderStatus.DRAFT

    def test_total_amount_column(self):
        """PurchaseOrder should have a total_amount Numeric column."""
        col = PurchaseOrder.__table__.columns["total_amount"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 14
        assert col.type.scale == 2
        assert col.nullable is False

    def test_total_amount_default(self):
        """PurchaseOrder total_amount column should default to 0.00."""
        col = PurchaseOrder.__table__.columns["total_amount"]
        assert col.default.arg == Decimal("0.00")

    def test_notes_column(self):
        """PurchaseOrder should have a nullable Text notes column."""
        col = PurchaseOrder.__table__.columns["notes"]
        assert isinstance(col.type, Text)
        assert col.nullable is True

    def test_approved_by_column(self):
        """PurchaseOrder should have a nullable approved_by UUID FK column."""
        col = PurchaseOrder.__table__.columns["approved_by"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is True
        fk = list(col.foreign_keys)
        assert len(fk) == 1
        assert fk[0].target_fullname == "users.id"

    def test_approved_at_column(self):
        """PurchaseOrder should have a nullable approved_at DateTime column."""
        col = PurchaseOrder.__table__.columns["approved_at"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.nullable is True

    def test_new_instance_defaults(self):
        """A new PurchaseOrder should have correct nullable defaults."""
        po = PurchaseOrder()
        # Column defaults are applied at flush/insert time by SQLAlchemy
        # Verify nullable fields are None before flush
        assert po.notes is None
        assert po.approved_by is None
        assert po.approved_at is None
        # Verify column defaults exist for non-nullable fields
        col_status = PurchaseOrder.__table__.columns["status"]
        assert col_status.default.arg == PurchaseOrderStatus.DRAFT
        col_total = PurchaseOrder.__table__.columns["total_amount"]
        assert col_total.default.arg == Decimal("0.00")

    def test_repr(self):
        """PurchaseOrder __repr__ should include key fields."""
        po = PurchaseOrder()
        po.supplier_id = uuid.uuid4()
        repr_str = repr(po)
        assert "PurchaseOrder" in repr_str
        assert "status" in repr_str


# =============================================================================
# PurchaseOrderItem Model Tests
# =============================================================================


class TestPurchaseOrderItemModel:
    """Test PurchaseOrderItem model structure and columns."""

    def test_tablename(self):
        """PurchaseOrderItem should map to 'purchase_order_items' table."""
        assert PurchaseOrderItem.__tablename__ == "purchase_order_items"

    def test_inherits_base_model_columns(self):
        """PurchaseOrderItem should have all BaseModel audit columns."""
        table = PurchaseOrderItem.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns
        assert "created_by" in table.columns
        assert "updated_by" in table.columns

    def test_purchase_order_id_column(self):
        """PurchaseOrderItem should have a purchase_order_id UUID FK column."""
        col = PurchaseOrderItem.__table__.columns["purchase_order_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)
        assert len(fk) == 1
        assert fk[0].target_fullname == "purchase_orders.id"

    def test_spare_part_id_column(self):
        """PurchaseOrderItem should have a spare_part_id UUID FK column."""
        col = PurchaseOrderItem.__table__.columns["spare_part_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)
        assert len(fk) == 1
        assert fk[0].target_fullname == "spare_parts.id"

    def test_quantity_ordered_column(self):
        """PurchaseOrderItem should have a quantity_ordered Numeric column."""
        col = PurchaseOrderItem.__table__.columns["quantity_ordered"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 12
        assert col.type.scale == 2
        assert col.nullable is False

    def test_quantity_received_column(self):
        """PurchaseOrderItem should have a quantity_received Numeric column."""
        col = PurchaseOrderItem.__table__.columns["quantity_received"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 12
        assert col.type.scale == 2
        assert col.nullable is False

    def test_quantity_received_default(self):
        """PurchaseOrderItem quantity_received column should default to 0."""
        col = PurchaseOrderItem.__table__.columns["quantity_received"]
        assert col.default.arg == Decimal("0.00")

    def test_unit_cost_column(self):
        """PurchaseOrderItem should have a unit_cost Numeric column."""
        col = PurchaseOrderItem.__table__.columns["unit_cost"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 12
        assert col.type.scale == 2
        assert col.nullable is False

    def test_line_total_property(self):
        """PurchaseOrderItem.line_total should return quantity_ordered * unit_cost."""
        item = PurchaseOrderItem()
        item.quantity_ordered = Decimal("10.00")
        item.unit_cost = Decimal("25.50")
        assert item.line_total == Decimal("255.00")

    def test_is_fully_received_false(self):
        """is_fully_received should be False when qty_received < qty_ordered."""
        item = PurchaseOrderItem()
        item.quantity_ordered = Decimal("10.00")
        item.quantity_received = Decimal("5.00")
        assert item.is_fully_received is False

    def test_is_fully_received_true(self):
        """is_fully_received should be True when qty_received >= qty_ordered."""
        item = PurchaseOrderItem()
        item.quantity_ordered = Decimal("10.00")
        item.quantity_received = Decimal("10.00")
        assert item.is_fully_received is True

    def test_is_fully_received_over_received(self):
        """is_fully_received should be True when qty_received > qty_ordered."""
        item = PurchaseOrderItem()
        item.quantity_ordered = Decimal("10.00")
        item.quantity_received = Decimal("12.00")
        assert item.is_fully_received is True

    def test_repr(self):
        """PurchaseOrderItem __repr__ should include key fields."""
        item = PurchaseOrderItem()
        item.purchase_order_id = uuid.uuid4()
        item.spare_part_id = uuid.uuid4()
        item.quantity_ordered = Decimal("5.00")
        item.quantity_received = Decimal("0.00")
        item.unit_cost = Decimal("10.00")
        repr_str = repr(item)
        assert "PurchaseOrderItem" in repr_str
        assert "qty_ordered" in repr_str


# =============================================================================
# PurchaseOrder.calculate_total Tests (Req 9.8)
# =============================================================================


class TestPurchaseOrderCalculateTotal:
    """Test PurchaseOrder.calculate_total method (Req 9.8)."""

    def test_calculate_total_empty_items(self):
        """calculate_total with no items should return 0."""
        po = PurchaseOrder()
        po.items = []
        assert po.calculate_total() == Decimal("0.00")

    def test_calculate_total_single_item(self):
        """calculate_total with one item should return qty * unit_cost."""
        po = PurchaseOrder()
        item = PurchaseOrderItem()
        item.quantity_ordered = Decimal("10.00")
        item.unit_cost = Decimal("25.00")
        po.items = [item]
        assert po.calculate_total() == Decimal("250.00")

    def test_calculate_total_multiple_items(self):
        """calculate_total with multiple items should sum all line totals."""
        po = PurchaseOrder()
        item1 = PurchaseOrderItem()
        item1.quantity_ordered = Decimal("10.00")
        item1.unit_cost = Decimal("25.00")

        item2 = PurchaseOrderItem()
        item2.quantity_ordered = Decimal("5.00")
        item2.unit_cost = Decimal("100.00")

        po.items = [item1, item2]
        # 10*25 + 5*100 = 250 + 500 = 750
        assert po.calculate_total() == Decimal("750.00")

    def test_calculate_total_decimal_precision(self):
        """calculate_total should handle decimal precision correctly."""
        po = PurchaseOrder()
        item = PurchaseOrderItem()
        item.quantity_ordered = Decimal("3.50")
        item.unit_cost = Decimal("12.99")
        po.items = [item]
        # 3.50 * 12.99 = 45.465
        assert po.calculate_total() == Decimal("45.4650")


# =============================================================================
# Import/Export Tests
# =============================================================================


class TestPurchaseOrderImports:
    """Test that models are properly exported from the models package."""

    def test_purchase_order_importable_from_package(self):
        """PurchaseOrder should be importable from app.models."""
        from app.models import PurchaseOrder as PO
        assert PO is PurchaseOrder

    def test_purchase_order_item_importable_from_package(self):
        """PurchaseOrderItem should be importable from app.models."""
        from app.models import PurchaseOrderItem as POI
        assert POI is PurchaseOrderItem

    def test_purchase_order_status_importable_from_package(self):
        """PurchaseOrderStatus should be importable from app.models."""
        from app.models import PurchaseOrderStatus as POS
        assert POS is PurchaseOrderStatus
