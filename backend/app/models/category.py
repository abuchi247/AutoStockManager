"""
Category model for hierarchical product categorization.

This module defines the Category model supporting a tree structure where
categories can have subcategories via a self-referential parent_id foreign key.

Satisfies Requirement 3.4: Support hierarchical categorization with categories
and subcategories.
"""

from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.spare_part import SparePart


class Category(BaseModel, SoftDeleteMixin):
    """Hierarchical category model for organizing spare parts.

    Supports a parent/child tree structure where top-level categories have
    parent_id = NULL and subcategories reference their parent category.

    Satisfies Requirement 3.4: THE ERP_System SHALL support hierarchical
    categorization with categories and subcategories.

    Columns:
        name        - Category display name (required)
        parent_id   - FK to self for subcategory hierarchy (nullable for top-level)
        description - Optional category description
        is_active   - Whether this category is currently active/visible

    Relationships:
        parent   - The parent category (if this is a subcategory)
        children - Child subcategories of this category
        spare_parts_as_category    - Parts using this as their primary category
        spare_parts_as_subcategory - Parts using this as their subcategory
    """

    __tablename__ = "categories"

    # -------------------------------------------------------------------------
    # Columns
    # -------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Category display name",
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
        comment="Parent category ID for subcategory hierarchy (NULL for top-level)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Optional description of this category",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this category is currently active",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
        lazy="selectin",
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        lazy="selectin",
    )

    spare_parts_as_category: Mapped[list["SparePart"]] = relationship(
        "SparePart",
        foreign_keys="SparePart.category_id",
        back_populates="category",
        lazy="selectin",
    )

    spare_parts_as_subcategory: Mapped[list["SparePart"]] = relationship(
        "SparePart",
        foreign_keys="SparePart.subcategory_id",
        back_populates="subcategory",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', parent_id={self.parent_id})>"
