"""
Unit tests for the CostLayer model and FIFO consumption algorithm.

Tests cover:
- CostLayer model instantiation and field types
- FIFO consumption order (oldest layers consumed first)
- Partial consumption across multiple layers
- InsufficientCostLayerError when layers are exhausted
- Decimal precision for monetary values
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.cost_layer import CostLayer
from app.utils.fifo import consume_fifo_layers, InsufficientCostLayerError


# =============================================================================
# CostLayer Model Tests
# =============================================================================


class TestCostLayerModel:
    """Tests for CostLayer model structure and instantiation."""

    def test_cost_layer_tablename(self):
        """CostLayer should use 'cost_layers' as table name."""
        assert CostLayer.__tablename__ == "cost_layers"

    def test_cost_layer_has_required_columns(self):
        """CostLayer should have all required columns defined."""
        column_names = {c.name for c in CostLayer.__table__.columns}
        required = {
            "id",
            "spare_part_id",
            "location_id",
            "unit_cost",
            "original_quantity",
            "remaining_quantity",
            "source_type",
            "source_reference_id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        }
        assert required.issubset(column_names)

    def test_cost_layer_spare_part_id_not_nullable(self):
        """spare_part_id column should not be nullable."""
        col = CostLayer.__table__.c.spare_part_id
        assert col.nullable is False

    def test_cost_layer_location_id_not_nullable(self):
        """location_id column should not be nullable."""
        col = CostLayer.__table__.c.location_id
        assert col.nullable is False

    def test_cost_layer_unit_cost_not_nullable(self):
        """unit_cost column should not be nullable."""
        col = CostLayer.__table__.c.unit_cost
        assert col.nullable is False

    def test_cost_layer_original_quantity_not_nullable(self):
        """original_quantity column should not be nullable."""
        col = CostLayer.__table__.c.original_quantity
        assert col.nullable is False

    def test_cost_layer_remaining_quantity_not_nullable(self):
        """remaining_quantity column should not be nullable."""
        col = CostLayer.__table__.c.remaining_quantity
        assert col.nullable is False

    def test_cost_layer_source_type_not_nullable(self):
        """source_type column should not be nullable."""
        col = CostLayer.__table__.c.source_type
        assert col.nullable is False

    def test_cost_layer_source_reference_id_not_nullable(self):
        """source_reference_id column should not be nullable."""
        col = CostLayer.__table__.c.source_reference_id
        assert col.nullable is False

    def test_cost_layer_has_partial_index(self):
        """CostLayer should have a partial composite index for FIFO lookup."""
        indexes = list(CostLayer.__table__.indexes)
        fifo_index = None
        for idx in indexes:
            if idx.name == "ix_cost_layers_fifo_lookup":
                fifo_index = idx
                break
        assert fifo_index is not None, "FIFO lookup index not found"
        # Verify it covers the right columns
        col_names = [c.name for c in fifo_index.columns]
        assert "spare_part_id" in col_names
        assert "location_id" in col_names
        assert "created_at" in col_names

    def test_cost_layer_unit_cost_precision(self):
        """unit_cost should have precision=12, scale=4 for monetary values."""
        col = CostLayer.__table__.c.unit_cost
        assert col.type.precision == 12
        assert col.type.scale == 4

    def test_cost_layer_repr(self):
        """CostLayer __repr__ should produce a readable string."""
        layer = CostLayer()
        layer.id = uuid.uuid4()
        layer.spare_part_id = uuid.uuid4()
        layer.location_id = uuid.uuid4()
        layer.unit_cost = Decimal("10.50")
        layer.original_quantity = Decimal("100")
        layer.remaining_quantity = Decimal("75")
        repr_str = repr(layer)
        assert "CostLayer" in repr_str
        assert "remaining=" in repr_str


# =============================================================================
# FIFO Consumption Algorithm Tests
# =============================================================================


def _make_layer(
    unit_cost: Decimal,
    remaining_quantity: Decimal,
    created_at: datetime,
    original_quantity: Decimal | None = None,
) -> CostLayer:
    """Helper to create a CostLayer instance for testing."""
    layer = CostLayer()
    layer.id = uuid.uuid4()
    layer.spare_part_id = uuid.uuid4()
    layer.location_id = uuid.uuid4()
    layer.unit_cost = unit_cost
    layer.original_quantity = original_quantity or remaining_quantity
    layer.remaining_quantity = remaining_quantity
    layer.source_type = "purchase"
    layer.source_reference_id = uuid.uuid4()
    layer.created_at = created_at
    return layer


class TestConsumeFifoLayers:
    """Tests for the consume_fifo_layers function."""

    @pytest.mark.asyncio
    async def test_single_layer_full_consumption(self):
        """Should consume entirely from a single layer when quantity matches."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        layer = _make_layer(
            unit_cost=Decimal("10.00"),
            remaining_quantity=Decimal("5"),
            created_at=now,
        )
        layer.spare_part_id = spare_part_id
        layer.location_id = location_id

        # Mock the database session
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [layer]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        total_cost, details = await consume_fifo_layers(
            db=db,
            spare_part_id=spare_part_id,
            location_id=location_id,
            quantity_to_consume=Decimal("5"),
        )

        assert total_cost == Decimal("50.00")
        assert len(details) == 1
        assert details[0]["quantity_consumed"] == Decimal("5")
        assert layer.remaining_quantity == Decimal("0")

    @pytest.mark.asyncio
    async def test_multiple_layers_fifo_order(self):
        """Should consume oldest layers first (FIFO order)."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        layer1 = _make_layer(
            unit_cost=Decimal("8.00"),
            remaining_quantity=Decimal("3"),
            created_at=now - timedelta(days=10),
        )
        layer2 = _make_layer(
            unit_cost=Decimal("12.00"),
            remaining_quantity=Decimal("5"),
            created_at=now - timedelta(days=5),
        )
        layer3 = _make_layer(
            unit_cost=Decimal("15.00"),
            remaining_quantity=Decimal("10"),
            created_at=now,
        )

        for layer in [layer1, layer2, layer3]:
            layer.spare_part_id = spare_part_id
            layer.location_id = location_id

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        # Layers are returned already ordered by created_at ASC
        mock_scalars.all.return_value = [layer1, layer2, layer3]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        # Consume 7 units: should take 3 from layer1 + 4 from layer2
        total_cost, details = await consume_fifo_layers(
            db=db,
            spare_part_id=spare_part_id,
            location_id=location_id,
            quantity_to_consume=Decimal("7"),
        )

        # Cost: 3 * 8.00 + 4 * 12.00 = 24 + 48 = 72
        assert total_cost == Decimal("72.00")
        assert len(details) == 2
        assert details[0]["quantity_consumed"] == Decimal("3")
        assert details[0]["unit_cost"] == Decimal("8.00")
        assert details[1]["quantity_consumed"] == Decimal("4")
        assert details[1]["unit_cost"] == Decimal("12.00")

        # Verify layer remaining quantities updated
        assert layer1.remaining_quantity == Decimal("0")
        assert layer2.remaining_quantity == Decimal("1")
        assert layer3.remaining_quantity == Decimal("10")  # untouched

    @pytest.mark.asyncio
    async def test_insufficient_layers_raises_error(self):
        """Should raise InsufficientCostLayerError when layers can't fulfill demand."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        layer = _make_layer(
            unit_cost=Decimal("5.00"),
            remaining_quantity=Decimal("3"),
            created_at=now,
        )
        layer.spare_part_id = spare_part_id
        layer.location_id = location_id

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [layer]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InsufficientCostLayerError) as exc_info:
            await consume_fifo_layers(
                db=db,
                spare_part_id=spare_part_id,
                location_id=location_id,
                quantity_to_consume=Decimal("10"),
            )

        assert exc_info.value.spare_part_id == spare_part_id
        assert exc_info.value.location_id == location_id
        assert exc_info.value.shortfall == Decimal("7")

    @pytest.mark.asyncio
    async def test_no_layers_raises_error(self):
        """Should raise InsufficientCostLayerError when no layers exist."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InsufficientCostLayerError) as exc_info:
            await consume_fifo_layers(
                db=db,
                spare_part_id=spare_part_id,
                location_id=location_id,
                quantity_to_consume=Decimal("1"),
            )

        assert exc_info.value.shortfall == Decimal("1")

    @pytest.mark.asyncio
    async def test_exact_quantity_across_all_layers(self):
        """Should succeed when quantity exactly matches total remaining across layers."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        layer1 = _make_layer(
            unit_cost=Decimal("10.00"),
            remaining_quantity=Decimal("5"),
            created_at=now - timedelta(days=2),
        )
        layer2 = _make_layer(
            unit_cost=Decimal("12.00"),
            remaining_quantity=Decimal("5"),
            created_at=now,
        )

        for layer in [layer1, layer2]:
            layer.spare_part_id = spare_part_id
            layer.location_id = location_id

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [layer1, layer2]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        total_cost, details = await consume_fifo_layers(
            db=db,
            spare_part_id=spare_part_id,
            location_id=location_id,
            quantity_to_consume=Decimal("10"),
        )

        # 5 * 10 + 5 * 12 = 50 + 60 = 110
        assert total_cost == Decimal("110.00")
        assert len(details) == 2
        assert layer1.remaining_quantity == Decimal("0")
        assert layer2.remaining_quantity == Decimal("0")

    @pytest.mark.asyncio
    async def test_decimal_precision_preserved(self):
        """Should preserve Decimal precision in cost calculations."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        layer = _make_layer(
            unit_cost=Decimal("3.3333"),
            remaining_quantity=Decimal("3.5"),
            created_at=now,
        )
        layer.spare_part_id = spare_part_id
        layer.location_id = location_id

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [layer]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        total_cost, details = await consume_fifo_layers(
            db=db,
            spare_part_id=spare_part_id,
            location_id=location_id,
            quantity_to_consume=Decimal("2.5"),
        )

        # 2.5 * 3.3333 = 8.33325
        expected = Decimal("2.5") * Decimal("3.3333")
        assert total_cost == expected
        assert layer.remaining_quantity == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_consumed_details_structure(self):
        """Consumed details should contain layer_id, quantity_consumed, unit_cost, layer_cost."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        layer = _make_layer(
            unit_cost=Decimal("7.50"),
            remaining_quantity=Decimal("10"),
            created_at=now,
        )
        layer.spare_part_id = spare_part_id
        layer.location_id = location_id

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [layer]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        _, details = await consume_fifo_layers(
            db=db,
            spare_part_id=spare_part_id,
            location_id=location_id,
            quantity_to_consume=Decimal("4"),
        )

        assert len(details) == 1
        detail = details[0]
        assert "layer_id" in detail
        assert detail["layer_id"] == layer.id
        assert detail["quantity_consumed"] == Decimal("4")
        assert detail["unit_cost"] == Decimal("7.50")
        assert detail["layer_cost"] == Decimal("30.00")


class TestInsufficientCostLayerError:
    """Tests for the InsufficientCostLayerError exception."""

    def test_error_attributes(self):
        """Error should store spare_part_id, location_id, and shortfall."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()
        shortfall = Decimal("5.5")

        error = InsufficientCostLayerError(
            spare_part_id=spare_part_id,
            location_id=location_id,
            shortfall=shortfall,
        )

        assert error.spare_part_id == spare_part_id
        assert error.location_id == location_id
        assert error.shortfall == shortfall

    def test_error_message(self):
        """Error message should contain relevant identifiers."""
        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()

        error = InsufficientCostLayerError(
            spare_part_id=spare_part_id,
            location_id=location_id,
            shortfall=Decimal("3"),
        )

        assert str(spare_part_id) in str(error)
        assert str(location_id) in str(error)
        assert "3" in str(error)

    def test_error_is_exception(self):
        """InsufficientCostLayerError should be an Exception."""
        error = InsufficientCostLayerError(
            spare_part_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            shortfall=Decimal("1"),
        )
        assert isinstance(error, Exception)
