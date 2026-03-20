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
- Handler callbacks: save() max<min error, invalid font color, invalid stroke color,
  success path; reset(); clear_logo(); handle_logo_upload None-content path.
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
        """#XXYYZZ contains non-hex characters - invalid."""
        assert is_valid_hex_color("#XXYYZZ") is False

    def test_empty_string(self) -> None:
        """Empty string is invalid."""
        assert is_valid_hex_color("") is False


# ---------------------------------------------------------------------------
# _discover_fonts
# ---------------------------------------------------------------------------


class TestDiscoverFonts:
    """Tests for the _discover_fonts() module-level helper."""

    def test_empty_dir_returns_arial(self, tmp_path: Path) -> None:
        """Empty fonts directory returns the Arial fallback."""
        from src.pages.settings import _discover_fonts

        result = _discover_fonts(fonts_dir=tmp_path)
        assert result == ["Arial"]

    def test_valid_ttfs_returns_sorted_names(self, tmp_path: Path) -> None:
        """TTF files are parsed and names returned sorted alphabetically."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "barlow.ttf").write_bytes(b"fake")
        (tmp_path / "arial.ttf").write_bytes(b"fake")

        def _mock_ttfont(path: str) -> MagicMock:
            font = MagicMock()
            name_table = MagicMock()
            if "barlow" in path:
                r = MagicMock()
                r.nameID = 1
                r.toUnicode.return_value = "Barlow Condensed"
            else:
                r = MagicMock()
                r.nameID = 1
                r.toUnicode.return_value = "Arial"
            name_table.names = [r]
            font.__getitem__ = lambda _self, _key: name_table
            return font

        with patch("src.pages.settings.TTFont", side_effect=_mock_ttfont):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Arial", "Barlow Condensed"]

    def test_bad_file_is_skipped(self, tmp_path: Path) -> None:
        """Unparseable TTF files are skipped; valid ones still returned."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "good.ttf").write_bytes(b"fake")
        (tmp_path / "bad.ttf").write_bytes(b"invalid")

        good_font = MagicMock()
        good_record = MagicMock()
        good_record.nameID = 1
        good_record.toUnicode.return_value = "Good Font"
        good_name_table = MagicMock()
        good_name_table.names = [good_record]
        good_font.__getitem__ = lambda _self, _key: good_name_table

        def _mock_ttfont(path: str) -> MagicMock:
            if Path(path).name == "bad.ttf":
                raise Exception("Invalid font file")
            return good_font

        with patch("src.pages.settings.TTFont", side_effect=_mock_ttfont):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Good Font"]

    def test_all_files_fail_falls_back_to_arial(self, tmp_path: Path) -> None:
        """When all TTF files fail to parse, Arial fallback is returned."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "broken.ttf").write_bytes(b"garbage")

        with patch("src.pages.settings.TTFont", side_effect=Exception("parse error")):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Arial"]

    def test_current_value_not_in_list_is_prepended(self, tmp_path: Path) -> None:
        """current_value is prepended when not in the discovered list."""
        from src.pages.settings import _discover_fonts

        result = _discover_fonts(fonts_dir=tmp_path, current_value="MyCustomFont")
        # tmp_path is empty → fallback ["Arial"], "MyCustomFont" prepended
        assert result == ["MyCustomFont", "Arial"]

    def test_current_value_already_in_list_not_duplicated(
        self, tmp_path: Path
    ) -> None:
        """current_value is not added when already present in the list."""
        from src.pages.settings import _discover_fonts

        result = _discover_fonts(fonts_dir=tmp_path, current_value="Arial")
        assert result == ["Arial"]  # not ["Arial", "Arial"]

    def test_nameids_fallback_to_nameid4(self, tmp_path: Path) -> None:
        """Falls back to nameID 4 when nameID 1 is absent."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "font.ttf").write_bytes(b"fake")

        font = MagicMock()
        name_table = MagicMock()
        r4 = MagicMock()
        r4.nameID = 4
        r4.toUnicode.return_value = "Full Name Font"
        name_table.names = [r4]
        font.__getitem__ = lambda _self, _key: name_table

        with patch("src.pages.settings.TTFont", return_value=font):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Full Name Font"]

    def test_tounicode_error_falls_back_to_next_record(self, tmp_path: Path) -> None:
        """When toUnicode() raises, the next matching record is tried."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "font.ttf").write_bytes(b"fake")

        font = MagicMock()
        name_table = MagicMock()

        # First nameID-1 record raises, second nameID-1 record succeeds
        r_bad = MagicMock()
        r_bad.nameID = 1
        r_bad.toUnicode.side_effect = Exception("decode error")

        r_good = MagicMock()
        r_good.nameID = 1
        r_good.toUnicode.return_value = "Fallback Font"

        name_table.names = [r_bad, r_good]
        font.__getitem__ = lambda _self, _key: name_table

        with patch("src.pages.settings.TTFont", return_value=font):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Fallback Font"]


# ---------------------------------------------------------------------------
# _build_typo_html / _build_phone_html
# ---------------------------------------------------------------------------


class TestBuildPreviewHtml:
    """Tests for the preview HTML builder functions."""

    def test_typo_html_contains_font_color(self) -> None:
        """Typography card HTML includes the font color."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FF0000",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "#FF0000" in html

    def test_typo_html_contains_font_size(self) -> None:
        """Typography card HTML includes the font size in px."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=36,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "36px" in html

    def test_typo_html_contains_stroke_color(self) -> None:
        """Typography card HTML includes the stroke color."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#ABCDEF",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "#ABCDEF" in html

    def test_typo_html_contains_stroke_width(self) -> None:
        """Typography card HTML includes the stroke width."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=3.5,
            shadow_offset=1,
        )
        assert "3.5px" in html

    def test_typo_html_contains_sample_text(self) -> None:
        """Typography card HTML contains the sample subtitle text."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "Every moment" in html

    def test_phone_html_contains_subtitle_y_position(self) -> None:
        """Phone frame HTML positions the text at the specified Y percentage."""
        from src.pages.settings import _build_phone_html

        html = _build_phone_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
            subtitle_y=80,
        )
        assert "80%" in html

    def test_phone_html_contains_font_color(self) -> None:
        """Phone frame HTML includes the font color."""
        from src.pages.settings import _build_phone_html

        html = _build_phone_html(
            font_family="Arial",
            font_size=24,
            font_color="#12FF34",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
            subtitle_y=75,
        )
        assert "#12FF34" in html

    def test_phone_html_contains_sample_text(self) -> None:
        """Phone frame HTML contains the sample subtitle text."""
        from src.pages.settings import _build_phone_html

        html = _build_phone_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
            subtitle_y=75,
        )
        assert "Every moment" in html


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
# Logo upload handler (simulated inline)
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
# Inner handler coverage via callback capture
#
# Design: each test builds a capturing UI mock, patches module globals, calls
# render(), then -- WHILE STILL INSIDE the patch context -- invokes the
# captured handler.  This ensures that when save()/reset()/etc. call
# ui.notify, the patched mock_ui is still installed at src.pages.settings.ui.
# ---------------------------------------------------------------------------


def _make_elem(*_args: object, **kwargs: object) -> MagicMock:
    """Return a MagicMock element with fluent API and settable .value / .text.

    Args:
        *_args: Positional arguments (ignored; NiceGUI passes label as first arg).
        **kwargs: Optional value keyword forwarded to elem.value and elem.text.

    Returns:
        A pre-configured MagicMock suitable for NiceGUI widget use.
    """
    elem = MagicMock()
    elem.__enter__ = MagicMock(return_value=elem)
    elem.__exit__ = MagicMock(return_value=False)
    elem.classes = MagicMock(return_value=elem)
    elem.props = MagicMock(return_value=elem)
    elem.value = kwargs.get("value", "")
    elem.text = kwargs.get("value", "")
    return elem


def _build_capturing_ui_mock(
    notify_calls: list[tuple] | None = None,
    slider_values: dict[int, object] | None = None,
    color_overrides: dict[str, str] | None = None,
) -> tuple[MagicMock, dict[str, object]]:
    """Build a UI mock that captures button on_click and upload on_upload callbacks.

    Sliders are created in render() in this order:
    1=font_size, 2=stroke_width, 3=shadow_offset, 4=subtitle_y,
    5=min_clip, 6=max_clip.

    Args:
        notify_calls: List that receives (args, kwargs) tuples from ui.notify calls.
        slider_values: {1-based call index: value} overrides for slider widgets.
        color_overrides: {label_substring: forced_value} overrides for color_input.

    Returns:
        A (mock_ui, captured) tuple.  Keys in captured:
        "button_N_<label>" per button with on_click,
        "on_upload" for the upload widget.
    """
    captured: dict[str, object] = {}
    call_order: list[str] = []
    slider_call_count = 0

    def _slider(*_args: object, **kwargs: object) -> MagicMock:
        nonlocal slider_call_count
        slider_call_count += 1
        elem = _make_elem(**kwargs)
        if slider_values and slider_call_count in slider_values:
            elem.value = slider_values[slider_call_count]
        return elem

    def _color_input(*_args: object, **kwargs: object) -> MagicMock:
        elem = _make_elem(**kwargs)
        if color_overrides:
            label = str(kwargs.get("label", ""))
            for key, forced_val in color_overrides.items():
                if key in label:
                    elem.value = forced_val
                    break
        return elem

    def _button(*_args: object, **kwargs: object) -> MagicMock:
        elem = _make_elem(**kwargs)
        label = _args[0] if _args else kwargs.get("label", "")
        on_click = kwargs.get("on_click")
        if on_click is not None:
            call_order.append(str(label))
            captured[f"button_{len(call_order)}_{label}"] = on_click
        return elem

    def _upload(*_args: object, **kwargs: object) -> MagicMock:
        elem = _make_elem(**kwargs)
        on_upload = kwargs.get("on_upload")
        if on_upload is not None:
            captured["on_upload"] = on_upload
        return elem

    def _notify(*args: object, **kwargs: object) -> MagicMock:
        if notify_calls is not None:
            notify_calls.append((args, kwargs))
        return MagicMock()

    mock_ui = MagicMock()
    for name in ("column", "card", "row", "label", "input", "textarea", "select"):
        getattr(mock_ui, name).side_effect = _make_elem

    mock_ui.slider.side_effect = _slider
    mock_ui.color_input.side_effect = _color_input
    mock_ui.button.side_effect = _button
    mock_ui.upload.side_effect = _upload
    mock_ui.notify.side_effect = _notify

    return mock_ui, captured


def _make_default_prefs() -> UserPreferences:
    """Return a default UserPreferences instance for use in handler tests."""
    return UserPreferences(
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


class TestHandlerCallbacks:
    """Tests that exercise inner closures in render() via captured callbacks."""

    async def test_save_max_less_than_min_shows_error(
        self, tmp_path: Path
    ) -> None:
        """save() notifies an error when max_clip < min_clip (lines 252-257).

        Slider creation order: 1=font_size, 2=stroke_width, 3=shadow_offset,
        4=subtitle_y, 5=min_clip, 6=max_clip.
        """
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(
            notify_calls=notify_calls,
            slider_values={5: 45, 6: 10},
        )

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            save_cb = next(
                (v for k, v in captured.items() if "Save Settings" in k), None
            )
            assert save_cb is not None, f"Save callback missing; keys={list(captured)}"
            await save_cb()  # type: ignore[operator]

        assert any(
            "max" in str(a).lower() for a, _kw in notify_calls
        ), f"Expected max-clip error notify; got: {notify_calls}"

    async def test_save_invalid_font_color_shows_error(
        self, tmp_path: Path
    ) -> None:
        """save() notifies an error for an invalid font color hex (lines 262-267)."""
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(
            notify_calls=notify_calls,
            color_overrides={"Font Color": "NOTAHEX"},
        )

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            save_cb = next(
                (v for k, v in captured.items() if "Save Settings" in k), None
            )
            assert save_cb is not None
            await save_cb()  # type: ignore[operator]

        assert any(
            "font color" in str(a).lower() for a, _kw in notify_calls
        ), f"Expected font-color error notify; got: {notify_calls}"

    async def test_save_invalid_stroke_color_shows_error(
        self, tmp_path: Path
    ) -> None:
        """save() notifies an error for an invalid stroke color hex (lines 269-273)."""
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(
            notify_calls=notify_calls,
            color_overrides={"Stroke Color": "BADHEX"},
        )

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            save_cb = next(
                (v for k, v in captured.items() if "Save Settings" in k), None
            )
            assert save_cb is not None
            await save_cb()  # type: ignore[operator]

        assert any(
            "stroke" in str(a).lower() for a, _kw in notify_calls
        ), f"Expected stroke-color error notify; got: {notify_calls}"

    async def test_save_success_calls_save_prefs_and_notifies(
        self, tmp_path: Path
    ) -> None:
        """save() calls save_prefs and notifies success (lines 276-292)."""
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(notify_calls=notify_calls)
        mock_save = AsyncMock()

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
            patch("src.pages.settings.save_prefs", new=mock_save),
        ):
            await settings_mod.render()
            save_cb = next(
                (v for k, v in captured.items() if "Save Settings" in k), None
            )
            assert save_cb is not None
            await save_cb()  # type: ignore[operator]

        mock_save.assert_awaited_once()
        assert any(
            "saved" in str(a).lower() for a, _kw in notify_calls
        ), f"Expected saved notify; got: {notify_calls}"

    async def test_reset_restores_defaults_and_notifies(
        self, tmp_path: Path
    ) -> None:
        """reset() sets widget values back to defaults (lines 296-309)."""
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(notify_calls=notify_calls)

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            reset_cb = next(
                (v for k, v in captured.items() if "Reset" in k), None
            )
            assert reset_cb is not None, (
                f"Reset callback missing; keys={list(captured)}"
            )
            reset_cb()  # type: ignore[operator]

        assert any(
            "reset" in str(a).lower() or "default" in str(a).lower()
            for a, _kw in notify_calls
        ), f"Expected reset notify; got: {notify_calls}"

    async def test_clear_logo_resets_state(self, tmp_path: Path) -> None:
        """clear_logo() clears logo_state and updates logo_display (lines 235-237)."""
        import src.pages.settings as settings_mod

        prefs = _make_default_prefs()
        prefs.logo_path = "/tmp/logo/brand.png"
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock()

        with (
            patch(
                "src.pages.settings.load_prefs", new=AsyncMock(return_value=prefs)
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            clear_cb = next(
                (v for k, v in captured.items() if "Clear Logo" in k), None
            )
            assert clear_cb is not None, (
                f"Clear Logo callback missing; keys={list(captured)}"
            )
            clear_cb()  # type: ignore[operator]

    async def test_handle_logo_upload_none_content_notifies(
        self, tmp_path: Path
    ) -> None:
        """handle_logo_upload with None content calls ui.notify (lines 216-218)."""
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(notify_calls=notify_calls)

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            upload_cb = captured.get("on_upload")
            assert upload_cb is not None, "on_upload callback was not captured"

            bad_event = MagicMock()
            bad_event.name = "broken.png"
            bad_event.content = None
            upload_cb(bad_event)  # type: ignore[operator]

        assert any(
            "failed" in str(a).lower() or "no content" in str(a).lower()
            for a, _kw in notify_calls
        ), f"Expected upload-failed notify; got: {notify_calls}"

    async def test_handle_logo_upload_success_writes_file(
        self, tmp_path: Path
    ) -> None:
        """handle_logo_upload writes bytes to temp_dir/logo/ (lines 220-226)."""
        import src.pages.settings as settings_mod

        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock()

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
        ):
            await settings_mod.render()
            upload_cb = captured.get("on_upload")
            assert upload_cb is not None

            good_event = MagicMock()
            good_event.name = "logo.png"
            good_event.content = BytesIO(b"fake-image-bytes")
            upload_cb(good_event)  # type: ignore[operator]

        expected = tmp_path / "logo" / "logo.png"
        assert expected.exists()
        assert expected.read_bytes() == b"fake-image-bytes"


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
    is itself a MagicMock whose .classes(), .props(), and
    __enter__/__exit__ context manager methods all return mocks so
    that with ui.column(): blocks execute without error.
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
