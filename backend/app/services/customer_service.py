"""Customer service implementing CRUD operations and purchase history.

Provides create, read, update, soft-delete, and purchase history retrieval
for customer records.

Satisfies Requirements:
- 6.1: Store customer profiles with all required attributes
- 6.2: Maintain complete purchase history for each customer
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.sale import Sale
from app.schemas.customer import CustomerCreate, CustomerUpdate


# =============================================================================
# Custom Exceptions
# =============================================================================


class CustomerNotFoundError(Exception):
    """Raised when a customer with the given ID is not found."""

    def __init__(self, customer_id: UUID):
        self.message = f"Customer with ID '{customer_id}' not found"
        super().__init__(self.message)


class DuplicateCustomerError(Exception):
    """Raised when a duplicate customer is detected."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


# =============================================================================
# Customer Service
# =============================================================================


class CustomerService:
    """Service handling customer CRUD operations and purchase history.

    All methods operate on non-deleted (active) records only, respecting
    the soft-delete pattern used throughout the ERP system.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the customer service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    async def create_customer(
        self, data: CustomerCreate, created_by: Optional[str] = None
    ) -> Customer:
        """Create a new customer record.

        Satisfies Requirement 6.1: Store customer profiles with name, phone,
        email, address, tax_id, credit_limit, and account_status.

        Args:
            data: Validated customer creation data.
            created_by: User identifier performing the creation.

        Returns:
            The newly created Customer instance.
        """
        customer = Customer(
            name=data.name,
            phone=data.phone,
            email=data.email,
            address=data.address,
            tax_id=data.tax_id,
            credit_limit=data.credit_limit,
            account_status=data.account_status,
            created_by=created_by,
        )
        self.db.add(customer)
        await self.db.flush()
        await self.db.refresh(customer)
        return customer

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_customer(self, customer_id: UUID) -> Customer:
        """Retrieve a single customer by ID.

        Args:
            customer_id: UUID of the customer to retrieve.

        Returns:
            The Customer instance.

        Raises:
            CustomerNotFoundError: If no active customer with that ID exists.
        """
        stmt = select(Customer).filter(
            Customer.id == customer_id,
            Customer.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        customer = result.scalar_one_or_none()

        if customer is None:
            raise CustomerNotFoundError(customer_id)

        return customer

    async def list_customers(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[Customer], int]:
        """List customers with pagination and optional search.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            search: Optional search term to filter by name, phone, or email.

        Returns:
            Tuple of (list of customers, total count).
        """
        filters = [Customer.deleted_at.is_(None)]

        if search:
            search_term = f"%{search}%"
            from sqlalchemy import or_
            filters.append(
                or_(
                    Customer.name.ilike(search_term),
                    Customer.phone.ilike(search_term),
                    Customer.email.ilike(search_term),
                )
            )

        # Count total
        count_stmt = select(func.count(Customer.id)).filter(*filters)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(Customer)
            .filter(*filters)
            .order_by(Customer.name.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())

        return customers, total

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    async def update_customer(
        self,
        customer_id: UUID,
        data: CustomerUpdate,
        updated_by: Optional[str] = None,
    ) -> Customer:
        """Update an existing customer's attributes.

        Only non-None fields in the update data are applied.

        Args:
            customer_id: UUID of the customer to update.
            data: Validated partial update data.
            updated_by: User identifier performing the update.

        Returns:
            The updated Customer instance.

        Raises:
            CustomerNotFoundError: If no active customer with that ID exists.
        """
        customer = await self.get_customer(customer_id)

        # Apply updates for non-None fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        if updated_by:
            customer.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(customer)
        return customer

    # -------------------------------------------------------------------------
    # Soft Delete
    # -------------------------------------------------------------------------

    async def delete_customer(
        self, customer_id: UUID, deleted_by: Optional[str] = None
    ) -> Customer:
        """Soft-delete a customer.

        Marks the record with deleted_at and deleted_by timestamps instead
        of physically removing it.

        Args:
            customer_id: UUID of the customer to delete.
            deleted_by: User identifier performing the deletion.

        Returns:
            The soft-deleted Customer instance.

        Raises:
            CustomerNotFoundError: If no active customer with that ID exists.
        """
        customer = await self.get_customer(customer_id)
        customer.soft_delete(deleted_by=deleted_by)
        await self.db.flush()
        return customer

    # -------------------------------------------------------------------------
    # Purchase History
    # -------------------------------------------------------------------------

    async def get_purchase_history(
        self,
        customer_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Sale], int]:
        """Retrieve purchase history for a customer.

        Satisfies Requirement 6.2: Maintain complete purchase history for
        each customer including all sales transactions, dates, amounts,
        and payment status.

        Args:
            customer_id: UUID of the customer.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of sales, total count).

        Raises:
            CustomerNotFoundError: If no active customer with that ID exists.
        """
        # Verify customer exists
        await self.get_customer(customer_id)

        # Count total sales for this customer (exclude drafts - not completed transactions)
        count_stmt = select(func.count(Sale.id)).filter(
            Sale.customer_id == customer_id,
            Sale.deleted_at.is_(None),
            Sale.status != "DRAFT",
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(Sale)
            .filter(
                Sale.customer_id == customer_id,
                Sale.deleted_at.is_(None),
                Sale.status != "DRAFT",
            )
            .order_by(Sale.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        sales = list(result.scalars().all())

        return sales, total
