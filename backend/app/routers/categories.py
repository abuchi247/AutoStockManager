"""Category management router with CRUD endpoints.

Provides the following endpoints:
- GET    /api/v1/categories              - List all categories (paginated)
- POST   /api/v1/categories              - Create a new category (Admin, Manager)
- GET    /api/v1/categories/{id}         - Get category by ID
- PUT    /api/v1/categories/{id}         - Update a category (Admin, Manager)
- DELETE /api/v1/categories/{id}         - Soft-delete a category (Admin only)

Satisfies Requirement 3.4: Support hierarchical categorization with categories
and subcategories.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.category import Category
from app.models.spare_part import SparePart
from app.models.user import User, UserRole
from app.models.base import SoftDeleteQuery
from app.schemas.auth import ErrorResponse
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])


# =============================================================================
# Helper Functions
# =============================================================================


def _build_category_response(category: Category, depth: int = 0) -> CategoryResponse:
    """Build a CategoryResponse from a Category model, including children and spare parts count.
    
    Limits recursion depth to avoid lazy loading issues in async context.
    """
    # Count spare parts using this category (as primary category)
    try:
        spare_parts_count = len(category.spare_parts_as_category) if category.spare_parts_as_category else 0
    except Exception:
        spare_parts_count = 0

    # Build children (limit to 1 level deep to avoid lazy loading issues)
    children = []
    if depth < 1 and category.children:
        for child in category.children:
            if child.deleted_at is None:
                children.append(_build_category_response(child, depth + 1))

    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        children=children,
        spare_parts_count=spare_parts_count,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=CategoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all categories",
    description="Retrieve a paginated list of all active categories with their subcategories.",
)
async def list_categories(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=100, ge=1, le=500, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Search by name"),
    parent_only: bool = Query(default=False, description="Only return top-level categories"),
) -> CategoryListResponse:
    """List all active categories with pagination.

    Accessible by all authenticated users.
    """
    # Base query filtering out soft-deleted records
    base_query = SoftDeleteQuery.active(select(Category), Category)

    if parent_only:
        base_query = base_query.filter(Category.parent_id.is_(None))

    if search:
        search_filter = f"%{search}%"
        base_query = base_query.filter(Category.name.ilike(search_filter))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Paginated results with eager loading of children and spare_parts
    offset = (page - 1) * page_size
    stmt = (
        base_query
        .options(
            selectinload(Category.children),
            selectinload(Category.spare_parts_as_category),
        )
        .order_by(Category.name.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    categories = result.scalars().all()

    return CategoryListResponse(
        data=[_build_category_response(cat) for cat in categories],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category",
    description="Create a new category. Admin or Manager only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_category(
    request: CategoryCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> CategoryResponse:
    """Create a new category.

    Requirement 3.4: Support hierarchical categorization.
    """
    # Validate parent_id if provided
    if request.parent_id:
        parent_stmt = SoftDeleteQuery.active(
            select(Category).filter(Category.id == request.parent_id), Category
        )
        parent_result = await db.execute(parent_stmt)
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found",
            )

    category = Category(
        name=request.name,
        parent_id=request.parent_id,
        description=request.description,
        is_active=request.is_active,
        created_by=str(current_user.id),
    )

    db.add(category)
    await db.commit()
    await db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        children=[],
        spare_parts_count=0,
    )


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category by ID",
    description="Retrieve a single category by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Category not found"},
    },
)
async def get_category(
    category_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CategoryResponse:
    """Get a single category by ID.

    Accessible by all authenticated users.
    """
    stmt = (
        SoftDeleteQuery.active(
            select(Category).filter(Category.id == category_id), Category
        )
        .options(
            selectinload(Category.children),
            selectinload(Category.spare_parts_as_category),
        )
    )
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    return _build_category_response(category)


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a category",
    description="Update an existing category's attributes. Admin or Manager only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Category not found"},
    },
)
async def update_category(
    category_id: UUID,
    request: CategoryUpdate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> CategoryResponse:
    """Update a category's attributes (partial update)."""
    stmt = (
        SoftDeleteQuery.active(
            select(Category).filter(Category.id == category_id), Category
        )
        .options(
            selectinload(Category.children),
            selectinload(Category.spare_parts_as_category),
        )
    )
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Validate parent_id if being changed
    update_data = request.model_dump(exclude_unset=True)
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        # Prevent setting parent to self
        if update_data["parent_id"] == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category cannot be its own parent",
            )
        parent_stmt = SoftDeleteQuery.active(
            select(Category).filter(Category.id == update_data["parent_id"]), Category
        )
        parent_result = await db.execute(parent_stmt)
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found",
            )

    # Apply only the fields that were provided
    for field, value in update_data.items():
        setattr(category, field, value)

    category.updated_by = str(current_user.id)

    await db.commit()
    await db.refresh(category)
    return _build_category_response(category)


@router.delete(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a category",
    description="Soft-delete a category. Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Category not found"},
    },
)
async def delete_category(
    category_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.ADMIN)
    ),
) -> CategoryResponse:
    """Soft-delete a category.

    Only Admins can delete categories.
    """
    stmt = (
        SoftDeleteQuery.active(
            select(Category).filter(Category.id == category_id), Category
        )
        .options(
            selectinload(Category.children),
            selectinload(Category.spare_parts_as_category),
        )
    )
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    response = _build_category_response(category)
    category.soft_delete(deleted_by=str(current_user.id))
    await db.commit()
    return response
