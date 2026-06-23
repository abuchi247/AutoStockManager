"""
SparePart model for the Auto Spare Parts ERP system.

This module defines the SparePart model which stores all product information
including identification, pricing, categorization, and stock level parameters.

Satisfies Requirement 3.1: Store each Spare_Part with: part number, barcode,
name, description, brand, category, subcategory, vehicle compatibility list,
unit of measure, cost price, selling price, minimum stock level, maximum stock
level, and reorder quantity.
"""

from typing import Optional
import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, SoftDeleteMixin
from app.models.category import Category


class SparePart(BaseModel, SoftDeleteMixin):
    """Spare part product model.

    Stores complete product information for each spare part in the inventory,
    including identification codes, pricing, categorization, and stock
    replenishment parameters.

    Satisfies Requirement 3.1: THE ERP_System SHALL store each Spare_Part with:
    part number, barcode, name, description, brand, category, subcategory,
    vehicle compatibility list, unit of measure, cost price, selling price,
    minimum stock level, maximum stock level, and reorder quantity.

    Columns:
        part_number          - Unique part identifier code
        barcode              - Scannable barcode (unique, nullable)
        name                 - Product display name
        description          - Optional product description
        brand                - Manufacturer/brand name
        category_id          - FK to primary category
        subcategory_id       - FK to subcategory (nullable)
        vehicle_compatibility - JSON list of compatible vehicles
        unit_of_measure      - Unit for quantity tracking (e.g., PCS, BOX, LTR)
        cost_price           - Purchase/cost price
        selling_price        - Retail selling price
        min_stock_level      - Minimum stock threshold for reorder alerts
        max_stock_level      - Maximum stock capacity
        reorder_quantity     - Default quantity to reorder

    Relationships:
        category    - The primary category for this part
        subcategory - The subcategory for this part (optional)
    """

    __tablename__ = "spare_parts"

    # -------------------------------------------------------------------------
    # Identification
    # -------------------------------------------------------------------------
    part_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique part identification number",
    )

    barcode: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Scannable barcode value (unique when present)",
    )

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Product display name",
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(2000),
        nullable=True,
        comment="Detailed product description",
    )

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
    brand: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Manufacturer or brand name",
    )

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
        comment="Primary category for this spare part (optional)",
    )

    subcategory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
        comment="Subcategory for this spare part (optional)",
    )

    vehicle_compatibility: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="JSON list of compatible vehicles",
    )

    # -------------------------------------------------------------------------
    # Unit of Measure
    # -------------------------------------------------------------------------
    unit_of_measure: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PCS",
        comment="Unit of measure (e.g., PCS, BOX, LTR, KG)",
    )

    # -------------------------------------------------------------------------
    # Pricing
    # -------------------------------------------------------------------------
    cost_price: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Purchase/cost price",
    )

    selling_price: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Retail selling price",
    )

    # -------------------------------------------------------------------------
    # Stock Level Parameters
    # -------------------------------------------------------------------------
    min_stock_level: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Minimum stock threshold triggering reorder alerts",
    )

    max_stock_level: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Maximum stock capacity for this part",
    )

    reorder_quantity: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Default quantity to reorder when stock is low",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    category: Mapped["Category"] = relationship(
        "Category",
        foreign_keys=[category_id],
        back_populates="spare_parts_as_category",
        lazy="selectin",
    )

    subcategory: Mapped[Optional["Category"]] = relationship(
        "Category",
        foreign_keys=[subcategory_id],
        back_populates="spare_parts_as_subcategory",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SparePart(id={self.id}, part_number='{self.part_number}', name='{self.name}')>"
