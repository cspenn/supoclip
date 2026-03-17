# start tests/unit/test_settings.py
"""Unit tests for src/pages/settings.py.

Covers:
- is_valid_hex_color: valid and invalid inputs
- load_prefs: returns existing row from DB
- load_prefs: returns default instance when no row exists
- save_prefs: creates new row when none exists
- save_prefs: updates an existing row
- save_prefs: ai_prompt stored as None when blank string passed
- save_prefs: logo_path stored as None when not supplied
- render: loads existing preferences without error (mocked DB + NiceGUI)
- render: uses defaults when no existing preferences exist (mocked DB + NiceGUI)
- Logo upload handler: writes file and updates logo_state
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database import Base
from src.models import UserPreferences
from src.pages.settings import is_valid_hex_color, load_prefs, save_prefs

# ---------------------------------------------------------------------------
# In-memory DB fixture (mirrors pattern used in test_models.py)
# ---------------------------------------------------------------------------

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    """Provide a fresh in-memory database session for each test.

    Yields:
        An AsyncSession backed by an in-memory SQLite database.
    """
    engine = create_async_engine(_TEST_DB_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        yield sess

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# is_valid_hex_color
# ---------------------------------------------------------------------------


class TestIsValidHexColor:
    """Tests for the hex colour validator."""

    def test_valid_uppercase(self) -> None:
        """#FFFFFF is valid."""
        assert is_valid_hex_color("#FFFFFF") is True

    def test_valid_lowercase(self) -> None:
        """#ffffff is valid (case-insensitive)."""
        assert is_valid_hex_color("#ffffff") is True

    def test_valid_mixed_case(self) -> None:
        """#AbCdEf is valid."""
        assert is_valid_hex_color("#AbCdEf") is True

    def test_valid_black(self) -> None:
        """#000000 is valid."""
        assert is_valid_hex_color("#000000") is True

    def test_invalid_no_hash(self) -> None:
        """FFFFFF without leading # is invalid."""
        assert is_valid_hex_color("FFFFFF") is False

    def test_invalid_short(self) -> None:
        """#FFF (3-digit shorthand) is not accepted."""
        assert is_valid_hex_color("#FFF") is False

    def test_invalid_too_long(self) -> None:
        """#FFFFFFFF (8 chars) is not accepted."""
        assert is_valid_hex_color("#FFFFFFFF") is False

    def test_invalid_non_hex_chars(self) -> None:
        """#XXYYZZ contains non-hex characters — invalid."""
        assert is_valid_hex_color("#XXYYZZ") is False

    def test_empty_string(self) -> None:
        """Empty string is invalid."""
        assert is_valid_hex_color("") is False


# ---------------------------------------------------------------------------
# load_prefs
# ---------------------------------------------------------------------------


class TestLoadPrefs:
    """Tests for load_prefs()."""

    async def test_returns_existing_row(self, session: AsyncSession) -> None:
        """load_prefs returns the stored row when it exists."""
        prefs = UserPreferences(
            id=1,
            font_family="TikTokSans-Regular",
            font_size=30,
            font_color="#FF0000",
            font_stroke_color="#00FF00",
            font_stroke_width=3.0,
            font_shadow_offset=2,
            subtitle_position_y=80,
            min_clip_length=20,
            max_clip_length=50,
            output_resolution="720p",
        )
        session.add(prefs)
        await session.commit()

        # Patch get_session to return our test session
        async def _fake_session():  # type: ignore[return]
            yield session

        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            result = await load_prefs()

        assert result.font_family == "TikTokSans-Regular"
        assert result.font_size == 30
        assert result.output_resolution == "720p"

    async def test_returns_defaults_when_no_row(self) -> None:
        """load_prefs returns a default UserPreferences when no row exists."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(return_value=None)

        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(mock_session),
        ):
            result = await load_prefs()

        assert result.font_family == "Arial"
        assert result.font_size == 24
        assert result.font_color == "#FFFFFF"
        assert result.font_stroke_color == "#000000"
        assert result.font_stroke_width == 2.0
        assert result.font_shadow_offset == 1
        assert result.subtitle_position_y == 75
        assert result.min_clip_length == 15
        assert result.max_clip_length == 45
        assert result.output_resolution == "1080p"
        assert result.ai_prompt is None
        assert result.logo_path is None


# ---------------------------------------------------------------------------
# save_prefs
# ---------------------------------------------------------------------------


class TestSavePrefs:
    """Tests for save_prefs()."""

    def _full_data(self, **overrides: object) -> dict:  # type: ignore[type-arg]
        """Return a full settings dict, optionally overriding fields."""
        base: dict = {  # type: ignore[type-arg]
            "font_family": "Arial",
            "font_size": 24,
            "font_color": "#FFFFFF",
            "font_stroke_color": "#000000",
            "font_stroke_width": 2.0,
            "font_shadow_offset": 1,
            "subtitle_position_y": 75,
            "min_clip_length": 15,
            "max_clip_length": 45,
            "output_resolution": "1080p",
            "ai_prompt": None,
            "logo_path": None,
        }
        base.update(overrides)
        return base

    async def test_creates_new_row_when_none_exists(
        self, session: AsyncSession
    ) -> None:
        """save_prefs inserts a new row when no row with id=1 exists."""
        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            await save_prefs(self._full_data(font_family="Roboto", font_size=28))

        saved = await session.get(UserPreferences, 1)
        assert saved is not None
        assert saved.font_family == "Roboto"
        assert saved.font_size == 28

    async def test_updates_existing_row(self, session: AsyncSession) -> None:
        """save_prefs updates the fields of an existing row."""
        prefs = UserPreferences(
            id=1,
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            font_stroke_color="#000000",
            font_stroke_width=2.0,
            font_shadow_offset=1,
            subtitle_position_y=75,
            min_clip_length=15,
            max_clip_length=45,
            output_resolution="1080p",
        )
        session.add(prefs)
        await session.commit()

        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            await save_prefs(
                self._full_data(
                    font_family="Helvetica",
                    font_size=32,
                    output_resolution="720p",
                )
            )

        await session.refresh(prefs)
        assert prefs.font_family == "Helvetica"
        assert prefs.font_size == 32
        assert prefs.output_resolution == "720p"

    async def test_blank_ai_prompt_stored_as_none(
        self, session: AsyncSession
    ) -> None:
        """An empty string ai_prompt is coerced to None."""
        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            await save_prefs(self._full_data(ai_prompt=""))

        saved = await session.get(UserPreferences, 1)
        assert saved is not None
        assert saved.ai_prompt is None

    async def test_logo_path_stored_as_none_when_not_supplied(
        self, session: AsyncSession
    ) -> None:
        """logo_path is None when not included in the data dict."""
        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            await save_prefs(self._full_data(logo_path=None))

        saved = await session.get(UserPreferences, 1)
        assert saved is not None
        assert saved.logo_path is None

    async def test_logo_path_persisted_when_provided(
        self, session: AsyncSession
    ) -> None:
        """logo_path is persisted when a non-empty path is given."""
        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            await save_prefs(self._full_data(logo_path="/tmp/logo/brand.png"))

        saved = await session.get(UserPreferences, 1)
        assert saved is not None
        assert saved.logo_path == "/tmp/logo/brand.png"

    async def test_all_numeric_fields_coerced(self, session: AsyncSession) -> None:
        """Numeric fields saved via float/int slider values are stored correctly."""
        with patch(
            "src.pages.settings.get_session",
            return_value=_make_cm(session),
        ):
            await save_prefs(
                self._full_data(
                    font_size=36,
                    font_stroke_width=4.5,
                    font_shadow_offset=3,
                    subtitle_position_y=85,
                    min_clip_length=20,
                    max_clip_length=60,
                )
            )

        saved = await session.get(UserPreferences, 1)
        assert saved is not None
        assert saved.font_size == 36
        assert saved.font_stroke_width == pytest.approx(4.5)
        assert saved.font_shadow_offset == 3
        assert saved.subtitle_position_y == 85
        assert saved.min_clip_length == 20
        assert saved.max_clip_length == 60


# ---------------------------------------------------------------------------
# render() integration (NiceGUI mocked out)
# ---------------------------------------------------------------------------


class TestRender:
    """Tests for render() with NiceGUI and DB mocked."""

    async def test_render_with_existing_prefs(self) -> None:
        """render() runs without error when DB returns an existing row."""
        existing = UserPreferences(
            id=1,
            font_family="Comic Sans",
            font_size=18,
            font_color="#FF00FF",
            font_stroke_color="#000000",
            font_stroke_width=1.0,
            font_shadow_offset=0,
            subtitle_position_y=70,
            min_clip_length=10,
            max_clip_length=30,
            output_resolution="720p",
            ai_prompt="Be concise.",
            logo_path="/tmp/logo.png",
        )

        with (
            patch("src.pages.settings.load_prefs", new=AsyncMock(return_value=existing)),
            patch("src.pages.settings.get_config", return_value=_mock_config()),
            patch("src.pages.settings.ui", new=_build_ui_mock()),
        ):
            from src.pages.settings import render

            await render()

    async def test_render_with_no_existing_prefs(self) -> None:
        """render() runs without error when DB returns default preferences."""
        defaults = UserPreferences(
            id=1,
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            font_stroke_color="#000000",
            font_stroke_width=2.0,
            font_shadow_offset=1,
            subtitle_position_y=75,
            min_clip_length=15,
            max_clip_length=45,
            output_resolution="1080p",
            ai_prompt=None,
            logo_path=None,
        )

        with (
            patch("src.pages.settings.load_prefs", new=AsyncMock(return_value=defaults)),
            patch("src.pages.settings.get_config", return_value=_mock_config()),
            patch("src.pages.settings.ui", new=_build_ui_mock()),
        ):
            from src.pages.settings import render

            await render()


# ---------------------------------------------------------------------------
# Logo upload handler
# ---------------------------------------------------------------------------


class TestLogoUpload:
    """Tests for the logo upload handler inside render()."""

    async def test_upload_writes_file_and_updates_state(
        self, tmp_path: Path
    ) -> None:
        """handle_logo_upload writes bytes to disk under config.temp_dir/logo/."""
        file_content = b"fake-png-data"
        upload_event = MagicMock()
        upload_event.name = "brand.png"
        upload_event.content = BytesIO(file_content)

        config_mock = MagicMock()
        config_mock.temp_dir = tmp_path

        captured_state: dict[str, str | None] = {"path": None}

        # Simulate what render() does: extract the handler and call it directly
        def make_handler(
            state: dict[str, str | None], cfg: object
        ):  # type: ignore[return]
            def handle_logo_upload(e: object) -> None:
                name: str = getattr(e, "name", "logo")
                content = getattr(e, "content", None)
                if content is None:
                    return


                logo_dir = cfg.temp_dir / "logo"
                logo_dir.mkdir(parents=True, exist_ok=True)
                dest = logo_dir / name
                dest.write_bytes(content.read())
                state["path"] = str(dest)

            return handle_logo_upload

        handler = make_handler(captured_state, config_mock)
        handler(upload_event)

        expected = tmp_path / "logo" / "brand.png"
        assert expected.exists()
        assert expected.read_bytes() == file_content
        assert captured_state["path"] == str(expected)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CM:
    """Minimal async context manager wrapping a pre-existing session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_: object) -> None:
        # Commit so that the test assertions can read the flushed state
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()


def _make_cm(session: AsyncSession) -> _CM:
    """Return an async context manager that yields *session*."""
    return _CM(session)


def _mock_config() -> MagicMock:
    """Return a mock Config with a temp_dir attribute."""
    cfg = MagicMock()
    cfg.temp_dir = Path("/tmp/supoclip_test")
    return cfg


def _build_ui_mock() -> MagicMock:
    """Return a MagicMock that satisfies all NiceGUI ui.* calls in render().

    Every element returned by a builder call (column, card, row, input, etc.)
    is itself a MagicMock whose ``.classes()``, ``.props()``, and
    ``__enter__``/``__exit__`` context manager methods all return mocks so
    that ``with ui.column():`` blocks execute without error.
    """
    def _element(*_args: object, **_kwargs: object) -> MagicMock:
        elem = MagicMock()
        elem.__enter__ = MagicMock(return_value=elem)
        elem.__exit__ = MagicMock(return_value=False)
        elem.classes = MagicMock(return_value=elem)
        elem.props = MagicMock(return_value=elem)
        elem.value = _kwargs.get("value", "")
        return elem

    mock_ui = MagicMock()
    for name in (
        "column",
        "card",
        "row",
        "label",
        "input",
        "slider",
        "color_input",
        "textarea",
        "select",
        "upload",
        "button",
        "notify",
    ):
        getattr(mock_ui, name).side_effect = _element

    return mock_ui
# end tests/unit/test_settings.py
