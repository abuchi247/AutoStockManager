"""Unit tests for the barcode service and barcode generator utility.

Tests cover:
- System barcode value generation
- Barcode SVG generation (Code 128)
- Barcode value decoding (system vs manufacturer)
- Barcode validation
- Barcode service: generate for part, lookup, assign

Satisfies Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.barcode_service import (
    BarcodeAlreadyExistsError,
    BarcodeNotFoundError,
    BarcodeService,
    InvalidBarcodeError,
    SparePartNotFoundError,
)
from app.utils.barcode_generator import (
    BarcodeGenerationError,
    decode_barcode_value,
    generate_barcode_svg,
    generate_system_barcode_value,
    validate_barcode_value,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_execute_result(scalar_value=None):
    """Create a mock result object that mimics SQLAlchemy's execute result."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    return result


def _make_mock_spare_part(
    part_number="SP-001",
    barcode=None,
    name="Brake Pad Set",
    spare_part_id=None,
):
    """Helper to create a mock SparePart object."""
    mock_part = MagicMock()
    mock_part.id = spare_part_id or uuid.uuid4()
    mock_part.part_number = part_number
    mock_part.barcode = barcode
    mock_part.name = name
    mock_part.brand = "Bosch"
    mock_part.selling_price = 45.00
    mock_part.unit_of_measure = "PCS"
    mock_part.deleted_at = None
    return mock_part


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def barcode_service(mock_db):
    """Create a BarcodeService with a mock database session."""
    return BarcodeService(db=mock_db)


# =============================================================================
# Barcode Generator Utility Tests
# =============================================================================


class TestGenerateSystemBarcodeValue:
    """Tests for generate_system_barcode_value."""

    def test_generates_value_with_asm_prefix(self):
        """System barcodes should start with ASM- prefix."""
        value = generate_system_barcode_value("SP-001")
        assert value.startswith("ASM-")

    def test_includes_normalized_part_number(self):
        """System barcodes should include the normalized part number."""
        value = generate_system_barcode_value("SP-001")
        # Part number normalized: SP-001 -> SP001
        assert "SP001" in value

    def test_generates_unique_values(self):
        """Each call should produce a unique barcode value."""
        values = {generate_system_barcode_value("SP-001") for _ in range(100)}
        assert len(values) == 100

    def test_handles_special_characters_in_part_number(self):
        """Special characters in part number should be removed."""
        value = generate_system_barcode_value("SP/001-ABC.123")
        assert value.startswith("ASM-")
        # Only alphanumeric chars kept
        assert "SP001ABC123" in value

    def test_handles_empty_part_number(self):
        """Empty part number should still generate a valid barcode."""
        value = generate_system_barcode_value("")
        assert value.startswith("ASM-")


class TestGenerateBarcodeSvg:
    """Tests for generate_barcode_svg."""

    def test_generates_valid_svg(self):
        """Should generate SVG content bytes."""
        svg_bytes = generate_barcode_svg("TEST123")
        assert svg_bytes is not None
        assert len(svg_bytes) > 0
        # SVG should contain XML/SVG markers
        svg_str = svg_bytes.decode("utf-8")
        assert "svg" in svg_str.lower()

    def test_generates_svg_with_text(self):
        """SVG should include the barcode text when include_text=True."""
        svg_bytes = generate_barcode_svg("HELLO123", include_text=True)
        svg_str = svg_bytes.decode("utf-8")
        assert "HELLO123" in svg_str

    def test_generates_svg_without_text(self):
        """SVG should not include barcode text when include_text=False."""
        svg_bytes = generate_barcode_svg("HELLO123", include_text=False)
        # The barcode is still generated, just no text
        assert svg_bytes is not None
        assert len(svg_bytes) > 0

    def test_handles_alphanumeric_values(self):
        """Should handle various alphanumeric barcode values."""
        for value in ["ABC123", "SP-001-BRAKE", "ASM-TEST-12345678"]:
            svg_bytes = generate_barcode_svg(value)
            assert svg_bytes is not None
            assert len(svg_bytes) > 0


class TestDecodeBarcodeValue:
    """Tests for decode_barcode_value."""

    def test_decode_system_barcode(self):
        """System barcodes (ASM- prefix) should be identified correctly."""
        result = decode_barcode_value("ASM-SP001-ABCD1234")
        assert result["type"] == "system"
        assert result["value"] == "ASM-SP001-ABCD1234"
        assert result["part_number_hint"] == "SP001"

    def test_decode_manufacturer_barcode(self):
        """Non-ASM barcodes should be identified as manufacturer."""
        result = decode_barcode_value("8901234567890")
        assert result["type"] == "manufacturer"
        assert result["value"] == "8901234567890"
        assert result["part_number_hint"] is None

    def test_decode_system_barcode_with_complex_part_number(self):
        """System barcodes with complex part numbers should decode correctly."""
        result = decode_barcode_value("ASM-SP001ABC123-DEADBEEF")
        assert result["type"] == "system"
        assert result["part_number_hint"] == "SP001ABC123"

    def test_decode_empty_string(self):
        """Empty string should be treated as manufacturer type."""
        result = decode_barcode_value("")
        assert result["type"] == "manufacturer"


class TestValidateBarcodeValue:
    """Tests for validate_barcode_value."""

    def test_valid_ascii_values(self):
        """Standard ASCII values should be valid."""
        assert validate_barcode_value("ABC123") is True
        assert validate_barcode_value("SP-001-BRAKE") is True
        assert validate_barcode_value("8901234567890") is True

    def test_empty_string_invalid(self):
        """Empty string should be invalid."""
        assert validate_barcode_value("") is False

    def test_non_ascii_invalid(self):
        """Non-ASCII characters should be invalid for Code 128."""
        assert validate_barcode_value("café") is False
        assert validate_barcode_value("日本語") is False

    def test_special_ascii_chars_valid(self):
        """Special ASCII characters within range should be valid."""
        assert validate_barcode_value("!@#$%^&*()") is True
        assert validate_barcode_value("test value with spaces") is True


# =============================================================================
# Barcode Service Tests
# =============================================================================


class TestBarcodeServiceGenerateForPart:
    """Tests for BarcodeService.generate_barcode_for_part."""

    @pytest.mark.asyncio
    async def test_generate_barcode_success(self, barcode_service, mock_db):
        """Should generate and assign a barcode to a part without one."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(
            part_number="SP-001", barcode=None, spare_part_id=spare_part_id
        )

        # Calls: _get_spare_part, _barcode_exists
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=mock_part),  # get spare part
                _make_execute_result(scalar_value=None),  # barcode doesn't exist
            ]
        )

        result = await barcode_service.generate_barcode_for_part(spare_part_id)
        assert result.startswith("ASM-")
        assert "SP001" in result
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_generate_barcode_already_exists_raises(self, barcode_service, mock_db):
        """Should raise error if part already has a barcode and overwrite=False."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(
            part_number="SP-001", barcode="EXISTING-BARCODE"
        )

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=mock_part)
        )

        with pytest.raises(BarcodeAlreadyExistsError):
            await barcode_service.generate_barcode_for_part(spare_part_id)

    @pytest.mark.asyncio
    async def test_generate_barcode_overwrite(self, barcode_service, mock_db):
        """Should replace existing barcode when overwrite=True."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(
            part_number="SP-001", barcode="OLD-BARCODE", spare_part_id=spare_part_id
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=mock_part),  # get spare part
                _make_execute_result(scalar_value=None),  # new barcode doesn't exist
            ]
        )

        result = await barcode_service.generate_barcode_for_part(
            spare_part_id, overwrite=True
        )
        assert result.startswith("ASM-")
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_generate_barcode_part_not_found(self, barcode_service, mock_db):
        """Should raise error if spare part doesn't exist."""
        spare_part_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        with pytest.raises(SparePartNotFoundError):
            await barcode_service.generate_barcode_for_part(spare_part_id)


class TestBarcodeServiceLookup:
    """Tests for BarcodeService.lookup_by_barcode."""

    @pytest.mark.asyncio
    async def test_lookup_success(self, barcode_service, mock_db):
        """Should return the spare part matching the barcode."""
        mock_part = _make_mock_spare_part(barcode="8901234567890")

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=mock_part)
        )

        result = await barcode_service.lookup_by_barcode("8901234567890")
        assert result == mock_part

    @pytest.mark.asyncio
    async def test_lookup_not_found(self, barcode_service, mock_db):
        """Should raise error if no part matches the barcode."""
        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        with pytest.raises(BarcodeNotFoundError):
            await barcode_service.lookup_by_barcode("NONEXISTENT")


class TestBarcodeServiceDecode:
    """Tests for BarcodeService.decode_barcode."""

    def test_decode_system_barcode(self, barcode_service):
        """Should identify system barcodes."""
        result = barcode_service.decode_barcode("ASM-SP001-ABCD1234")
        assert result["type"] == "system"
        assert result["part_number_hint"] == "SP001"

    def test_decode_manufacturer_barcode(self, barcode_service):
        """Should identify manufacturer barcodes."""
        result = barcode_service.decode_barcode("8901234567890")
        assert result["type"] == "manufacturer"


class TestBarcodeServiceAssignManufacturer:
    """Tests for BarcodeService.assign_manufacturer_barcode."""

    @pytest.mark.asyncio
    async def test_assign_success(self, barcode_service, mock_db):
        """Should assign manufacturer barcode to a part."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(
            part_number="SP-001", barcode=None, spare_part_id=spare_part_id
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=mock_part),  # get spare part
                _make_execute_result(scalar_value=None),  # barcode not in use
            ]
        )

        result = await barcode_service.assign_manufacturer_barcode(
            spare_part_id, "8901234567890"
        )
        assert result == "8901234567890"
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_assign_invalid_barcode(self, barcode_service, mock_db):
        """Should raise error for invalid barcode value."""
        spare_part_id = uuid.uuid4()

        with pytest.raises(InvalidBarcodeError):
            await barcode_service.assign_manufacturer_barcode(spare_part_id, "")

    @pytest.mark.asyncio
    async def test_assign_barcode_already_used(self, barcode_service, mock_db):
        """Should raise error if barcode already used by another part."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(spare_part_id=spare_part_id)

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(scalar_value=mock_part),  # get spare part
                _make_execute_result(scalar_value=uuid.uuid4()),  # barcode in use
            ]
        )

        with pytest.raises(BarcodeAlreadyExistsError):
            await barcode_service.assign_manufacturer_barcode(
                spare_part_id, "8901234567890"
            )

    @pytest.mark.asyncio
    async def test_assign_part_not_found(self, barcode_service, mock_db):
        """Should raise error if spare part doesn't exist."""
        spare_part_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        with pytest.raises(SparePartNotFoundError):
            await barcode_service.assign_manufacturer_barcode(
                spare_part_id, "8901234567890"
            )


class TestBarcodeServiceGetImage:
    """Tests for BarcodeService.get_barcode_image."""

    @pytest.mark.asyncio
    async def test_get_image_svg_with_existing_barcode(self, barcode_service, mock_db):
        """Should return SVG image for part with existing barcode."""
        spare_part_id = uuid.uuid4()
        mock_part = _make_mock_spare_part(
            barcode="TEST123", spare_part_id=spare_part_id
        )

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=mock_part)
        )

        image_bytes, content_type = await barcode_service.get_barcode_image(
            spare_part_id, format="svg"
        )
        assert content_type == "image/svg+xml"
        assert len(image_bytes) > 0
        assert b"svg" in image_bytes.lower()

    @pytest.mark.asyncio
    async def test_get_image_part_not_found(self, barcode_service, mock_db):
        """Should raise error if spare part doesn't exist."""
        spare_part_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(scalar_value=None)
        )

        with pytest.raises(SparePartNotFoundError):
            await barcode_service.get_barcode_image(spare_part_id)
