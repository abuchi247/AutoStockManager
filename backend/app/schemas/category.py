"""Pydantic schemas for category management endpoints.

Defines request/response models for category CRUD operations.

Satisfies Requirement 3.4: Support hierarchical categorization with categories
and subcategories.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class CategoryCreate(BaseModel):
    """Request body for POST /api/v1/categories (create a new category)."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Category display name",
        examples=["Brakes"],
    )
    parent_id: Optional[UUID] = Field(
        default=None,
        description="Parent category ID for subcategory hierarchy (NULL for top-level)",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional description of this category",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this category is currently active",
    )


class CategoryUpdate(BaseModel):
    """Request body for PUT /api/v1/categories/{id} (partial update)."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Category display name",
    )
    parent_id: Optional[UUID] = Field(
        default=None,
        description="Parent category ID for subcategory hierarchy",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional description of this category",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether this category is currently active",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class CategoryResponse(BaseModel):
    """Response body for a single category."""

    id: UUID = Field(..., description="Category UUID")
    name: str = Field(..., description="Category name")
    parent_id: Optional[UUID] = Field(default=None, description="Parent category ID")
    description: Optional[str] = Field(default=None, description="Category description")
    is_active: bool = Field(..., description="Whether category is active")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")
    children: list["CategoryResponse"] = Field(
        default_factory=list, description="Child subcategories"
    )
    spare_parts_count: int = Field(default=0, description="Number of spare parts in this category")

    model_config = {"from_attributes": True}


# Rebuild model to resolve forward reference
CategoryResponse.model_rebuild()


class CategoryListResponse(BaseModel):
    """Response body for category list with pagination metadata."""

    data: list[CategoryResponse] = Field(..., description="List of categories")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0, "page_size": 20},
        description="Pagination metadata",
    )
