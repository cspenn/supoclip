"""Unit tests for FastAPI dependency injection functions.

Tests auth middleware and other dependencies used throughout the application.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_current_user, get_optional_user


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = MagicMock()
    request.headers = {}
    return request


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_x_user_id_header(self, mock_request, mock_db):
        """Test extracting user from X-User-ID header."""
        mock_request.headers = {"X-User-ID": "user_123"}

        # Mock database result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_123",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_id = await get_current_user(mock_request, mock_db)

        assert user_id == "user_123"

    @pytest.mark.asyncio
    async def test_get_current_user_with_user_id_header(self, mock_request, mock_db):
        """Test extracting user from user-id header (fallback format)."""
        mock_request.headers = {"user-id": "user_456"}

        # Mock database result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_456",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_id = await get_current_user(mock_request, mock_db)

        assert user_id == "user_456"

    @pytest.mark.asyncio
    async def test_get_current_user_prefers_x_user_id(self, mock_request, mock_db):
        """Test that X-User-ID is preferred over user-id."""
        mock_request.headers = {
            "X-User-ID": "user_123",
            "user-id": "user_456"
        }

        # Mock database result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_123",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_id = await get_current_user(mock_request, mock_db)

        assert user_id == "user_123"

    @pytest.mark.asyncio
    async def test_get_current_user_missing_header_raises_401(self, mock_request, mock_db):
        """Test that missing user header raises 401 error."""
        mock_request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, mock_db)

        assert exc_info.value.status_code == 401
        assert "authentication required" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_empty_header_raises_401(self, mock_request, mock_db):
        """Test that empty user header raises 401 error."""
        mock_request.headers = {"X-User-ID": ""}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_whitespace_only_header_raises_401(self, mock_request, mock_db):
        """Test that whitespace-only user header raises 401 error."""
        mock_request.headers = {"X-User-ID": "   "}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_not_found_in_db_raises_401(self, mock_request, mock_db):
        """Test that non-existent user raises 401 error."""
        mock_request.headers = {"X-User-ID": "nonexistent_user"}

        # Mock database returning no result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, mock_db)

        assert exc_info.value.status_code == 401
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_database_error_raises_500(self, mock_request, mock_db):
        """Test that database errors raise 500 error."""
        mock_request.headers = {"X-User-ID": "user_123"}

        # Mock database raising an exception
        mock_db.execute = AsyncMock(side_effect=Exception("Database connection error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, mock_db)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_current_user_verifies_in_database(self, mock_request, mock_db):
        """Test that user is verified to exist in database."""
        mock_request.headers = {"X-User-ID": "user_123"}

        # Mock database result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_123",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        await get_current_user(mock_request, mock_db)

        # Verify database query was executed
        mock_db.execute.assert_called_once()
        # Verify the query includes user ID
        call_args = mock_db.execute.call_args
        assert "user_id" in str(call_args)


class TestGetOptionalUser:
    """Test get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_user_when_authenticated(self, mock_request, mock_db):
        """Test that optional user returns user_id when authenticated."""
        mock_request.headers = {"X-User-ID": "user_123"}

        # Mock database result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_123",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_id = await get_optional_user(mock_request, mock_db)

        assert user_id == "user_123"

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_none_when_not_authenticated(self, mock_request, mock_db):
        """Test that optional user returns None when not authenticated."""
        mock_request.headers = {}

        user_id = await get_optional_user(mock_request, mock_db)

        assert user_id is None

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_none_when_user_not_found(self, mock_request, mock_db):
        """Test that optional user returns None when user not found in database."""
        mock_request.headers = {"X-User-ID": "nonexistent_user"}

        # Mock database returning no result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_id = await get_optional_user(mock_request, mock_db)

        assert user_id is None

    @pytest.mark.asyncio
    async def test_get_optional_user_does_not_raise_on_missing_header(self, mock_request, mock_db):
        """Test that optional user doesn't raise exception on missing header."""
        mock_request.headers = {}

        # Should not raise an exception
        user_id = await get_optional_user(mock_request, mock_db)
        assert user_id is None

    @pytest.mark.asyncio
    async def test_get_optional_user_does_not_raise_on_database_error(self, mock_request, mock_db):
        """Test that optional user doesn't raise on database error."""
        mock_request.headers = {"X-User-ID": "user_123"}

        # Mock database raising an exception
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

        # Should not raise an exception
        user_id = await get_optional_user(mock_request, mock_db)
        assert user_id is None

    @pytest.mark.asyncio
    async def test_get_optional_user_with_both_header_formats(self, mock_request, mock_db):
        """Test optional user with both header formats present."""
        mock_request.headers = {
            "X-User-ID": "user_123",
            "user-id": "user_456"
        }

        # Mock database result
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_123",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_id = await get_optional_user(mock_request, mock_db)

        # Should return the user from X-User-ID (preferred format)
        assert user_id == "user_123"

# end backend/tests/unit/test_dependencies.py
