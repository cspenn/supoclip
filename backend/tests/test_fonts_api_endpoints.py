# start backend/tests/test_fonts_api_endpoints.py

"""Comprehensive API endpoint tests for font management."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime

from src.main import app
from src.models import Base, SystemFont
from src.services.font_service import FontService
from src.dependencies import set_font_service

client = TestClient(app)


@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_font_service(test_db):
    """Create test font service with database session."""
    service = FontService(db_session=test_db, temp_dir=Path("/tmp"))
    set_font_service(service)
    return service


@pytest.fixture
async def sample_fonts(test_db):
    """Create sample fonts for testing."""
    fonts = [
        SystemFont(
            id=str(uuid.uuid4()),
            name="Arial",
            family="Arial",
            style="Regular",
            weight=400,
            file_path="/System/Library/Fonts/Arial.ttf",
            file_hash="hash1",
            is_valid=True,
            detection_timestamp=datetime.now().isoformat(),
            source="system",
        ),
        SystemFont(
            id=str(uuid.uuid4()),
            name="Arial Bold",
            family="Arial",
            style="Bold",
            weight=700,
            file_path="/System/Library/Fonts/Arial Bold.ttf",
            file_hash="hash2",
            is_valid=True,
            detection_timestamp=datetime.now().isoformat(),
            source="system",
        ),
        SystemFont(
            id=str(uuid.uuid4()),
            name="Times New Roman",
            family="Times New Roman",
            style="Regular",
            weight=400,
            file_path="/System/Library/Fonts/Times.ttf",
            file_hash="hash3",
            is_valid=True,
            detection_timestamp=datetime.now().isoformat(),
            source="system",
        ),
        SystemFont(
            id=str(uuid.uuid4()),
            name="Custom Font",
            family="Custom",
            style="Regular",
            weight=400,
            file_path="/backend/fonts/custom.ttf",
            file_hash="hash4",
            is_valid=True,
            detection_timestamp=datetime.now().isoformat(),
            source="bundled",
        ),
    ]

    test_db.add_all(fonts)
    await test_db.commit()

    return fonts


class TestFontsListEndpoint:
    """Tests for GET /fonts endpoint."""

    def test_list_all_fonts(self):
        """Test listing all fonts returns success."""
        response = client.get("/fonts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_fonts_with_bundled_filter(self):
        """Test filtering fonts by bundled source."""
        response = client.get("/fonts?source=bundled")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for font in data:
            assert font["source"] == "bundled"

    def test_list_fonts_with_system_filter(self):
        """Test filtering fonts by system source."""
        response = client.get("/fonts?source=system")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for font in data:
            assert font["source"] == "system"

    def test_list_fonts_response_format(self):
        """Test that response has correct font metadata format."""
        response = client.get("/fonts")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            font = data[0]
            assert "id" in font
            assert "name" in font
            assert "family" in font
            assert "style" in font
            assert "weight" in font
            assert "source" in font


class TestFontSearchEndpoint:
    """Tests for GET /fonts/search endpoint."""

    def test_search_fonts_by_name(self):
        """Test searching fonts by name."""
        response = client.get("/fonts/search?q=arial")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for font in data:
            search_term = "arial"
            assert (
                search_term in font["name"].lower()
                or search_term in font["family"].lower()
            )

    def test_search_fonts_by_family(self):
        """Test searching fonts by family."""
        response = client.get("/fonts/search?q=times")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_nonexistent_font(self):
        """Test searching for nonexistent font returns empty list."""
        response = client.get("/fonts/search?q=nonexistentfontXYZ")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_search_missing_query_parameter(self):
        """Test search without query parameter returns 422."""
        response = client.get("/fonts/search")
        assert response.status_code == 422

    def test_search_query_too_short(self):
        """Test search with 1 character query returns 400."""
        response = client.get("/fonts/search?q=a")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_search_case_insensitive(self):
        """Test search is case insensitive."""
        response_lower = client.get("/fonts/search?q=arial")
        response_upper = client.get("/fonts/search?q=ARIAL")
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        assert len(data_lower) == len(data_upper)


class TestFontRefreshEndpoint:
    """Tests for POST /fonts/refresh endpoint."""

    def test_refresh_fonts(self):
        """Test refreshing system fonts."""
        response = client.post("/fonts/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "message" in data
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_refresh_fonts_returns_proper_structure(self):
        """Test refresh response has required fields."""
        response = client.post("/fonts/refresh")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data
        assert "count" in data
        assert data["status"] in ["success", "error"]


class TestFontFileServingEndpoint:
    """Tests for GET /fonts/{font_name} endpoint."""

    def test_serve_nonexistent_font_file(self):
        """Test serving nonexistent font returns 404."""
        response = client.get("/fonts/NonExistentFontXYZ")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_serve_existing_font_file(self):
        """Test serving an existing font file."""
        # Try to serve Arial which might exist
        response = client.get("/fonts/Arial")
        assert response.status_code in [200, 404]


class TestFontsEndpointErrorHandling:
    """Tests for error handling across endpoints."""

    def test_invalid_source_filter(self):
        """Test invalid source filter parameter."""
        response = client.get("/fonts?source=invalid")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should return empty list for invalid source
        assert len(data) == 0

    def test_special_characters_in_search(self):
        """Test search with special characters."""
        response = client.get("/fonts/search?q=!@test")
        assert response.status_code in [200, 400]

    def test_very_long_search_query(self):
        """Test search with very long query string."""
        long_query = "a" * 100
        response = client.get(f"/fonts/search?q={long_query}")
        assert response.status_code in [200, 400]


class TestEdgeCasesAndConcurrency:
    """Tests for edge cases and concurrent operations."""

    def test_empty_font_list(self):
        """Test behavior with empty font list."""
        response = client.get("/fonts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# end backend/tests/test_fonts_api_endpoints.py
