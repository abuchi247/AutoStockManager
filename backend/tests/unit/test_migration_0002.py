"""Unit tests for migration 0002 - base models, locations, spare_parts, and categories.

Verifies that the migration file correctly defines:
- Table creation for categories, locations, and spare_parts
- Partial unique indexes for soft-delete compatibility (Requirement 18.5)
- Performance indexes (Requirement 18.7)
- Proper revision chain (depends on migration 0001)
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Load the migration module with alembic.op properly mocked
# ---------------------------------------------------------------------------

MIGRATION_PATH = Path(__file__).parent.parent.parent / (
    "alembic/versions/20250102_000000_0002_base_models.py"
)


@pytest.fixture
def migration_module():
    """Dynamically load the migration module with alembic.op mocked."""
    # Create a mock for alembic.op
    mock_op = MagicMock()

    # We need to patch the alembic module that the migration imports from.
    # The local alembic package shadows the installed one, so we mock it.
    import alembic as real_alembic
    original_op = getattr(real_alembic, "op", None)
    real_alembic.op = mock_op

    try:
        # Remove cached module if it was previously loaded
        module_name = "migration_0002"
        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, MIGRATION_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module._mock_op = mock_op
        return module
    finally:
        # Restore original state
        if original_op is None:
            if hasattr(real_alembic, "op"):
                delattr(real_alembic, "op")
        else:
            real_alembic.op = original_op


class TestMigrationMetadata:
    """Test migration revision metadata."""

    def test_revision_id(self, migration_module):
        """Migration should have revision '0002'."""
        assert migration_module.revision == "0002"

    def test_down_revision(self, migration_module):
        """Migration should depend on '0001' (initial migration)."""
        assert migration_module.down_revision == "0001"

    def test_has_upgrade_function(self, migration_module):
        """Migration should define an upgrade() function."""
        assert hasattr(migration_module, "upgrade")
        assert callable(migration_module.upgrade)

    def test_has_downgrade_function(self, migration_module):
        """Migration should define a downgrade() function."""
        assert hasattr(migration_module, "downgrade")
        assert callable(migration_module.downgrade)


class TestMigrationUpgrade:
    """Test that upgrade() creates the expected tables and indexes."""

    def test_creates_categories_table(self, migration_module):
        """upgrade() should create the 'categories' table."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        create_calls = [
            c for c in mock_op.create_table.call_args_list
            if c[0][0] == "categories"
        ]
        assert len(create_calls) == 1, "Should create 'categories' table exactly once"

    def test_creates_locations_table(self, migration_module):
        """upgrade() should create the 'locations' table."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        create_calls = [
            c for c in mock_op.create_table.call_args_list
            if c[0][0] == "locations"
        ]
        assert len(create_calls) == 1, "Should create 'locations' table exactly once"

    def test_creates_spare_parts_table(self, migration_module):
        """upgrade() should create the 'spare_parts' table."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        create_calls = [
            c for c in mock_op.create_table.call_args_list
            if c[0][0] == "spare_parts"
        ]
        assert len(create_calls) == 1, "Should create 'spare_parts' table exactly once"

    def test_creates_partial_unique_index_part_number(self, migration_module):
        """upgrade() should create partial unique index on spare_parts.part_number.

        Requirement 18.5: Use partial unique indexes for soft-delete compatibility.
        """
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        index_calls = [
            c for c in mock_op.create_index.call_args_list
            if c[0][0] == "uix_spare_parts_part_number_active"
        ]
        assert len(index_calls) == 1, "Should create part_number partial unique index"

        call_args = index_calls[0]
        assert call_args[0][1] == "spare_parts"  # table name
        assert call_args[0][2] == ["part_number"]  # columns
        assert call_args[1]["unique"] is True  # unique=True
        # Verify postgresql_where is set (partial index condition)
        assert "postgresql_where" in call_args[1]

    def test_creates_partial_unique_index_barcode(self, migration_module):
        """upgrade() should create partial unique index on spare_parts.barcode.

        Requirement 18.5: Use partial unique indexes for soft-delete compatibility.
        """
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        index_calls = [
            c for c in mock_op.create_index.call_args_list
            if c[0][0] == "uix_spare_parts_barcode_active"
        ]
        assert len(index_calls) == 1, "Should create barcode partial unique index"

        call_args = index_calls[0]
        assert call_args[0][1] == "spare_parts"  # table name
        assert call_args[0][2] == ["barcode"]  # columns
        assert call_args[1]["unique"] is True  # unique=True
        # Verify postgresql_where is set (partial index condition)
        assert "postgresql_where" in call_args[1]

    def test_creates_performance_indexes(self, migration_module):
        """upgrade() should create performance indexes (Requirement 18.7)."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        index_names = [
            c[0][0] for c in mock_op.create_index.call_args_list
        ]
        # Verify performance indexes exist
        assert "ix_spare_parts_category_id" in index_names
        assert "ix_spare_parts_subcategory_id" in index_names
        assert "ix_spare_parts_brand" in index_names
        assert "ix_categories_parent_id" in index_names
        assert "ix_locations_is_active" in index_names

    def test_table_creation_order(self, migration_module):
        """Categories should be created before spare_parts (FK dependency)."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.upgrade()

        table_names = [
            c[0][0] for c in mock_op.create_table.call_args_list
        ]
        cat_idx = table_names.index("categories")
        sp_idx = table_names.index("spare_parts")
        assert cat_idx < sp_idx, "categories must be created before spare_parts"


class TestMigrationDowngrade:
    """Test that downgrade() drops tables and indexes in the correct order."""

    def test_drops_spare_parts_table(self, migration_module):
        """downgrade() should drop the 'spare_parts' table."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.downgrade()

        drop_calls = [
            c for c in mock_op.drop_table.call_args_list
            if c[0][0] == "spare_parts"
        ]
        assert len(drop_calls) == 1

    def test_drops_locations_table(self, migration_module):
        """downgrade() should drop the 'locations' table."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.downgrade()

        drop_calls = [
            c for c in mock_op.drop_table.call_args_list
            if c[0][0] == "locations"
        ]
        assert len(drop_calls) == 1

    def test_drops_categories_table(self, migration_module):
        """downgrade() should drop the 'categories' table."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.downgrade()

        drop_calls = [
            c for c in mock_op.drop_table.call_args_list
            if c[0][0] == "categories"
        ]
        assert len(drop_calls) == 1

    def test_drops_indexes_before_tables(self, migration_module):
        """downgrade() should drop indexes before dropping tables."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.downgrade()

        # Get call order
        all_calls = mock_op.method_calls
        drop_index_positions = [
            i for i, c in enumerate(all_calls) if c[0] == "drop_index"
        ]
        drop_table_positions = [
            i for i, c in enumerate(all_calls) if c[0] == "drop_table"
        ]

        if drop_index_positions and drop_table_positions:
            assert max(drop_index_positions) < min(drop_table_positions), (
                "All indexes should be dropped before any tables"
            )

    def test_drops_tables_in_reverse_dependency_order(self, migration_module):
        """spare_parts should be dropped before categories (FK dependency)."""
        mock_op = migration_module._mock_op
        mock_op.reset_mock()
        migration_module.downgrade()

        table_names = [
            c[0][0] for c in mock_op.drop_table.call_args_list
        ]
        sp_idx = table_names.index("spare_parts")
        cat_idx = table_names.index("categories")
        assert sp_idx < cat_idx, "spare_parts must be dropped before categories"
