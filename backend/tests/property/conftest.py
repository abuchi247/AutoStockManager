"""
Hypothesis custom strategies and configuration for property-based testing.

This module defines reusable Hypothesis strategies that generate valid domain objects
for the Auto Spare Parts ERP system. These strategies constrain generated values to
realistic ranges matching database column types and business rules.

Validates: Requirements 1.5, 1.10, 3.7
"""

import uuid
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import settings, HealthCheck
from hypothesis import strategies as st

# =============================================================================
# Hypothesis Global Settings
# =============================================================================

# Configure default Hypothesis settings for the property test suite.
# max_examples=100 provides good coverage without being too slow.
# deadline=None disables per-example timeouts for async tests.
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

settings.register_profile(
    "ci",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

settings.register_profile(
    "quick",
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

settings.load_profile("default")


# =============================================================================
# Primitive Strategies
# =============================================================================

# UUIDs for foreign key references
uuids = st.builds(uuid.uuid4)

# Positive decimals for monetary/quantity values (precision 12, scale 4)
positive_decimals = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("99999999.9999"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Monetary amounts (precision 14, scale 2) — used for prices, totals
monetary_amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Quantities (positive integers or decimals for stock)
quantities = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("10000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Unit costs — realistic range for auto spare parts
unit_costs = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("50000.00"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Timestamps within a reasonable range (last 5 years to now)
timestamps = st.builds(
    lambda days_ago: datetime.now(timezone.utc) - timedelta(days=days_ago),
    st.integers(min_value=0, max_value=1825),
)


# =============================================================================
# Cost Layer Strategies
# =============================================================================

@st.composite
def cost_layers(draw, spare_part_id=None, location_id=None):
    """Generate a valid cost layer data dictionary.

    Generates cost layer data matching CostLayer model constraints:
    - spare_part_id and location_id are UUIDs
    - unit_cost is a positive decimal (precision 12, scale 4)
    - original_quantity is a positive decimal
    - remaining_quantity is between 0 and original_quantity (inclusive)
    - source_type is one of the valid types

    Args:
        spare_part_id: Optional fixed spare_part_id. Generates one if None.
        location_id: Optional fixed location_id. Generates one if None.

    Returns:
        Dictionary with cost layer field values.
    """
    sp_id = spare_part_id or draw(uuids)
    loc_id = location_id or draw(uuids)

    u_cost = draw(st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("50000.0000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ))

    orig_qty = draw(st.decimals(
        min_value=Decimal("1.0000"),
        max_value=Decimal("10000.0000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ))

    # remaining_quantity must be <= original_quantity and >= 0
    rem_qty = draw(st.decimals(
        min_value=Decimal("0.0000"),
        max_value=orig_qty,
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ))

    source_type = draw(st.sampled_from(["purchase", "transfer", "return", "adjustment"]))
    created_at = draw(timestamps)

    return {
        "spare_part_id": sp_id,
        "location_id": loc_id,
        "unit_cost": u_cost,
        "original_quantity": orig_qty,
        "remaining_quantity": rem_qty,
        "source_type": source_type,
        "source_reference_id": draw(uuids),
        "created_at": created_at,
    }


@st.composite
def cost_layer_lists(draw, min_size=1, max_size=10, spare_part_id=None, location_id=None):
    """Generate a list of cost layers ordered by created_at (FIFO order).

    Ensures layers are sorted chronologically with distinct timestamps,
    simulating a real FIFO queue of inventory batches.

    Args:
        min_size: Minimum number of layers.
        max_size: Maximum number of layers.
        spare_part_id: Fixed spare_part_id for all layers.
        location_id: Fixed location_id for all layers.

    Returns:
        List of cost layer dictionaries ordered by created_at ASC.
    """
    sp_id = spare_part_id or draw(uuids)
    loc_id = location_id or draw(uuids)

    n = draw(st.integers(min_value=min_size, max_value=max_size))
    layers = []

    base_time = datetime.now(timezone.utc) - timedelta(days=365)

    for i in range(n):
        layer_time = base_time + timedelta(days=i * 10, hours=draw(st.integers(0, 23)))

        u_cost = draw(st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("50000.0000"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        ))

        orig_qty = draw(st.decimals(
            min_value=Decimal("1.0000"),
            max_value=Decimal("10000.0000"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        ))

        layers.append({
            "spare_part_id": sp_id,
            "location_id": loc_id,
            "unit_cost": u_cost,
            "original_quantity": orig_qty,
            "remaining_quantity": orig_qty,  # Full layers for FIFO testing
            "source_type": "purchase",
            "source_reference_id": draw(uuids),
            "created_at": layer_time,
        })

    # Ensure chronological order
    layers.sort(key=lambda x: x["created_at"])
    return layers


# =============================================================================
# Credit Entry Strategies
# =============================================================================

@st.composite
def credit_entries(draw, customer_id=None):
    """Generate a valid customer credit ledger entry data dictionary.

    Generates entries matching CustomerCreditLedger model constraints:
    - transaction_type is one of SALE, PAYMENT, ADJUSTMENT, RETURN
    - amount follows sign convention: positive for debits, negative for credits
    - reference_type matches transaction_type context

    Args:
        customer_id: Optional fixed customer_id. Generates one if None.

    Returns:
        Dictionary with credit ledger entry field values.
    """
    cust_id = customer_id or draw(uuids)
    tx_type = draw(st.sampled_from(["SALE", "PAYMENT", "ADJUSTMENT", "RETURN"]))

    # Amount sign convention: SALE = positive (debit), others = negative (credit)
    if tx_type == "SALE":
        amount = draw(st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("1000000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ))
    else:
        amount = draw(st.decimals(
            min_value=Decimal("-1000000.00"),
            max_value=Decimal("-0.01"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ))

    # Reference type maps to transaction type
    ref_type_map = {
        "SALE": "sale",
        "PAYMENT": "payment",
        "ADJUSTMENT": "adjustment",
        "RETURN": "return",
    }

    return {
        "customer_id": cust_id,
        "transaction_type": tx_type,
        "amount": amount,
        "reference_type": ref_type_map[tx_type],
        "reference_id": draw(uuids),
        "notes": draw(st.one_of(st.none(), st.text(min_size=1, max_size=200))),
        "created_by": draw(uuids),
        "created_at": draw(timestamps),
    }


@st.composite
def credit_entry_sequences(draw, customer_id=None, min_size=1, max_size=20):
    """Generate a sequence of credit entries for a single customer.

    Ensures entries are chronologically ordered and represent a realistic
    transaction history.

    Args:
        customer_id: Fixed customer_id for all entries.
        min_size: Minimum number of entries.
        max_size: Maximum number of entries.

    Returns:
        List of credit entry dictionaries ordered by created_at.
    """
    cust_id = customer_id or draw(uuids)
    n = draw(st.integers(min_value=min_size, max_value=max_size))

    entries = []
    base_time = datetime.now(timezone.utc) - timedelta(days=365)

    for i in range(n):
        entry = draw(credit_entries(customer_id=cust_id))
        entry["created_at"] = base_time + timedelta(days=i, hours=draw(st.integers(0, 23)))
        entries.append(entry)

    entries.sort(key=lambda x: x["created_at"])
    return entries


# =============================================================================
# Password Strategies
# =============================================================================

@st.composite
def valid_passwords(draw):
    """Generate passwords that meet complexity requirements.

    Requirements (Requirement 2.5):
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit

    Returns:
        A string that passes password complexity validation.
    """
    # Ensure minimum requirements are met
    uppercase = draw(st.text(
        alphabet=string.ascii_uppercase,
        min_size=1,
        max_size=3,
    ))
    lowercase = draw(st.text(
        alphabet=string.ascii_lowercase,
        min_size=1,
        max_size=3,
    ))
    digits = draw(st.text(
        alphabet=string.digits,
        min_size=1,
        max_size=3,
    ))

    # Fill remaining characters to reach at least 8 total
    remaining_needed = max(0, 8 - len(uppercase) - len(lowercase) - len(digits))
    filler = draw(st.text(
        alphabet=string.ascii_letters + string.digits,
        min_size=remaining_needed,
        max_size=remaining_needed + 8,
    ))

    # Combine and shuffle
    password_chars = list(uppercase + lowercase + digits + filler)
    # Use hypothesis to shuffle
    shuffled = draw(st.permutations(password_chars))
    return "".join(shuffled)


@st.composite
def invalid_passwords(draw):
    """Generate passwords that fail at least one complexity requirement.

    Returns a tuple of (password, failure_reason) where failure_reason indicates
    which check the password fails.
    """
    failure_type = draw(st.sampled_from([
        "too_short",
        "no_uppercase",
        "no_lowercase",
        "no_digit",
    ]))

    if failure_type == "too_short":
        # 1-7 characters, may still have uppercase/lowercase/digit
        password = draw(st.text(
            alphabet=string.ascii_letters + string.digits,
            min_size=1,
            max_size=7,
        ))
        return (password, "too_short")

    elif failure_type == "no_uppercase":
        # At least 8 chars, only lowercase + digits
        password = draw(st.text(
            alphabet=string.ascii_lowercase + string.digits,
            min_size=8,
            max_size=20,
        ))
        # Ensure it actually has lowercase and digit
        password = password[:6] + "a" + "1" + password[8:]
        return (password[:max(8, len(password))], "no_uppercase")

    elif failure_type == "no_lowercase":
        # At least 8 chars, only uppercase + digits
        password = draw(st.text(
            alphabet=string.ascii_uppercase + string.digits,
            min_size=8,
            max_size=20,
        ))
        password = password[:6] + "A" + "1" + password[8:]
        return (password[:max(8, len(password))], "no_lowercase")

    else:  # no_digit
        # At least 8 chars, only letters (no digits)
        password = draw(st.text(
            alphabet=string.ascii_letters,
            min_size=8,
            max_size=20,
        ))
        # Ensure has both cases
        password = password[:6] + "A" + "a" + password[8:]
        return (password[:max(8, len(password))], "no_digit")


# =============================================================================
# Sale Line Item Strategies
# =============================================================================

@st.composite
def sale_line_items(draw, spare_part_id=None):
    """Generate valid sale line item data dictionaries.

    Generates sale line items matching SaleItem model constraints:
    - quantity is positive (precision 12, scale 2)
    - unit_price is positive (precision 12, scale 2)
    - discount_amount is non-negative and <= quantity * unit_price
    - line_total = (quantity * unit_price) - discount_amount

    Args:
        spare_part_id: Optional fixed spare_part_id.

    Returns:
        Dictionary with sale line item field values including calculated line_total.
    """
    sp_id = spare_part_id or draw(uuids)

    quantity = draw(st.decimals(
        min_value=Decimal("1.00"),
        max_value=Decimal("1000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))

    unit_price = draw(st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))

    gross_amount = quantity * unit_price

    # Discount must not exceed gross amount
    max_discount = min(gross_amount, Decimal("999999.99"))
    discount_amount = draw(st.decimals(
        min_value=Decimal("0.00"),
        max_value=max_discount,
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ))

    line_total = (quantity * unit_price) - discount_amount

    return {
        "spare_part_id": sp_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "discount_amount": discount_amount,
        "line_total": line_total,
    }


@st.composite
def sale_line_item_lists(draw, min_size=1, max_size=10):
    """Generate a list of sale line items for a single sale.

    Args:
        min_size: Minimum number of items.
        max_size: Maximum number of items.

    Returns:
        List of sale line item dictionaries.
    """
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    items = []
    for _ in range(n):
        item = draw(sale_line_items())
        items.append(item)
    return items


# =============================================================================
# Transfer Data Strategies
# =============================================================================

@st.composite
def transfer_data(draw):
    """Generate valid transfer request data dictionaries.

    Generates transfer data matching Transfer model constraints:
    - source_location and dest_location are different UUIDs
    - quantity is positive (precision 15, scale 4)

    Returns:
        Dictionary with transfer field values.
    """
    source_location = draw(uuids)
    dest_location = draw(uuids.filter(lambda x: x != source_location))

    quantity = draw(st.decimals(
        min_value=Decimal("0.0001"),
        max_value=Decimal("100000.0000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ))

    return {
        "spare_part_id": draw(uuids),
        "source_location_id": source_location,
        "destination_location_id": dest_location,
        "quantity": quantity,
        "requested_by": draw(uuids),
    }


@st.composite
def transfer_with_stock(draw, available_stock=None):
    """Generate transfer data along with sufficient source stock.

    Useful for testing transfers where we need to ensure the source has
    enough stock to fulfill the transfer.

    Args:
        available_stock: Optional fixed available stock quantity.
            If None, generates stock >= transfer quantity.

    Returns:
        Dictionary with transfer data and source stock information.
    """
    transfer = draw(transfer_data())

    if available_stock is not None:
        stock = available_stock
    else:
        # Ensure stock is at least as much as the transfer quantity
        extra = draw(st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("10000"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        ))
        stock = transfer["quantity"] + extra

    return {
        **transfer,
        "available_stock": stock,
    }
