"""Barcode generation utility using python-barcode library.

Generates Code 128 barcodes in SVG and PNG formats for spare parts.
Supports both manufacturer-provided barcodes and system-generated barcodes.

Satisfies Requirements:
- 10.1: Generate unique system barcodes for parts without manufacturer barcode
- 10.4: Generate barcode labels in printable format (standard label sizes)
- 10.5: Encode system-generated barcodes in Code 128 format
"""

import io
import uuid
from typing import Optional

import barcode
from barcode.writer import SVGWriter


class BarcodeGenerationError(Exception):
    """Raised when barcode generation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


def generate_system_barcode_value(part_number: str) -> str:
    """Generate a unique system barcode value for a spare part.

    Creates a barcode string based on the part number with a prefix
    to distinguish system-generated barcodes from manufacturer barcodes.

    The format is: ASM-{part_number_normalized}-{short_uuid}
    where short_uuid provides uniqueness guarantee.

    Args:
        part_number: The spare part's part number.

    Returns:
        A unique barcode string suitable for Code 128 encoding.

    Satisfies Requirement 10.1: Generate unique system barcodes for parts
    without manufacturer barcode.
    """
    # Normalize part number: uppercase, remove special chars that aren't alphanumeric
    normalized = "".join(c for c in part_number.upper() if c.isalnum())
    # Add short UUID suffix for uniqueness
    short_id = uuid.uuid4().hex[:8].upper()
    return f"ASM-{normalized}-{short_id}"


def generate_barcode_svg(barcode_value: str, include_text: bool = True) -> bytes:
    """Generate a Code 128 barcode as SVG bytes.

    Args:
        barcode_value: The string to encode in the barcode.
        include_text: Whether to include human-readable text below the barcode.

    Returns:
        SVG content as bytes.

    Raises:
        BarcodeGenerationError: If the barcode value cannot be encoded.

    Satisfies Requirements:
    - 10.4: Generate barcode labels in printable format
    - 10.5: Encode system-generated barcodes in Code 128 format
    """
    try:
        code128 = barcode.get_barcode_class("code128")
        writer = SVGWriter()

        # Configure writer options for standard label sizes
        writer_options = {
            "module_width": 0.2,  # mm per module
            "module_height": 15.0,  # mm barcode height
            "quiet_zone": 6.5,  # mm quiet zone
            "font_size": 10,  # pt font size for text
            "text_distance": 5.0,  # mm distance from barcode to text
            "write_text": include_text,
        }

        barcode_instance = code128(barcode_value, writer=writer)

        # Write to bytes buffer
        buffer = io.BytesIO()
        barcode_instance.write(buffer, options=writer_options)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        raise BarcodeGenerationError(
            f"Failed to generate barcode for value '{barcode_value}': {str(e)}"
        )


def generate_barcode_png(barcode_value: str, include_text: bool = True) -> bytes:
    """Generate a Code 128 barcode as PNG bytes.

    Requires Pillow to be installed for PNG generation.

    Args:
        barcode_value: The string to encode in the barcode.
        include_text: Whether to include human-readable text below the barcode.

    Returns:
        PNG content as bytes.

    Raises:
        BarcodeGenerationError: If the barcode value cannot be encoded or
            Pillow is not available.

    Satisfies Requirements:
    - 10.4: Generate barcode labels in printable format
    - 10.5: Encode system-generated barcodes in Code 128 format
    """
    try:
        from barcode.writer import ImageWriter

        code128 = barcode.get_barcode_class("code128")
        writer = ImageWriter()

        # Configure writer options for standard label sizes
        writer_options = {
            "module_width": 0.2,  # mm per module
            "module_height": 15.0,  # mm barcode height
            "quiet_zone": 6.5,  # mm quiet zone
            "font_size": 10,  # pt font size for text
            "text_distance": 5.0,  # mm distance from barcode to text
            "write_text": include_text,
            "dpi": 300,  # High DPI for print quality
        }

        barcode_instance = code128(barcode_value, writer=writer)

        # Write to bytes buffer
        buffer = io.BytesIO()
        barcode_instance.write(buffer, options=writer_options)
        buffer.seek(0)
        return buffer.getvalue()
    except ImportError:
        raise BarcodeGenerationError(
            "Pillow is required for PNG barcode generation. Install with: pip install Pillow"
        )
    except Exception as e:
        raise BarcodeGenerationError(
            f"Failed to generate PNG barcode for value '{barcode_value}': {str(e)}"
        )


def decode_barcode_value(barcode_value: str) -> dict:
    """Decode a barcode value and extract metadata.

    Determines if a barcode is system-generated (ASM- prefix) or
    manufacturer-provided, and extracts relevant components.

    Args:
        barcode_value: The barcode string to decode.

    Returns:
        Dictionary with decoded barcode metadata:
        - type: "system" or "manufacturer"
        - value: The raw barcode value
        - part_number_hint: Extracted part number (for system barcodes)

    Satisfies Requirement 10.2: Support storing both manufacturer and
    system-generated barcodes.
    """
    result = {
        "value": barcode_value,
        "type": "manufacturer",
        "part_number_hint": None,
    }

    if barcode_value.startswith("ASM-"):
        result["type"] = "system"
        # Extract the part number portion (between first and last dash segments)
        parts = barcode_value.split("-")
        if len(parts) >= 3:
            # Part number is everything between ASM- and the last segment (UUID)
            result["part_number_hint"] = "-".join(parts[1:-1])

    return result


def validate_barcode_value(barcode_value: str) -> bool:
    """Validate that a barcode value can be encoded as Code 128.

    Code 128 supports ASCII characters 0-127, so this checks that
    all characters in the value are within that range and the value
    is not empty.

    Args:
        barcode_value: The barcode string to validate.

    Returns:
        True if the value is valid for Code 128 encoding.
    """
    if not barcode_value or len(barcode_value) == 0:
        return False

    # Code 128 supports full ASCII (0-127)
    for char in barcode_value:
        if ord(char) > 127:
            return False

    return True
