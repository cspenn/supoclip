"""Unit tests for FontService.

Tests the font detection, validation, caching, and management service.
Covers all methods and branches for 100% line coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path
import hashlib

from src.services.font_service import (
    FontMetadata,
    FontNameExtractor,
    FontWeightExtractor,
    FontService,
)


# --- FontNameExtractor Tests ---

class TestFontNameExtractor:
    """Test FontNameExtractor static methods."""

    def test_extract_from_name_table_found(self):
        """Test extracting a name that exists in the table."""
        mock_record = MagicMock()
        mock_record.nameID = 1
        mock_record.toUnicode.return_value = "Arial"

        mock_name_table = MagicMock()
        mock_name_table.names = [mock_record]

        result = FontNameExtractor.extract_from_name_table(mock_name_table, 1)
        assert result == "Arial"

    def test_extract_from_name_table_not_found(self):
        """Test extracting a name when the nameID doesn't exist."""
        mock_record = MagicMock()
        mock_record.nameID = 2

        mock_name_table = MagicMock()
        mock_name_table.names = [mock_record]

        result = FontNameExtractor.extract_from_name_table(mock_name_table, 1)
        assert result is None

    def test_extract_from_name_table_decode_error(self):
        """Test handling decode errors in name extraction (lines 57-59)."""
        mock_record = MagicMock()
        mock_record.nameID = 1
        mock_record.toUnicode.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "bad")

        mock_name_table = MagicMock()
        mock_name_table.names = [mock_record]

        result = FontNameExtractor.extract_from_name_table(mock_name_table, 1)
        assert result is None

    def test_extract_all_names(self):
        """Test extracting all font names."""
        mock_name_table = MagicMock()

        records = []
        for name_id, value in [(1, "Arial"), (2, "Bold"), (4, "Arial Bold")]:
            record = MagicMock()
            record.nameID = name_id
            record.toUnicode.return_value = value
            records.append(record)
        mock_name_table.names = records

        result = FontNameExtractor.extract_all_names(mock_name_table)
        assert result["family"] == "Arial"
        assert result["style"] == "Bold"
        assert result["full_name"] == "Arial Bold"


# --- FontWeightExtractor Tests ---

class TestFontWeightExtractor:
    """Test FontWeightExtractor static methods."""

    def test_extract_weight_with_os2_table(self):
        """Test extracting weight when OS/2 table exists."""
        mock_font = MagicMock()
        mock_font.__contains__ = MagicMock(return_value=True)
        mock_font.__getitem__ = MagicMock(return_value=MagicMock(usWeightClass=700))

        result = FontWeightExtractor.extract_weight(mock_font)
        assert result == 700

    def test_extract_weight_without_os2_table(self):
        """Test extracting weight when OS/2 table is absent."""
        mock_font = MagicMock()
        mock_font.__contains__ = MagicMock(return_value=False)

        result = FontWeightExtractor.extract_weight(mock_font)
        assert result is None


# --- FontService Tests ---

@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    return AsyncMock()


@pytest.fixture
def font_service(mock_db_session, tmp_path):
    """Create a FontService instance for testing."""
    service = FontService(db_session=mock_db_session, temp_dir=tmp_path)
    return service


@pytest.fixture
def font_service_no_db(tmp_path):
    """Create a FontService without a database session."""
    return FontService(db_session=None, temp_dir=tmp_path)


class TestFontServiceInit:
    """Test FontService initialization."""

    def test_init_stores_db_session_and_temp_dir(self, mock_db_session, tmp_path):
        """Test that __init__ stores parameters."""
        service = FontService(db_session=mock_db_session, temp_dir=tmp_path)
        assert service.db_session is mock_db_session
        assert service.temp_dir == tmp_path


class TestGetBundledFonts:
    """Test get_bundled_fonts method."""

    @pytest.mark.asyncio
    async def test_get_bundled_fonts_directory_not_exists(self, font_service, tmp_path):
        """Test when bundled fonts directory doesn't exist (line 123-127)."""
        font_service.bundled_fonts_dir = tmp_path / "nonexistent"
        result = await font_service.get_bundled_fonts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_bundled_fonts_empty_directory(self, font_service, tmp_path):
        """Test with an empty fonts directory."""
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        font_service.bundled_fonts_dir = fonts_dir

        result = await font_service.get_bundled_fonts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_bundled_fonts_with_valid_fonts(self, font_service, tmp_path):
        """Test with valid font files (lines 140-152)."""
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        font_file = fonts_dir / "TestFont.ttf"
        font_file.write_bytes(b"fake font data")
        font_service.bundled_fonts_dir = fonts_dir

        expected_metadata = FontMetadata(name="TestFont", family="TestFont", source="bundled")
        font_service.validate_font = AsyncMock(return_value=True)
        font_service.extract_font_metadata = AsyncMock(return_value=expected_metadata)

        result = await font_service.get_bundled_fonts()
        assert len(result) == 1
        assert result[0].name == "TestFont"
        assert result[0].source == "bundled"

    @pytest.mark.asyncio
    async def test_get_bundled_fonts_invalid_font_skipped(self, font_service, tmp_path):
        """Test that invalid fonts are skipped (line 144-145)."""
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        font_file = fonts_dir / "Bad.ttf"
        font_file.write_bytes(b"bad font")
        font_service.bundled_fonts_dir = fonts_dir

        font_service.validate_font = AsyncMock(return_value=False)

        result = await font_service.get_bundled_fonts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_bundled_fonts_metadata_extraction_fails(self, font_service, tmp_path):
        """Test when metadata extraction returns None."""
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        font_file = fonts_dir / "NoMeta.ttf"
        font_file.write_bytes(b"font data")
        font_service.bundled_fonts_dir = fonts_dir

        font_service.validate_font = AsyncMock(return_value=True)
        font_service.extract_font_metadata = AsyncMock(return_value=None)

        result = await font_service.get_bundled_fonts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_bundled_fonts_exception_during_processing(self, font_service, tmp_path):
        """Test exception handling during font processing (lines 154-155)."""
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        font_file = fonts_dir / "Boom.ttf"
        font_file.write_bytes(b"font data")
        font_service.bundled_fonts_dir = fonts_dir

        font_service.validate_font = AsyncMock(side_effect=RuntimeError("boom"))

        result = await font_service.get_bundled_fonts()
        assert result == []


class TestDetectSystemFonts:
    """Test detect_system_fonts method."""

    @pytest.mark.asyncio
    async def test_detect_system_fonts_success(self, font_service, tmp_path):
        """Test successful system font detection (lines 183-193)."""
        font_file = tmp_path / "SystemFont.ttf"
        font_file.write_bytes(b"system font data")

        with patch("src.services.font_service.fm.findSystemFonts", return_value=[str(font_file)]):
            font_service.validate_font = AsyncMock(return_value=True)
            expected_meta = FontMetadata(name="SystemFont", family="SystemFont")
            font_service.extract_font_metadata = AsyncMock(return_value=expected_meta)

            result = await font_service.detect_system_fonts()
            assert len(result) == 1
            assert result[0].source == "system"

    @pytest.mark.asyncio
    async def test_detect_system_fonts_nonexistent_path_skipped(self, font_service):
        """Test that non-existent font paths are skipped (line 182-183)."""
        with patch("src.services.font_service.fm.findSystemFonts",
                    return_value=["/nonexistent/path/Font.ttf"]):
            result = await font_service.detect_system_fonts()
            assert result == []

    @pytest.mark.asyncio
    async def test_detect_system_fonts_invalid_font_skipped(self, font_service, tmp_path):
        """Test that invalid fonts are skipped during system detection."""
        font_file = tmp_path / "Invalid.ttf"
        font_file.write_bytes(b"data")

        with patch("src.services.font_service.fm.findSystemFonts", return_value=[str(font_file)]):
            font_service.validate_font = AsyncMock(return_value=False)
            result = await font_service.detect_system_fonts()
            assert result == []

    @pytest.mark.asyncio
    async def test_detect_system_fonts_metadata_extraction_returns_none(self, font_service, tmp_path):
        """Test when metadata extraction returns None for a system font."""
        font_file = tmp_path / "NoMeta.ttf"
        font_file.write_bytes(b"data")

        with patch("src.services.font_service.fm.findSystemFonts", return_value=[str(font_file)]):
            font_service.validate_font = AsyncMock(return_value=True)
            font_service.extract_font_metadata = AsyncMock(return_value=None)
            result = await font_service.detect_system_fonts()
            assert result == []

    @pytest.mark.asyncio
    async def test_detect_system_fonts_per_font_exception(self, font_service, tmp_path):
        """Test exception handling for individual font processing (lines 195-198)."""
        font_file = tmp_path / "Error.ttf"
        font_file.write_bytes(b"data")

        with patch("src.services.font_service.fm.findSystemFonts", return_value=[str(font_file)]):
            font_service.validate_font = AsyncMock(side_effect=RuntimeError("per font error"))
            result = await font_service.detect_system_fonts()
            assert result == []

    @pytest.mark.asyncio
    async def test_detect_system_fonts_global_exception(self, font_service):
        """Test global exception handling in detect_system_fonts (lines 202-203)."""
        with patch("src.services.font_service.fm.findSystemFonts",
                    side_effect=RuntimeError("global error")):
            result = await font_service.detect_system_fonts()
            assert result == []


class TestExtractFontMetadata:
    """Test extract_font_metadata method."""

    @pytest.mark.asyncio
    async def test_extract_font_metadata_success(self, font_service, tmp_path):
        """Test successful metadata extraction."""
        font_file = tmp_path / "Good.ttf"
        font_file.write_bytes(b"font content")

        mock_font = MagicMock()
        mock_name_table = MagicMock()
        # Setup name records
        records = []
        for name_id, value in [(1, "GoodFamily"), (2, "Regular"), (4, "Good Font")]:
            rec = MagicMock()
            rec.nameID = name_id
            rec.toUnicode.return_value = value
            records.append(rec)
        mock_name_table.names = records
        mock_font.__getitem__ = MagicMock(side_effect=lambda key: {
            "name": mock_name_table,
            "OS/2": MagicMock(usWeightClass=400)
        }[key])
        mock_font.__contains__ = MagicMock(return_value=True)

        with patch("src.services.font_service.TTFont", return_value=mock_font):
            font_service.compute_file_hash = AsyncMock(return_value="abc123hash")
            result = await font_service.extract_font_metadata(font_file)

        assert result is not None
        assert result.name == "Good Font"
        assert result.family == "GoodFamily"
        assert result.style == "Regular"
        assert result.weight == 400
        assert result.file_hash == "abc123hash"
        assert result.is_valid is True
        mock_font.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_font_metadata_no_full_name(self, font_service, tmp_path):
        """Test metadata extraction when full_name is None, falls back to stem."""
        font_file = tmp_path / "StemName.ttf"
        font_file.write_bytes(b"font content")

        mock_font = MagicMock()
        mock_name_table = MagicMock()
        records = []
        for name_id, value in [(1, "FamilyOnly"), (2, "Bold")]:
            rec = MagicMock()
            rec.nameID = name_id
            rec.toUnicode.return_value = value
            records.append(rec)
        mock_name_table.names = records
        mock_font.__getitem__ = MagicMock(side_effect=lambda key: {
            "name": mock_name_table,
        }.get(key))
        mock_font.__contains__ = MagicMock(return_value=False)

        with patch("src.services.font_service.TTFont", return_value=mock_font):
            font_service.compute_file_hash = AsyncMock(return_value="hash456")
            result = await font_service.extract_font_metadata(font_file)

        assert result is not None
        assert result.name == "StemName"  # Falls back to file stem

    @pytest.mark.asyncio
    async def test_extract_font_metadata_no_family(self, font_service, tmp_path):
        """Test metadata extraction when family is None, falls back to name."""
        font_file = tmp_path / "NoFamily.ttf"
        font_file.write_bytes(b"data")

        mock_font = MagicMock()
        mock_name_table = MagicMock()
        rec = MagicMock()
        rec.nameID = 4
        rec.toUnicode.return_value = "FullNameOnly"
        mock_name_table.names = [rec]
        mock_font.__getitem__ = MagicMock(side_effect=lambda key: {
            "name": mock_name_table,
        }.get(key))
        mock_font.__contains__ = MagicMock(return_value=False)

        with patch("src.services.font_service.TTFont", return_value=mock_font):
            font_service.compute_file_hash = AsyncMock(return_value="hash")
            result = await font_service.extract_font_metadata(font_file)

        assert result is not None
        assert result.family == "FullNameOnly"

    @pytest.mark.asyncio
    async def test_extract_font_metadata_exception(self, font_service, tmp_path):
        """Test metadata extraction failure returns None (lines 254-256)."""
        font_file = tmp_path / "Broken.ttf"
        font_file.write_bytes(b"bad data")

        with patch("src.services.font_service.TTFont", side_effect=RuntimeError("parse error")):
            result = await font_service.extract_font_metadata(font_file)
        assert result is None


class TestValidateFont:
    """Test validate_font method."""

    @pytest.mark.asyncio
    async def test_validate_font_file_not_found(self, font_service, tmp_path):
        """Test validation when file doesn't exist (lines 273-275)."""
        result = await font_service.validate_font(tmp_path / "nonexistent.ttf")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_font_empty_file(self, font_service, tmp_path):
        """Test validation when file is empty (lines 278-280)."""
        empty_file = tmp_path / "empty.ttf"
        empty_file.write_bytes(b"")
        result = await font_service.validate_font(empty_file)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_font_load_failure(self, font_service, tmp_path):
        """Test validation when font loading fails (lines 284-287)."""
        font_file = tmp_path / "bad.ttf"
        font_file.write_bytes(b"not a font")

        with patch("src.services.font_service.TTFont", side_effect=Exception("load error")):
            result = await font_service.validate_font(font_file)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_font_missing_required_table(self, font_service, tmp_path):
        """Test validation when required tables are missing (lines 299-304)."""
        font_file = tmp_path / "missing_tables.ttf"
        font_file.write_bytes(b"some data")

        mock_font = MagicMock()
        # Only has "head" and "hhea", missing "maxp", "hmtx", "cmap"
        mock_font.__contains__ = MagicMock(side_effect=lambda key: key in {"head", "hhea"})

        with patch("src.services.font_service.TTFont", return_value=mock_font):
            result = await font_service.validate_font(font_file)
        assert result is False
        mock_font.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_font_all_required_tables(self, font_service, tmp_path):
        """Test validation when all required tables are present (lines 309-312)."""
        font_file = tmp_path / "valid.ttf"
        font_file.write_bytes(b"valid font data")

        mock_font = MagicMock()
        required_tables = {"head", "hhea", "maxp", "hmtx", "cmap"}
        mock_font.__contains__ = MagicMock(side_effect=lambda key: key in required_tables)

        with patch("src.services.font_service.TTFont", return_value=mock_font):
            result = await font_service.validate_font(font_file)
        assert result is True
        mock_font.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_font_outer_exception(self, font_service, tmp_path):
        """Test outer exception handling in validate_font (lines 314-316)."""
        font_file = tmp_path / "outer_error.ttf"
        font_file.write_bytes(b"data")

        # Make Path.exists() raise an exception by mocking
        with patch.object(Path, "exists", side_effect=RuntimeError("outer error")):
            result = await font_service.validate_font(font_file)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_font_not_a_file(self, font_service, tmp_path):
        """Test validation when path is a directory, not a file."""
        dir_path = tmp_path / "a_directory"
        dir_path.mkdir()
        result = await font_service.validate_font(dir_path)
        assert result is False


class TestComputeFileHash:
    """Test compute_file_hash method."""

    @pytest.mark.asyncio
    async def test_compute_file_hash_success(self, font_service, tmp_path):
        """Test successful hash computation."""
        test_file = tmp_path / "hashme.ttf"
        test_content = b"hello world font data"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        result = await font_service.compute_file_hash(test_file)
        assert result == expected_hash

    @pytest.mark.asyncio
    async def test_compute_file_hash_exception(self, font_service, tmp_path):
        """Test hash computation failure returns empty string (lines 338-340)."""
        result = await font_service.compute_file_hash(tmp_path / "nonexistent.ttf")
        assert result == ""


class TestCacheFonts:
    """Test cache_fonts method."""

    @pytest.mark.asyncio
    async def test_cache_fonts_no_db_session(self, font_service_no_db):
        """Test cache_fonts without database session (line 350-351)."""
        fonts = [FontMetadata(name="Test")]
        await font_service_no_db.cache_fonts(fonts)
        # Should just return without error

    @pytest.mark.asyncio
    async def test_cache_fonts_empty_list(self, font_service):
        """Test cache_fonts with empty list (lines 353-355)."""
        await font_service.cache_fonts([])
        # Should just return without doing any DB work

    @pytest.mark.asyncio
    async def test_cache_fonts_new_font(self, font_service, mock_db_session):
        """Test caching a brand new font (lines 382-398)."""
        font = FontMetadata(
            name="NewFont",
            family="NewFont",
            style="Regular",
            weight=400,
            file_path="/path/to/font.ttf",
            file_hash="abc123",
            is_valid=True,
            detection_timestamp="2026-01-01T00:00:00",
            metadata_json={"file_size": 1234},
            source="bundled",
        )

        # Mock the query to return no existing font
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        with patch("src.services.font_service.SystemFont", create=True) as mock_sf_cls:
            # We need to mock the import inside the method
            with patch.dict("sys.modules", {"src.models": MagicMock()}):
                # Actually mock the import that happens in the function
                mock_system_font_module = MagicMock()
                mock_sf = MagicMock()
                mock_sf_cls.return_value = mock_sf

                with patch("src.services.font_service.select") as mock_select:
                    # The function does from ..models import SystemFont
                    # We need to handle that import
                    import importlib
                    with patch("builtins.__import__", side_effect=ImportError("test")):
                        pass

        # Better approach: just patch at the service level
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()
        mock_db_session.add = MagicMock()

        await font_service.cache_fonts([font])

        # Verify commit was called
        mock_db_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_cache_fonts_update_existing_font(self, font_service, mock_db_session):
        """Test updating an existing font in cache (lines 370-381)."""
        font = FontMetadata(
            name="ExistingFont",
            family="ExistingFamily",
            style="Bold",
            weight=700,
            file_path="/new/path.ttf",
            file_hash="newhash",
            is_valid=True,
            detection_timestamp="2026-02-01T00:00:00",
            metadata_json={"file_size": 5678},
            source="system",
        )

        # Mock existing font found in DB
        mock_existing = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_existing
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        await font_service.cache_fonts([font])

        # Verify the existing font was updated
        assert mock_existing.family == "ExistingFamily"
        assert mock_existing.style == "Bold"
        assert mock_existing.weight == 700
        mock_db_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_cache_fonts_integrity_error(self, font_service, mock_db_session):
        """Test handling IntegrityError during caching (lines 400-403)."""
        from sqlalchemy.exc import IntegrityError

        font = FontMetadata(name="DuplicateFont", family="Dup")

        mock_result = MagicMock()
        # First call raises IntegrityError
        mock_result.scalar.side_effect = IntegrityError("duplicate", {}, Exception())
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()
        mock_db_session.rollback = AsyncMock()

        await font_service.cache_fonts([font])
        mock_db_session.rollback.assert_awaited()

    @pytest.mark.asyncio
    async def test_cache_fonts_per_font_exception(self, font_service, mock_db_session):
        """Test per-font exception handling (lines 404-405)."""
        font = FontMetadata(name="ErrorFont", family="Err")

        mock_result = MagicMock()
        mock_result.scalar.side_effect = RuntimeError("unexpected error")
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        await font_service.cache_fonts([font])

    @pytest.mark.asyncio
    async def test_cache_fonts_global_exception(self, font_service, mock_db_session):
        """Test global exception handling in cache_fonts (lines 411-414)."""
        font = FontMetadata(name="GlobalError", family="Err")

        # Make execute succeed but commit fail to trigger the outer except
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
        mock_db_session.rollback = AsyncMock()

        await font_service.cache_fonts([font])
        mock_db_session.rollback.assert_awaited()


class TestGetAllFonts:
    """Test get_all_fonts method."""

    @pytest.mark.asyncio
    async def test_get_all_fonts_no_db_session(self, font_service_no_db):
        """Test get_all_fonts without db session (lines 429-431)."""
        result = await font_service_no_db.get_all_fonts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_fonts_no_filters(self, font_service, mock_db_session):
        """Test get_all_fonts with no filters (lines 433-476)."""
        mock_font = MagicMock()
        mock_font.id = "font-1"
        mock_font.name = "Arial"
        mock_font.family = "Arial"
        mock_font.style = "Regular"
        mock_font.weight = 400
        mock_font.file_path = "/path/arial.ttf"
        mock_font.file_hash = "hash123"
        mock_font.is_valid = True
        mock_font.detection_timestamp = "2026-01-01"
        mock_font.metadata_json = {"size": 100}
        mock_font.source = "system"

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_font]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await font_service.get_all_fonts()
        assert len(result) == 1
        assert result[0].name == "Arial"
        assert result[0].source == "system"

    @pytest.mark.asyncio
    async def test_get_all_fonts_with_source_filter(self, font_service, mock_db_session):
        """Test get_all_fonts with source filter (line 441)."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await font_service.get_all_fonts(source_filter="bundled")
        assert result == []
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_all_fonts_with_search_query(self, font_service, mock_db_session):
        """Test get_all_fonts with search query (lines 444-451)."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await font_service.get_all_fonts(search_query="arial")
        assert result == []
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_all_fonts_exception(self, font_service, mock_db_session):
        """Test get_all_fonts exception handling (lines 478-480)."""
        mock_db_session.execute = AsyncMock(side_effect=RuntimeError("db error"))
        result = await font_service.get_all_fonts()
        assert result == []


class TestGetFontByName:
    """Test get_font_by_name method."""

    @pytest.mark.asyncio
    async def test_get_font_by_name_exact_match(self, font_service, mock_db_session):
        """Test finding a font by exact name match (lines 492-501)."""
        mock_font = MagicMock()
        mock_font.id = "font-1"
        mock_font.name = "Arial"
        mock_font.family = "Arial"
        mock_font.style = "Regular"
        mock_font.weight = 400
        mock_font.file_path = "/path/arial.ttf"
        mock_font.file_hash = "hash"
        mock_font.is_valid = True
        mock_font.detection_timestamp = "2026-01-01"
        mock_font.metadata_json = {}
        mock_font.source = "system"

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_font]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await font_service.get_font_by_name("Arial")
        assert result is not None
        assert result.name == "Arial"

    @pytest.mark.asyncio
    async def test_get_font_by_name_family_match(self, font_service, mock_db_session):
        """Test finding a font by family name match (lines 503-504)."""
        mock_font = MagicMock()
        mock_font.id = "font-1"
        mock_font.name = "Arial Bold"
        mock_font.family = "Arial"
        mock_font.style = "Bold"
        mock_font.weight = 700
        mock_font.file_path = "/path/arialbd.ttf"
        mock_font.file_hash = "hash"
        mock_font.is_valid = True
        mock_font.detection_timestamp = "2026-01-01"
        mock_font.metadata_json = {}
        mock_font.source = "system"

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_font]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await font_service.get_font_by_name("Arial")
        assert result is not None
        assert result.family == "Arial"

    @pytest.mark.asyncio
    async def test_get_font_by_name_not_found(self, font_service, mock_db_session):
        """Test when font is not found (lines 506-507)."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await font_service.get_font_by_name("NonExistentFont")
        assert result is None


class TestRefreshSystemFonts:
    """Test refresh_system_fonts method."""

    @pytest.mark.asyncio
    async def test_refresh_system_fonts_success(self, font_service):
        """Test successful system font refresh (lines 516-526)."""
        fonts = [FontMetadata(name="SystemFont", family="SF")]
        font_service.detect_system_fonts = AsyncMock(return_value=fonts)
        font_service.cache_fonts = AsyncMock()

        result = await font_service.refresh_system_fonts()
        assert result == 1
        font_service.detect_system_fonts.assert_awaited_once()
        font_service.cache_fonts.assert_awaited_once_with(fonts)

    @pytest.mark.asyncio
    async def test_refresh_system_fonts_exception(self, font_service):
        """Test refresh_system_fonts exception handling (lines 527-529)."""
        font_service.detect_system_fonts = AsyncMock(side_effect=RuntimeError("refresh error"))

        result = await font_service.refresh_system_fonts()
        assert result == 0


# end backend/tests/unit/test_font_service.py
