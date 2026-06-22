"""Unit tests for SparePart and Category models."""

import uuid

import pytest
from sqlalchemy import Boolean, Numeric, String, inspect
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID

from app.models.category import Category
from app.models.spare_part import SparePart
from app.models.base import BaseModel, SoftDeleteMixin


# =============================================================================
# Category Model Tests
# =============================================================================


class TestCategoryModel:
    """Test Category model definition (Requirement 3.4)."""

    def test_category_inherits_base_model(self):
        """Category should inherit from BaseModel."""
        assert issubclass(Category, BaseModel)

    def test_category_has_soft_delete_mixin(self):
        """Category should include SoftDeleteMixin."""
        assert issubclass(Category, SoftDeleteMixin)

    def test_category_tablename(self):
        """Category should map to the 'categories' table."""
        assert Category.__tablename__ == "categories"

    def test_category_name_column(self):
        """Category should have a non-nullable name column."""
        col = Category.__table__.columns["name"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_category_parent_id_column(self):
        """Category should have a nullable parent_id FK to self."""
        col = Category.__table__.columns["parent_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is True
        # Check FK references categories.id
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "categories.id"

    def test_category_description_column(self):
        """Category should have a nullable description column."""
        col = Category.__table__.columns["description"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_category_is_active_column(self):
        """Category should have a boolean is_active column defaulting to True."""
        col = Category.__table__.columns["is_active"]
        assert isinstance(col.type, Boolean)
        assert col.nullable is False

    def test_category_has_audit_columns(self):
        """Category should have inherited audit columns from BaseModel."""
        table = Category.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns
        assert "created_by" in table.columns
        assert "updated_by" in table.columns

    def test_category_has_soft_delete_columns(self):
        """Category should have soft-delete columns."""
        table = Category.__table__
        assert "deleted_at" in table.columns
        assert "deleted_by" in table.columns

    def test_category_self_referential_relationship(self):
        """Category should have parent and children relationships."""
        mapper = inspect(Category)
        relationship_names = [r.key for r in mapper.relationships]
        assert "parent" in relationship_names
        assert "children" in relationship_names

    def test_category_instance_defaults(self):
        """A new Category instance should have expected defaults."""
        cat = Category(name="Test Category")
        assert cat.name == "Test Category"
        assert cat.parent_id is None
        assert cat.description is None
        # is_active default is applied at flush/insert time by SQLAlchemy
        # Before flush, it may be None; verify the column default exists
        col = Category.__table__.columns["is_active"]
        assert col.default.arg is True
        assert cat.is_deleted is False

    def test_category_repr(self):
        """Category repr should include id, name, and parent_id."""
        cat = Category(name="Brakes")
        result = repr(cat)
        assert "Category" in result
        assert "Brakes" in result


# =============================================================================
# Category Hierarchy Tests
# =============================================================================


class TestCategoryHierarchy:
    """Test hierarchical categorization support (Requirement 3.4)."""

    def test_top_level_category_has_null_parent(self):
        """A top-level category should have parent_id = None."""
        cat = Category(name="Engine Parts")
        assert cat.parent_id is None

    def test_subcategory_has_parent_id(self):
        """A subcategory should reference a parent category via parent_id."""
        parent_id = uuid.uuid4()
        sub = Category(name="Oil Filters", parent_id=parent_id)
        assert sub.parent_id == parent_id


# =============================================================================
# SparePart Model Tests
# =============================================================================


class TestSparePartModel:
    """Test SparePart model definition (Requirement 3.1)."""

    def test_spare_part_inherits_base_model(self):
        """SparePart should inherit from BaseModel."""
        assert issubclass(SparePart, BaseModel)

    def test_spare_part_has_soft_delete_mixin(self):
        """SparePart should include SoftDeleteMixin."""
        assert issubclass(SparePart, SoftDeleteMixin)

    def test_spare_part_tablename(self):
        """SparePart should map to the 'spare_parts' table."""
        assert SparePart.__tablename__ == "spare_parts"

    def test_part_number_column(self):
        """SparePart should have a non-nullable part_number.

        Uniqueness is enforced via a partial unique index (WHERE deleted_at IS NULL)
        rather than a column-level constraint, per Requirement 18.5.
        """
        col = SparePart.__table__.columns["part_number"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_barcode_column(self):
        """SparePart should have a nullable barcode.

        Uniqueness is enforced via a partial unique index (WHERE deleted_at IS NULL)
        rather than a column-level constraint, per Requirement 18.5.
        """
        col = SparePart.__table__.columns["barcode"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_name_column(self):
        """SparePart should have a non-nullable name."""
        col = SparePart.__table__.columns["name"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_description_column(self):
        """SparePart should have a nullable description."""
        col = SparePart.__table__.columns["description"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_brand_column(self):
        """SparePart should have a nullable brand."""
        col = SparePart.__table__.columns["brand"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_category_id_column(self):
        """SparePart should have a non-nullable category_id FK."""
        col = SparePart.__table__.columns["category_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is False
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "categories.id"

    def test_subcategory_id_column(self):
        """SparePart should have a nullable subcategory_id FK."""
        col = SparePart.__table__.columns["subcategory_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.nullable is True
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "categories.id"

    def test_vehicle_compatibility_column(self):
        """SparePart should have a JSON vehicle_compatibility column."""
        col = SparePart.__table__.columns["vehicle_compatibility"]
        assert isinstance(col.type, JSON)
        assert col.nullable is True

    def test_unit_of_measure_column(self):
        """SparePart should have a non-nullable unit_of_measure."""
        col = SparePart.__table__.columns["unit_of_measure"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_cost_price_column(self):
        """SparePart should have a Numeric cost_price column."""
        col = SparePart.__table__.columns["cost_price"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_selling_price_column(self):
        """SparePart should have a Numeric selling_price column."""
        col = SparePart.__table__.columns["selling_price"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_min_stock_level_column(self):
        """SparePart should have a Numeric min_stock_level column."""
        col = SparePart.__table__.columns["min_stock_level"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_max_stock_level_column(self):
        """SparePart should have a Numeric max_stock_level column."""
        col = SparePart.__table__.columns["max_stock_level"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_reorder_quantity_column(self):
        """SparePart should have a Numeric reorder_quantity column."""
        col = SparePart.__table__.columns["reorder_quantity"]
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_spare_part_has_audit_columns(self):
        """SparePart should have inherited audit columns."""
        table = SparePart.__table__
        assert "id" in table.columns
        assert "created_at" in table.columns
        assert "updated_at" in table.columns
        assert "created_by" in table.columns
        assert "updated_by" in table.columns

    def test_spare_part_has_soft_delete_columns(self):
        """SparePart should have soft-delete columns."""
        table = SparePart.__table__
        assert "deleted_at" in table.columns
        assert "deleted_by" in table.columns

    def test_spare_part_has_category_relationships(self):
        """SparePart should have category and subcategory relationships."""
        mapper = inspect(SparePart)
        relationship_names = [r.key for r in mapper.relationships]
        assert "category" in relationship_names
        assert "subcategory" in relationship_names


class TestSparePartInstance:
    """Test SparePart instance creation and defaults."""

    def test_instance_creation_with_required_fields(self):
        """A SparePart instance should be creatable with required fields."""
        category_id = uuid.uuid4()
        part = SparePart(
            part_number="BP-001",
            name="Brake Pad Set",
            category_id=category_id,
            unit_of_measure="SET",
            cost_price=25.00,
            selling_price=45.00,
            min_stock_level=10,
            max_stock_level=100,
            reorder_quantity=20,
        )
        assert part.part_number == "BP-001"
        assert part.name == "Brake Pad Set"
        assert part.category_id == category_id
        assert part.unit_of_measure == "SET"
        assert part.barcode is None
        assert part.description is None
        assert part.brand is None
        assert part.subcategory_id is None

    def test_instance_with_all_fields(self):
        """A SparePart should accept all optional fields."""
        category_id = uuid.uuid4()
        subcategory_id = uuid.uuid4()
        part = SparePart(
            part_number="OF-002",
            barcode="1234567890123",
            name="Oil Filter",
            description="Premium oil filter for Toyota engines",
            brand="Toyota Genuine",
            category_id=category_id,
            subcategory_id=subcategory_id,
            vehicle_compatibility=[
                {"make": "Toyota", "model": "Camry", "year_from": 2015, "year_to": 2023}
            ],
            unit_of_measure="PCS",
            cost_price=8.50,
            selling_price=15.00,
            min_stock_level=20,
            max_stock_level=200,
            reorder_quantity=50,
        )
        assert part.barcode == "1234567890123"
        assert part.description == "Premium oil filter for Toyota engines"
        assert part.brand == "Toyota Genuine"
        assert part.subcategory_id == subcategory_id
        assert len(part.vehicle_compatibility) == 1
        assert part.vehicle_compatibility[0]["make"] == "Toyota"

    def test_spare_part_soft_delete(self):
        """SparePart should support soft deletion."""
        part = SparePart(
            part_number="TEST-001",
            name="Test Part",
            category_id=uuid.uuid4(),
            unit_of_measure="PCS",
            cost_price=10,
            selling_price=20,
            min_stock_level=5,
            max_stock_level=50,
            reorder_quantity=10,
        )
        assert part.is_deleted is False
        part.soft_delete(deleted_by="admin")
        assert part.is_deleted is True
        assert part.deleted_by == "admin"

    def test_spare_part_repr(self):
        """SparePart repr should include key identifiers."""
        part = SparePart(part_number="BP-001", name="Brake Pad")
        result = repr(part)
        assert "SparePart" in result
        assert "BP-001" in result
        assert "Brake Pad" in result
