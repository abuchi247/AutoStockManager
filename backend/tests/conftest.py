"""
Root test configuration with async database setup, session fixtures, and factory functions.

This module provides shared fixtures for all tests (unit, property, and integration).
It sets up an in-memory SQLite database for fast testing without requiring PostgreSQL,
configures pytest-asyncio, and provides factory functions for creating test entities.

Validates: Requirements 1.5, 1.10, 3.7
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.models.base import BaseModel, SoftDeleteMixin
from app.models.cost_layer import CostLayer
from app.models.customer_credit_ledger import CustomerCreditLedger, CreditTransactionType
from app.models.location import Location
from app.models.sale import Sale, SaleItem, SaleStatus, PaymentType
from app.models.spare_part import SparePart
from app.models.stock_status_cache import StockStatusCache
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User


# =============================================================================
# Async Test Database Engine (SQLite async for speed)
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestAsyncSessionFactory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# Database Setup / Teardown Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with fresh tables for each test.

    Creates all tables before the test and drops them after. Each test gets
    a completely clean database state.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session_committed() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session that auto-commits (for integration-style tests).

    Unlike db_session which rolls back, this commits changes so they can be
    read back within the same test.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# =============================================================================
# Factory Functions for Creating Test Entities
# =============================================================================


class TestFactory:
    """Factory class for creating test entities with sensible defaults.

    All factory methods return model instances without persisting them.
    Call session.add(instance) and await session.flush() to persist.
    """

    @staticmethod
    def create_user(
        username: str = "testuser",
        email: str = "test@example.com",
        role: str = "ADMIN",
        is_active: bool = True,
        password_hash: str = "$2b$12$dummy_hash_for_testing",
    ) -> User:
        """Create a User instance with defaults."""
        user = User()
        user.id = uuid.uuid4()
        user.username = username
        user.email = email
        user.role = role
        user.is_active = is_active
        user.password_hash = password_hash
        user.failed_login_attempts = 0
        user.created_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        return user

    @staticmethod
    def create_location(
        name: str = "Main Warehouse",
        location_type: str = "WAREHOUSE",
        address: str = "123 Test Street",
        is_active: bool = True,
    ) -> Location:
        """Create a Location instance with defaults."""
        location = Location()
        location.id = uuid.uuid4()
        location.name = name
        location.type = location_type
        location.address = address
        location.is_active = is_active
        location.created_at = datetime.now(timezone.utc)
        location.updated_at = datetime.now(timezone.utc)
        return location

    @staticmethod
    def create_spare_part(
        part_number: str = "SP-001",
        name: str = "Test Brake Pad",
        barcode: Optional[str] = None,
        brand: str = "TestBrand",
        unit_of_measure: str = "PCS",
        cost_price: Decimal = Decimal("25.00"),
        selling_price: Decimal = Decimal("40.00"),
        min_stock_level: Decimal = Decimal("10"),
        max_stock_level: Decimal = Decimal("100"),
        reorder_quantity: Decimal = Decimal("50"),
    ) -> SparePart:
        """Create a SparePart instance with defaults."""
        part = SparePart()
        part.id = uuid.uuid4()
        part.part_number = part_number
        part.name = name
        part.barcode = barcode or f"BAR-{uuid.uuid4().hex[:8]}"
        part.brand = brand
        part.unit_of_measure = unit_of_measure
        part.cost_price = cost_price
        part.selling_price = selling_price
        part.min_stock_level = min_stock_level
        part.max_stock_level = max_stock_level
        part.reorder_quantity = reorder_quantity
        part.created_at = datetime.now(timezone.utc)
        part.updated_at = datetime.now(timezone.utc)
        return part

    @staticmethod
    def create_cost_layer(
        spare_part_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        unit_cost: Decimal = Decimal("10.00"),
        original_quantity: Decimal = Decimal("100"),
        remaining_quantity: Optional[Decimal] = None,
        source_type: str = "purchase",
        created_at: Optional[datetime] = None,
    ) -> CostLayer:
        """Create a CostLayer instance with defaults."""
        layer = CostLayer()
        layer.id = uuid.uuid4()
        layer.spare_part_id = spare_part_id or uuid.uuid4()
        layer.location_id = location_id or uuid.uuid4()
        layer.unit_cost = unit_cost
        layer.original_quantity = original_quantity
        layer.remaining_quantity = (
            remaining_quantity if remaining_quantity is not None else original_quantity
        )
        layer.source_type = source_type
        layer.source_reference_id = uuid.uuid4()
        layer.created_at = created_at or datetime.now(timezone.utc)
        layer.updated_at = datetime.now(timezone.utc)
        return layer

    @staticmethod
    def create_stock_status_cache(
        spare_part_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        current_quantity: Decimal = Decimal("50"),
    ) -> StockStatusCache:
        """Create a StockStatusCache instance with defaults."""
        cache = StockStatusCache()
        cache.id = uuid.uuid4()
        cache.spare_part_id = spare_part_id or uuid.uuid4()
        cache.location_id = location_id or uuid.uuid4()
        cache.current_quantity = current_quantity
        cache.last_reconciled_at = datetime.now(timezone.utc)
        cache.updated_at = datetime.now(timezone.utc)
        return cache

    @staticmethod
    def create_credit_ledger_entry(
        customer_id: Optional[uuid.UUID] = None,
        transaction_type: str = CreditTransactionType.SALE.value,
        amount: Decimal = Decimal("100.00"),
        reference_type: str = "sale",
        notes: Optional[str] = None,
    ) -> CustomerCreditLedger:
        """Create a CustomerCreditLedger entry with defaults."""
        entry = CustomerCreditLedger()
        entry.id = uuid.uuid4()
        entry.customer_id = customer_id or uuid.uuid4()
        entry.transaction_type = transaction_type
        entry.amount = amount
        entry.reference_type = reference_type
        entry.reference_id = uuid.uuid4()
        entry.notes = notes
        entry.created_by = uuid.uuid4()
        entry.created_at = datetime.now(timezone.utc)
        return entry

    @staticmethod
    def create_transfer(
        spare_part_id: Optional[uuid.UUID] = None,
        source_location_id: Optional[uuid.UUID] = None,
        destination_location_id: Optional[uuid.UUID] = None,
        quantity: Decimal = Decimal("10"),
        status: str = TransferStatus.PENDING.value,
        requested_by: Optional[uuid.UUID] = None,
    ) -> Transfer:
        """Create a Transfer instance with defaults."""
        transfer = Transfer()
        transfer.id = uuid.uuid4()
        transfer.spare_part_id = spare_part_id or uuid.uuid4()
        transfer.source_location_id = source_location_id or uuid.uuid4()
        transfer.destination_location_id = destination_location_id or uuid.uuid4()
        transfer.quantity = quantity
        transfer.status = status
        transfer.requested_by = requested_by or uuid.uuid4()
        transfer.created_at = datetime.now(timezone.utc)
        transfer.updated_at = datetime.now(timezone.utc)
        return transfer


@pytest.fixture
def factory() -> TestFactory:
    """Provide access to the TestFactory for creating test entities."""
    return TestFactory()
