"""Unit tests for AuditSession, AuditSnapshotItem, and AuditCount models."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from sqlalchemy import Numeric, Enum, DateTime, inspect
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.audit_session import (
    AuditSession,
    AuditSnapshotItem,
    AuditCount,
    AuditType,
    AuditStatus,
)
from app.models.base import BaseModel


# =============================================================================
# AuditType Enum Tests
# =============================================================================


class TestAuditTypeEnum:
    """Test AuditType enumeration values (Requirement 11.1)."""

    def test_cycle_count_type(self):
        """AuditType should have a CYCLE_COUNT value."""
        assert AuditType.CYCLE_COUNT == "CYCLE_COUNT"

    def test_full_stock_count_type(self):
        """AuditType should have a FULL_STOCK_COUNT value."""
        assert AuditType.FULL_STOCK_COUNT == "FULL_STOCK_COUNT"

    def test_all_types_present(self):
        """AuditType should have exactly 2 members."""
        assert len(AuditType) == 2

    def test_audit_type_is_str_enum(self):
        """AuditType values should be usable as strings."""
        assert str(AuditType.CYCLE_COUNT) == "AuditType.CYCLE_COUNT"
        assert AuditType.CYCLE_COUNT.value == "CYCLE_COUNT"


# =============================================================================
# AuditStatus Enum Tests
# =============================================================================


class TestAuditStatusEnum:
    """Test AuditStatus enumeration values."""

    def test_initiated_status(self):
        """AuditStatus should have an INITIATED value."""
        assert AuditStatus.INITIATED == "INITIATED"

    def test_in_progress_status(self):
        """AuditStatus should have an IN_PROGRESS value."""
        assert AuditStatus.IN_PROGRESS == "IN_PROGRESS"

    def test_completed_status(self):
        """AuditStatus should have a COMPLETED value."""
        assert AuditStatus.COMPLETED == "COMPLETED"

    def test_cancelled_status(self):
        """AuditStatus should have a CANCELLED value."""
        assert AuditStatus.CANCELLED == "CANCELLED"

    def test_all_statuses_present(self):
        """AuditStatus should have exactly 4 members."""
        assert len(AuditStatus) == 4


# =============================================================================
# AuditSession Model Tests
# =============================================================================


class TestAuditSessionModel:
    """Test AuditSession model definition (Requirements 11.1, 11.2)."""

    def test_inherits_base_model(self):
        """AuditSession should inherit from BaseModel."""
        assert issubclass(AuditSession, BaseModel)

    def test_tablename(self):
        """AuditSession should map to the 'audit_sessions' table."""
        assert AuditSession.__tablename__ == "audit_sessions"

    def test_location_id_column(self):
        """AuditSession should have a non-nullable location_id FK."""
        col = AuditSession.__table__.columns["location_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "locations.id"

    def test_audit_type_column(self):
        """AuditSession should have a non-nullable audit_type enum column."""
        col = AuditSession.__table__.columns["audit_type"]
        assert isinstance(col.type, Enum)
        assert col.nullable is False

    def test_status_column(self):
        """AuditSession should have a non-nullable status enum column."""
        col = AuditSession.__table__.columns["status"]
        assert isinstance(col.type, Enum)
        assert col.nullable is False

    def test_snapshot_timestamp_column(self):
        """AuditSession should have a non-nullable snapshot_timestamp column."""
        col = AuditSession.__table__.columns["snapshot_timestamp"]
        assert isinstance(col.type, DateTime)
        assert col.nullable is False

    def test_completed_at_column(self):
        """AuditSession should have a nullable completed_at column."""
        col = AuditSession.__table__.columns["completed_at"]
        assert isinstance(col.type, DateTime)
        assert col.nullable is True

    def test_initiated_by_column(self):
        """AuditSession should have a non-nullable initiated_by FK to users."""
        col = AuditSession.__table__.columns["initiated_by"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "users.id"

    def test_approved_by_column(self):
        """AuditSession should have a nullable approved_by FK to users."""
        col = AuditSession.__table__.columns["approved_by"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is True
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "users.id"

    def test_has_audit_columns(self):
        """AuditSession should have inherited audit columns from BaseModel."""
        table = AuditSession.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns
        assert "created_by" in table.columns
        assert "updated_by" in table.columns

    def test_has_snapshot_items_relationship(self):
        """AuditSession should have a 'snapshot_items' relationship."""
        mapper = inspect(AuditSession)
        relationship_names = [r.key for r in mapper.relationships]
        assert "snapshot_items" in relationship_names

    def test_has_counts_relationship(self):
        """AuditSession should have a 'counts' relationship."""
        mapper = inspect(AuditSession)
        relationship_names = [r.key for r in mapper.relationships]
        assert "counts" in relationship_names

    def test_location_status_index_exists(self):
        """AuditSession should have an index on (location_id, status)."""
        indexes = AuditSession.__table__.indexes
        index_names = {idx.name for idx in indexes}
        assert "ix_audit_sessions_location_status" in index_names

    def test_status_index_exists(self):
        """AuditSession should have an index on status."""
        indexes = AuditSession.__table__.indexes
        index_names = {idx.name for idx in indexes}
        assert "ix_audit_sessions_status" in index_names


# =============================================================================
# AuditSession Instance Tests
# =============================================================================


class TestAuditSessionInstance:
    """Test AuditSession instance creation and defaults."""

    def test_instance_with_required_fields(self):
        """An AuditSession instance should be creatable with required fields."""
        location_id = uuid.uuid4()
        initiated_by = uuid.uuid4()
        session = AuditSession(
            location_id=location_id,
            audit_type=AuditType.CYCLE_COUNT,
            initiated_by=initiated_by,
        )
        assert session.location_id == location_id
        assert session.audit_type == AuditType.CYCLE_COUNT
        assert session.initiated_by == initiated_by

    def test_default_status_is_initiated(self):
        """AuditSession should default to INITIATED status."""
        col = AuditSession.__table__.columns["status"]
        assert col.default.arg == AuditStatus.INITIATED

    def test_completed_at_defaults_to_none(self):
        """AuditSession completed_at should default to None."""
        session = AuditSession(
            location_id=uuid.uuid4(),
            audit_type=AuditType.FULL_STOCK_COUNT,
            initiated_by=uuid.uuid4(),
        )
        assert session.completed_at is None

    def test_approved_by_defaults_to_none(self):
        """AuditSession approved_by should default to None."""
        session = AuditSession(
            location_id=uuid.uuid4(),
            audit_type=AuditType.FULL_STOCK_COUNT,
            initiated_by=uuid.uuid4(),
        )
        assert session.approved_by is None

    def test_full_instance_creation(self):
        """An AuditSession can be created with all fields populated."""
        location_id = uuid.uuid4()
        initiated_by = uuid.uuid4()
        approved_by = uuid.uuid4()
        now = datetime.now(timezone.utc)
        session = AuditSession(
            location_id=location_id,
            audit_type=AuditType.FULL_STOCK_COUNT,
            status=AuditStatus.COMPLETED,
            snapshot_timestamp=now,
            initiated_by=initiated_by,
            approved_by=approved_by,
            completed_at=now,
        )
        assert session.status == AuditStatus.COMPLETED
        assert session.snapshot_timestamp == now
        assert session.approved_by == approved_by
        assert session.completed_at == now

    def test_repr(self):
        """AuditSession repr should include key identifiers."""
        location_id = uuid.uuid4()
        session = AuditSession(
            location_id=location_id,
            audit_type=AuditType.CYCLE_COUNT,
            status=AuditStatus.INITIATED,
            initiated_by=uuid.uuid4(),
        )
        result = repr(session)
        assert "AuditSession" in result
        assert str(location_id) in result


# =============================================================================
# AuditSnapshotItem Model Tests
# =============================================================================


class TestAuditSnapshotItemModel:
    """Test AuditSnapshotItem model definition."""

    def test_inherits_base_model(self):
        """AuditSnapshotItem should inherit from BaseModel."""
        assert issubclass(AuditSnapshotItem, BaseModel)

    def test_tablename(self):
        """AuditSnapshotItem should map to the 'audit_snapshot_items' table."""
        assert AuditSnapshotItem.__tablename__ == "audit_snapshot_items"

    def test_session_id_column(self):
        """AuditSnapshotItem should have a non-nullable session_id FK."""
        col = AuditSnapshotItem.__table__.columns["session_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "audit_sessions.id"

    def test_spare_part_id_column(self):
        """AuditSnapshotItem should have a non-nullable spare_part_id FK."""
        col = AuditSnapshotItem.__table__.columns["spare_part_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "spare_parts.id"

    def test_snapshot_quantity_column(self):
        """AuditSnapshotItem should have a non-nullable Numeric snapshot_quantity column."""
        col = AuditSnapshotItem.__table__.columns["snapshot_quantity"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_has_audit_columns(self):
        """AuditSnapshotItem should have inherited audit columns."""
        table = AuditSnapshotItem.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns

    def test_unique_index_on_session_part(self):
        """AuditSnapshotItem should have a unique index on (session_id, spare_part_id)."""
        indexes = AuditSnapshotItem.__table__.indexes
        found = False
        for idx in indexes:
            if idx.name == "ix_audit_snapshot_items_session_part":
                found = True
                assert idx.unique is True
        assert found, "Unique index on (session_id, spare_part_id) not found"

    def test_has_session_relationship(self):
        """AuditSnapshotItem should have a 'session' relationship."""
        mapper = inspect(AuditSnapshotItem)
        relationship_names = [r.key for r in mapper.relationships]
        assert "session" in relationship_names


# =============================================================================
# AuditSnapshotItem Instance Tests
# =============================================================================


class TestAuditSnapshotItemInstance:
    """Test AuditSnapshotItem instance creation."""

    def test_instance_creation(self):
        """An AuditSnapshotItem instance should be creatable with required fields."""
        session_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()
        item = AuditSnapshotItem(
            session_id=session_id,
            spare_part_id=spare_part_id,
            snapshot_quantity=Decimal("25.0000"),
        )
        assert item.session_id == session_id
        assert item.spare_part_id == spare_part_id
        assert item.snapshot_quantity == Decimal("25.0000")

    def test_repr(self):
        """AuditSnapshotItem repr should include key identifiers."""
        session_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()
        item = AuditSnapshotItem(
            session_id=session_id,
            spare_part_id=spare_part_id,
            snapshot_quantity=Decimal("10.0000"),
        )
        result = repr(item)
        assert "AuditSnapshotItem" in result
        assert str(session_id) in result
        assert str(spare_part_id) in result


# =============================================================================
# AuditCount Model Tests
# =============================================================================


class TestAuditCountModel:
    """Test AuditCount model definition."""

    def test_inherits_base_model(self):
        """AuditCount should inherit from BaseModel."""
        assert issubclass(AuditCount, BaseModel)

    def test_tablename(self):
        """AuditCount should map to the 'audit_counts' table."""
        assert AuditCount.__tablename__ == "audit_counts"

    def test_session_id_column(self):
        """AuditCount should have a non-nullable session_id FK."""
        col = AuditCount.__table__.columns["session_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "audit_sessions.id"

    def test_spare_part_id_column(self):
        """AuditCount should have a non-nullable spare_part_id FK."""
        col = AuditCount.__table__.columns["spare_part_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "spare_parts.id"

    def test_counted_quantity_column(self):
        """AuditCount should have a non-nullable Numeric counted_quantity column."""
        col = AuditCount.__table__.columns["counted_quantity"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_variance_column(self):
        """AuditCount should have a non-nullable Numeric variance column."""
        col = AuditCount.__table__.columns["variance"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_counted_by_column(self):
        """AuditCount should have a non-nullable counted_by FK to users."""
        col = AuditCount.__table__.columns["counted_by"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "users.id"

    def test_counted_at_column(self):
        """AuditCount should have a non-nullable counted_at timestamp column."""
        col = AuditCount.__table__.columns["counted_at"]
        assert isinstance(col.type, DateTime)
        assert col.nullable is False

    def test_has_audit_columns(self):
        """AuditCount should have inherited audit columns."""
        table = AuditCount.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns

    def test_session_part_index_exists(self):
        """AuditCount should have an index on (session_id, spare_part_id)."""
        indexes = AuditCount.__table__.indexes
        index_names = {idx.name for idx in indexes}
        assert "ix_audit_counts_session_part" in index_names

    def test_session_id_index_exists(self):
        """AuditCount should have an index on session_id."""
        indexes = AuditCount.__table__.indexes
        index_names = {idx.name for idx in indexes}
        assert "ix_audit_counts_session_id" in index_names

    def test_has_session_relationship(self):
        """AuditCount should have a 'session' relationship."""
        mapper = inspect(AuditCount)
        relationship_names = [r.key for r in mapper.relationships]
        assert "session" in relationship_names


# =============================================================================
# AuditCount Instance Tests
# =============================================================================


class TestAuditCountInstance:
    """Test AuditCount instance creation and defaults."""

    def test_instance_creation(self):
        """An AuditCount instance should be creatable with required fields."""
        session_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()
        counted_by = uuid.uuid4()
        count = AuditCount(
            session_id=session_id,
            spare_part_id=spare_part_id,
            counted_quantity=Decimal("23.0000"),
            variance=Decimal("-2.0000"),
            counted_by=counted_by,
        )
        assert count.session_id == session_id
        assert count.spare_part_id == spare_part_id
        assert count.counted_quantity == Decimal("23.0000")
        assert count.variance == Decimal("-2.0000")
        assert count.counted_by == counted_by

    def test_default_variance_is_zero(self):
        """AuditCount variance column should default to 0."""
        col = AuditCount.__table__.columns["variance"]
        assert col.default.arg == Decimal("0")

    def test_positive_variance(self):
        """AuditCount can have positive variance (counted > snapshot)."""
        count = AuditCount(
            session_id=uuid.uuid4(),
            spare_part_id=uuid.uuid4(),
            counted_quantity=Decimal("30.0000"),
            variance=Decimal("5.0000"),
            counted_by=uuid.uuid4(),
        )
        assert count.variance == Decimal("5.0000")

    def test_zero_variance(self):
        """AuditCount can have zero variance (counted == snapshot)."""
        count = AuditCount(
            session_id=uuid.uuid4(),
            spare_part_id=uuid.uuid4(),
            counted_quantity=Decimal("25.0000"),
            variance=Decimal("0.0000"),
            counted_by=uuid.uuid4(),
        )
        assert count.variance == Decimal("0.0000")

    def test_repr(self):
        """AuditCount repr should include key identifiers."""
        session_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()
        count = AuditCount(
            session_id=session_id,
            spare_part_id=spare_part_id,
            counted_quantity=Decimal("20.0000"),
            variance=Decimal("-5.0000"),
            counted_by=uuid.uuid4(),
        )
        result = repr(count)
        assert "AuditCount" in result
        assert str(session_id) in result
        assert str(spare_part_id) in result
