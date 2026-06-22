"""
SQLAlchemy ORM models package.

This package contains all database model definitions for the Auto Spare Parts
ERP system. Models are organized by domain and all inherit from BaseModel
(which provides audit columns) and optionally use SoftDeleteMixin for
financial/important records that require soft-deletion.

Exports:
    BaseModel          - Abstract base with id, created_at, updated_at, created_by, updated_by
    SoftDeleteMixin    - Mixin adding deleted_at, deleted_by for soft-delete support
    SoftDeleteQuery    - Helper class for building soft-delete-aware queries
    with_soft_delete_filter - Function to apply soft-delete filtering to any query
    User               - User authentication and authorization model
    Category           - Hierarchical category model
    SparePart          - Spare part product model
    LoginHistory       - Login attempt history model
    InventoryMovementLedger - Append-only immutable ledger for stock movements
    MovementType       - Enum of movement types (PURCHASE, SALE, TRANSFER_OUT, etc.)
    ReferenceType      - Enum of reference document types (sale, grn, transfer, etc.)
    CostLayer          - FIFO cost layer for inventory valuation
    StockStatusCache   - Stock quantity cache per part per location
    Sale               - Sale transaction model
    SaleItem           - Sale line item model
    SaleStatus         - Enum of sale lifecycle statuses
    PaymentType        - Enum of payment types
    CustomerCreditLedger - Append-only immutable ledger for customer credit transactions
    CreditTransactionType - Enum of credit transaction types (SALE, PAYMENT, ADJUSTMENT, RETURN)
"""

from app.models.base import BaseModel, SoftDeleteMixin, SoftDeleteQuery, with_soft_delete_filter
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.spare_part import SparePart
from app.models.login_history import LoginHistory
from app.models.inventory_movement_ledger import (
    InventoryMovementLedger,
    MovementType,
    ReferenceType,
)
from app.models.cost_layer import CostLayer
from app.models.stock_status_cache import StockStatusCache
from app.models.sale import Sale, SaleItem, SaleStatus, PaymentType
from app.models.transfer import Transfer, TransferStatus, VALID_TRANSFER_TRANSITIONS
from app.models.customer import Customer, AccountStatus
from app.models.customer_credit_ledger import CustomerCreditLedger, CreditTransactionType

__all__ = [
    "BaseModel",
    "SoftDeleteMixin",
    "SoftDeleteQuery",
    "with_soft_delete_filter",
    "User",
    "UserRole",
    "Category",
    "SparePart",
    "LoginHistory",
    "InventoryMovementLedger",
    "MovementType",
    "ReferenceType",
    "CostLayer",
    "StockStatusCache",
    "Sale",
    "SaleItem",
    "SaleStatus",
    "PaymentType",
    "Transfer",
    "TransferStatus",
    "VALID_TRANSFER_TRANSITIONS",
    "CustomerCreditLedger",
    "CreditTransactionType",
    "Customer",
    "AccountStatus",
]
