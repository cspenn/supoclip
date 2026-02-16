# start backend/tests/unit/test_source_repository.py
"""
Unit tests for SourceRepository — covers create_source, get_source_by_id,
and update_source_title.

Goal: 100% line coverage for src/repositories/source_repository.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSourceRepositoryCreateSource:
    """Test SourceRepository.create_source()."""

    async def test_create_source_returns_id(self):
        """Test that create_source creates a Source, flushes, and returns the ID."""
        from src.repositories.source_repository import SourceRepository

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        # Patch the Source model that gets imported inside the method
        mock_source_instance = MagicMock()
        mock_source_instance.id = "generated-uuid-123"

        with patch("src.models.Source", return_value=mock_source_instance):
            result = await SourceRepository.create_source(
                db=mock_db,
                source_type="youtube",
                title="Test Video",
                url="https://youtube.com/watch?v=123",
                metadata={"duration": 120},
            )

            mock_db.add.assert_called_once()
            mock_db.flush.assert_awaited_once()
            assert result == mock_source_instance.id

    async def test_create_source_sets_type_and_title(self):
        """Test that create_source sets type and title on the Source object."""
        from src.repositories.source_repository import SourceRepository

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        mock_source = MagicMock()
        mock_source.id = "src-456"

        with patch("src.models.Source", return_value=mock_source):
            await SourceRepository.create_source(
                db=mock_db,
                source_type="upload",
                title="Uploaded Video",
            )

            assert mock_source.type == "upload"
            assert mock_source.title == "Uploaded Video"

    async def test_create_source_without_optional_params(self):
        """Test create_source with default None for url and metadata."""
        from src.repositories.source_repository import SourceRepository

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        mock_source = MagicMock()
        mock_source.id = "src-789"

        with patch("src.models.Source", return_value=mock_source):
            result = await SourceRepository.create_source(
                db=mock_db,
                source_type="video_url",
                title="Some Video",
            )

            assert result == "src-789"


class TestSourceRepositoryGetSourceById:
    """Test SourceRepository.get_source_by_id()."""

    async def test_get_source_by_id_found(self):
        """Test get_source_by_id returns dict when source exists."""
        from src.repositories.source_repository import SourceRepository

        mock_row = MagicMock()
        mock_row.id = "src-123"
        mock_row.type = "youtube"
        mock_row.title = "Test Video"
        mock_row.url = "https://youtube.com/watch?v=123"
        mock_row.metadata = None
        mock_row.created_at = "2024-01-01T00:00:00"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await SourceRepository.get_source_by_id(mock_db, "src-123")

        assert result is not None
        assert result["id"] == "src-123"
        assert result["type"] == "youtube"
        assert result["title"] == "Test Video"
        assert result["created_at"] == "2024-01-01T00:00:00"

    async def test_get_source_by_id_not_found(self):
        """Test get_source_by_id returns None when source does not exist."""
        from src.repositories.source_repository import SourceRepository

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await SourceRepository.get_source_by_id(mock_db, "nonexistent")

        assert result is None

    async def test_get_source_by_id_missing_url_attribute(self):
        """Test get_source_by_id handles missing url attribute gracefully via getattr."""
        from src.repositories.source_repository import SourceRepository

        mock_row = MagicMock(spec=["id", "type", "title", "created_at"])
        mock_row.id = "src-456"
        mock_row.type = "upload"
        mock_row.title = "Upload Video"
        mock_row.created_at = "2024-06-01T12:00:00"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await SourceRepository.get_source_by_id(mock_db, "src-456")

        assert result is not None
        assert result["url"] is None
        assert result["metadata"] is None


class TestSourceRepositoryUpdateSourceTitle:
    """Test SourceRepository.update_source_title()."""

    async def test_update_source_title(self):
        """Test that update_source_title executes update and commits."""
        from src.repositories.source_repository import SourceRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await SourceRepository.update_source_title(
            mock_db, "src-123", "New Title"
        )

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify the parameters include both title and source_id
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["title"] == "New Title"
        assert params["source_id"] == "src-123"


# end backend/tests/unit/test_source_repository.py
