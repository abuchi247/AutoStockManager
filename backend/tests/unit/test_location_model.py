"""Unit tests for the Location model."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import Boolean, String

from app.models.location import Location
from app.models.base import BaseModel, SoftDeleteMixin


class TestLocationModelDefinition:
    """Test that Location model is correctly defined with required fields."""

    def test_location_inherits_base_model(self):
        """Location should inherit from BaseModel."""
        assert issubclass(Location, BaseModel)

    def test_location_inherits_soft_delete_mixin(self):
        """Location should inherit from SoftDeleteMixin."""
        assert issubclass(Location, SoftDeleteMixin)

    def test_tablename(self):
        """Location should use 'locations' as the table name."""
        assert Location.__tablename__ == "locations"

    def test_name_column_exists(self):
        """Location should have a name column of type String."""
        col = Location.__table__.columns["name"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_type_column_exists(self):
        """Location should have a type column of type String."""
        col = Location.__table__.columns["type"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_address_column_exists(self):
        """Location should have an address column of type String."""
        col = Location.__table__.columns["address"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_is_active_column_exists(self):
        """Location should have an is_active boolean column."""
        col = Location.__table__.columns["is_active"]
        assert isinstance(col.type, Boolean)
        assert col.nullable is False

    def test_is_active_default_is_true(self):
        """The is_active column should default to True."""
        col = Location.__table__.columns["is_active"]
        assert col.default is not None
        assert col.default.arg is True


class TestLocationModelInheritedColumns:
    """Test that Location inherits all BaseModel and SoftDeleteMixin columns."""

    def test_has_id_column(self):
        """Location should have the inherited UUID id column."""
        col = Location.__table__.columns["id"]
        assert col.primary_key is True

    def test_has_created_at_column(self):
        """Location should have the inherited created_at column."""
        assert "created_at" in Location.__table__.columns

    def test_has_updated_at_column(self):
        """Location should have the inherited updated_at column."""
        assert "updated_at" in Location.__table__.columns

    def test_has_created_by_column(self):
        """Location should have the inherited created_by column."""
        assert "created_by" in Location.__table__.columns

    def test_has_updated_by_column(self):
        """Location should have the inherited updated_by column."""
        assert "updated_by" in Location.__table__.columns

    def test_has_deleted_at_column(self):
        """Location should have the soft-delete deleted_at column."""
        assert "deleted_at" in Location.__table__.columns

    def test_has_deleted_by_column(self):
        """Location should have the soft-delete deleted_by column."""
        assert "deleted_by" in Location.__table__.columns


class TestLocationModelInstantiation:
    """Test creating Location instances."""

    def test_create_warehouse_location(self):
        """Should be able to create a warehouse location."""
        location = Location(
            name="Main Warehouse",
            type="warehouse",
            address="123 Industrial Ave, Lagos",
            created_by="admin-user",
        )
        assert location.name == "Main Warehouse"
        assert location.type == "warehouse"
        assert location.address == "123 Industrial Ave, Lagos"
        assert location.created_by == "admin-user"

    def test_create_retail_branch_location(self):
        """Should be able to create a retail branch location."""
        location = Location(
            name="Downtown Store",
            type="retail_branch",
            address="45 Market Street, Abuja",
        )
        assert location.name == "Downtown Store"
        assert location.type == "retail_branch"
        assert location.address == "45 Market Street, Abuja"

    def test_is_active_defaults_to_none_before_flush(self):
        """Before flush, is_active may be None (default fires at insert time) or True."""
        location = Location(
            name="Test",
            type="warehouse",
            address="Test Address",
        )
        # SQLAlchemy mapped_column defaults may apply at different times
        # depending on configuration. The column default is True.
        assert location.is_active is None or location.is_active is True

    def test_soft_delete_behavior(self):
        """Location should support soft_delete() from the mixin."""
        location = Location(
            name="Old Warehouse",
            type="warehouse",
            address="Old Address",
        )
        assert location.is_deleted is False

        location.soft_delete(deleted_by="admin")
        assert location.is_deleted is True
        assert location.deleted_by == "admin"
        assert isinstance(location.deleted_at, datetime)

    def test_restore_behavior(self):
        """Location should support restore() from the mixin."""
        location = Location(
            name="Restored Warehouse",
            type="warehouse",
            address="Some Address",
        )
        location.soft_delete(deleted_by="admin")
        location.restore()
        assert location.is_deleted is False
        assert location.deleted_at is None
        assert location.deleted_by is None
