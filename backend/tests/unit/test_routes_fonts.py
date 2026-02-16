# start backend/tests/unit/test_routes_fonts.py
"""
Comprehensive tests for the fonts API routes.

Covers all endpoints in src/api/routes/fonts.py with mocked
font service to achieve 100% line coverage.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.fonts import router
from src.services.font_service import FontMetadata, FontService
from src.dependencies import get_font_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with the fonts router and no lifespan."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


def _make_font_metadata(
    name: str = "TestFont",
    family: str = "Test",
    style: str = "Regular",
    weight: int = 400,
    source: str = "bundled",
    file_path: str | None = None,
) -> FontMetadata:
    """Create a FontMetadata instance for testing."""
    return FontMetadata(
        id="font-1",
        name=name,
        family=family,
        style=style,
        weight=weight,
        file_path=file_path,
        source=source,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    return _make_app()


@pytest.fixture()
def mock_font_service():
    """Return a mock FontService."""
    service = AsyncMock(spec=FontService)
    return service


@pytest.fixture()
def client(app, mock_font_service):
    """TestClient with get_font_service overridden."""
    async def _override():
        return mock_font_service

    app.dependency_overrides[get_font_service] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ==========================================================================
#  GET /fonts — list_fonts
# ==========================================================================

class TestListFonts:

    def test_list_fonts_success(self, client, mock_font_service):
        """List all fonts successfully."""
        fonts = [
            _make_font_metadata(name="Font1", family="Fam1"),
            _make_font_metadata(name="Font2", family="Fam2", source="system"),
        ]
        mock_font_service.get_all_fonts = AsyncMock(return_value=fonts)

        resp = client.get("/fonts")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["name"] == "Font1"
        assert body[1]["source"] == "system"

    def test_list_fonts_with_source_filter(self, client, mock_font_service):
        """List fonts filtered by source."""
        fonts = [_make_font_metadata(source="system")]
        mock_font_service.get_all_fonts = AsyncMock(return_value=fonts)

        resp = client.get("/fonts?source=system")

        assert resp.status_code == 200
        mock_font_service.get_all_fonts.assert_called_once_with(source_filter="system")

    def test_list_fonts_empty(self, client, mock_font_service):
        """List fonts when none available."""
        mock_font_service.get_all_fonts = AsyncMock(return_value=[])

        resp = client.get("/fonts")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_fonts_service_error(self, client, mock_font_service):
        """Service error returns 500."""
        mock_font_service.get_all_fonts = AsyncMock(
            side_effect=RuntimeError("db error")
        )

        resp = client.get("/fonts")

        assert resp.status_code == 500
        assert "Failed to list fonts" in resp.json()["detail"]


# ==========================================================================
#  GET /fonts/search — search_fonts
# ==========================================================================

class TestSearchFonts:

    def test_search_fonts_success(self, client, mock_font_service):
        """Search fonts by query."""
        fonts = [_make_font_metadata(name="Arial Bold", family="Arial")]
        mock_font_service.get_all_fonts = AsyncMock(return_value=fonts)

        resp = client.get("/fonts/search?q=Arial")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Arial Bold"
        mock_font_service.get_all_fonts.assert_called_once_with(search_query="Arial")

    def test_search_fonts_short_query(self, client, mock_font_service):
        """Query too short returns 400."""
        resp = client.get("/fonts/search?q=A")

        assert resp.status_code == 400
        assert "at least 2 characters" in resp.json()["detail"]

    def test_search_fonts_empty_query(self, client, mock_font_service):
        """Empty query returns 400 (FastAPI validates required param)."""
        resp = client.get("/fonts/search")

        assert resp.status_code == 422  # FastAPI validation error for required param

    def test_search_fonts_service_error(self, client, mock_font_service):
        """Service error returns 500."""
        mock_font_service.get_all_fonts = AsyncMock(
            side_effect=RuntimeError("search error")
        )

        resp = client.get("/fonts/search?q=test")

        assert resp.status_code == 500
        assert "Failed to search fonts" in resp.json()["detail"]


# ==========================================================================
#  POST /fonts/refresh — refresh_fonts
# ==========================================================================

class TestRefreshFonts:

    def test_refresh_fonts_success(self, client, mock_font_service):
        """Refresh system fonts successfully."""
        system_fonts = [
            _make_font_metadata(name="SysFont1", source="system"),
            _make_font_metadata(name="SysFont2", source="system"),
        ]
        mock_font_service.detect_system_fonts = AsyncMock(return_value=system_fonts)
        mock_font_service.cache_fonts = AsyncMock()

        resp = client.post("/fonts/refresh")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["count"] == 2
        assert "2 system fonts" in body["message"]

    def test_refresh_fonts_service_error(self, client, mock_font_service):
        """Service error returns 500."""
        mock_font_service.detect_system_fonts = AsyncMock(
            side_effect=RuntimeError("detection failed")
        )

        resp = client.post("/fonts/refresh")

        assert resp.status_code == 500
        assert "Failed to refresh fonts" in resp.json()["detail"]


# ==========================================================================
#  GET /fonts/{font_name} — get_font_file
# ==========================================================================

class TestGetFontFile:

    def test_get_font_file_success(self, client, mock_font_service):
        """Serve a font file successfully."""
        # Create a real temp file to serve
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as f:
            f.write(b"fake font data")
            temp_path = f.name

        font = _make_font_metadata(
            name="MyFont",
            file_path=temp_path,
        )
        mock_font_service.get_all_fonts = AsyncMock(return_value=[font])

        resp = client.get("/fonts/MyFont")

        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "font/ttf"
        assert "Cache-Control" in resp.headers

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_get_font_file_not_found_no_match(self, client, mock_font_service):
        """Font name not in list returns 404."""
        mock_font_service.get_all_fonts = AsyncMock(return_value=[])

        resp = client.get("/fonts/NonexistentFont")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_get_font_file_no_file_path(self, client, mock_font_service):
        """Font exists but has no file_path returns 404."""
        font = _make_font_metadata(name="NoPathFont", file_path=None)
        mock_font_service.get_all_fonts = AsyncMock(return_value=[font])

        resp = client.get("/fonts/NoPathFont")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_get_font_file_path_not_exists(self, client, mock_font_service):
        """Font has file_path but file doesn't exist returns 404."""
        font = _make_font_metadata(
            name="MissingFile",
            file_path="/tmp/nonexistent_font_file_12345.ttf",
        )
        mock_font_service.get_all_fonts = AsyncMock(return_value=[font])

        resp = client.get("/fonts/MissingFile")

        assert resp.status_code == 404
        assert "Font file not found" in resp.json()["detail"]

    def test_get_font_file_path_is_directory(self, client, mock_font_service):
        """Font file_path points to a directory returns 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            font = _make_font_metadata(
                name="DirFont",
                file_path=tmpdir,  # directory, not a file
            )
            mock_font_service.get_all_fonts = AsyncMock(return_value=[font])

            resp = client.get("/fonts/DirFont")

        assert resp.status_code == 404

    def test_get_font_file_service_error(self, client, mock_font_service):
        """Service error returns 500."""
        mock_font_service.get_all_fonts = AsyncMock(
            side_effect=RuntimeError("unexpected error")
        )

        resp = client.get("/fonts/SomeFont")

        assert resp.status_code == 500
        assert "Failed to serve font file" in resp.json()["detail"]


# end backend/tests/unit/test_routes_fonts.py
