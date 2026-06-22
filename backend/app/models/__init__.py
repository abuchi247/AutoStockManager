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
"""

from app.models.base import BaseModel, SoftDeleteMixin, SoftDeleteQuery, with_soft_delete_filter
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.spare_part import SparePart

__all__ = [
    "BaseModel",
    "SoftDeleteMixin",
    "SoftDeleteQuery",
    "with_soft_delete_filter",
    "User",
    "UserRole",
    "Category",
    "SparePart",
]
