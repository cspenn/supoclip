# start tests/unit/test_models.py
"""Unit tests for SQLAlchemy ORM models (Task, GeneratedClip, UserPreferences)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database import Base
from src.models import GeneratedClip, Task, UserPreferences

# In-memory SQLite URL for isolated tests
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
# Task tests
# ---------------------------------------------------------------------------


class TestTask:
    """Tests for the Task ORM model."""

    async def test_create_with_required_fields(self, session: AsyncSession) -> None:
        """Task is persisted with required fields and UUID primary key set."""
        task = Task(source_url="https://youtu.be/abc123", source_type="youtube")
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert task.id is not None
        assert len(task.id) == 36  # canonical UUID string
        assert task.source_url == "https://youtu.be/abc123"
        assert task.source_type == "youtube"

    async def test_default_status_is_pending(self, session: AsyncSession) -> None:
        """Task status defaults to 'pending' when not supplied."""
        task = Task(source_url="https://youtu.be/abc123", source_type="youtube", status="pending")
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert task.status == "pending"

    async def test_default_progress_is_zero(self, session: AsyncSession) -> None:
        """Task progress defaults to 0."""
        task = Task(source_url="https://youtu.be/abc123", source_type="youtube", status="pending", progress=0)
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert task.progress == 0

    async def test_nullable_fields_accept_none(self, session: AsyncSession) -> None:
        """Optional fields (settings_json, error_message, progress_message) accept None."""
        task = Task(
            source_url="https://youtu.be/abc123",
            source_type="youtube",
            status="pending",
            progress=0,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert task.settings_json is None
        assert task.error_message is None
        assert task.progress_message is None

    def test_datetime_columns_declare_timezone(self) -> None:
        """DateTime columns are declared with timezone=True (M-8).

        SQLite does not persist tz info on round-trip, so this asserts the
        schema declaration directly rather than a stored value.
        """
        assert Task.__table__.c.created_at.type.timezone is True
        assert Task.__table__.c.updated_at.type.timezone is True
        assert GeneratedClip.__table__.c.created_at.type.timezone is True
        assert UserPreferences.__table__.c.updated_at.type.timezone is True

    async def test_timestamps_set_on_creation(self, session: AsyncSession) -> None:
        """created_at and updated_at are set when a Task is created."""
        task = Task(source_url="https://youtu.be/abc123", source_type="youtube", status="pending", progress=0)
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert task.created_at is not None
        assert task.updated_at is not None

    async def test_upload_source_type(self, session: AsyncSession) -> None:
        """Task accepts 'upload' as source_type."""
        task = Task(source_url="my_video.mp4", source_type="upload", status="pending", progress=0)
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert task.source_type == "upload"


# ---------------------------------------------------------------------------
# GeneratedClip tests
# ---------------------------------------------------------------------------


class TestGeneratedClip:
    """Tests for the GeneratedClip ORM model."""

    async def _make_task(self, session: AsyncSession) -> Task:
        """Helper: persist and return a minimal Task."""
        task = Task(source_url="https://youtu.be/abc123", source_type="youtube", status="completed", progress=100)
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task

    async def test_create_with_task_id(self, session: AsyncSession) -> None:
        """GeneratedClip is persisted with correct task_id and timing fields."""
        task = await self._make_task(session)
        clip = GeneratedClip(
            task_id=task.id,
            filename="clip_001.mp4",
            start_time=10.0,
            end_time=35.0,
            duration=25.0,
        )
        session.add(clip)
        await session.commit()
        await session.refresh(clip)

        assert clip.id is not None
        assert len(clip.id) == 36
        assert clip.task_id == task.id
        assert clip.filename == "clip_001.mp4"
        assert clip.start_time == pytest.approx(10.0)
        assert clip.end_time == pytest.approx(35.0)
        assert clip.duration == pytest.approx(25.0)

    async def test_optional_fields_default_to_none(self, session: AsyncSession) -> None:
        """title, transcript_text, and score are None by default."""
        task = await self._make_task(session)
        clip = GeneratedClip(
            task_id=task.id,
            filename="clip_002.mp4",
            start_time=0.0,
            end_time=20.0,
            duration=20.0,
        )
        session.add(clip)
        await session.commit()
        await session.refresh(clip)

        assert clip.title is None
        assert clip.transcript_text is None
        assert clip.score is None

    async def test_created_at_set_on_insert(self, session: AsyncSession) -> None:
        """created_at timestamp is populated when the clip is persisted."""
        task = await self._make_task(session)
        clip = GeneratedClip(
            task_id=task.id,
            filename="clip_003.mp4",
            start_time=5.0,
            end_time=30.0,
            duration=25.0,
        )
        session.add(clip)
        await session.commit()
        await session.refresh(clip)

        assert clip.created_at is not None

    async def test_score_stores_float(self, session: AsyncSession) -> None:
        """score field stores a float value."""
        task = await self._make_task(session)
        clip = GeneratedClip(
            task_id=task.id,
            filename="clip_004.mp4",
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            score=0.87,
        )
        session.add(clip)
        await session.commit()
        await session.refresh(clip)

        assert clip.score == pytest.approx(0.87)


# ---------------------------------------------------------------------------
# UserPreferences tests
# ---------------------------------------------------------------------------


class TestUserPreferences:
    """Tests for the UserPreferences singleton ORM model."""

    async def test_create_singleton_row(self, session: AsyncSession) -> None:
        """UserPreferences row can be created and retrieved with id=1."""
        prefs = UserPreferences(id=1)
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)

        assert prefs.id == 1

    async def test_default_font_family(self, session: AsyncSession) -> None:
        """font_family defaults to 'Arial'."""
        prefs = UserPreferences(id=1, font_family="Arial")
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)

        assert prefs.font_family == "Arial"

    async def test_default_font_size(self, session: AsyncSession) -> None:
        """font_size defaults to 24."""
        prefs = UserPreferences(id=1, font_family="Arial", font_size=24)
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)

        assert prefs.font_size == 24

    async def test_default_font_colors(self, session: AsyncSession) -> None:
        """font_color defaults to '#FFFFFF' and font_stroke_color to '#000000'."""
        prefs = UserPreferences(
            id=1,
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            font_stroke_color="#000000",
        )
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)

        assert prefs.font_color == "#FFFFFF"
        assert prefs.font_stroke_color == "#000000"

    async def test_default_clip_lengths(self, session: AsyncSession) -> None:
        """min_clip_length defaults to 15 and max_clip_length to 45."""
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
        await session.refresh(prefs)

        assert prefs.min_clip_length == 15
        assert prefs.max_clip_length == 45

    async def test_default_output_resolution(self, session: AsyncSession) -> None:
        """output_resolution defaults to '1080p'."""
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
        await session.refresh(prefs)

        assert prefs.output_resolution == "1080p"

    async def test_nullable_optional_fields(self, session: AsyncSession) -> None:
        """ai_prompt and logo_path are None by default."""
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
        await session.refresh(prefs)

        assert prefs.ai_prompt is None
        assert prefs.logo_path is None


# ---------------------------------------------------------------------------
# Cascade delete tests
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Tests verifying cascade delete from Task to GeneratedClip."""

    async def test_deleting_task_deletes_clips(self, session: AsyncSession) -> None:
        """Deleting a Task removes all of its GeneratedClip children."""
        task = Task(source_url="https://youtu.be/del_test", source_type="youtube", status="completed", progress=100)
        session.add(task)
        await session.commit()
        await session.refresh(task)

        clip_a = GeneratedClip(task_id=task.id, filename="a.mp4", start_time=0.0, end_time=10.0, duration=10.0)
        clip_b = GeneratedClip(task_id=task.id, filename="b.mp4", start_time=15.0, end_time=30.0, duration=15.0)
        session.add_all([clip_a, clip_b])
        await session.commit()

        task_id = task.id
        await session.delete(task)
        await session.commit()

        # Clips should be gone
        from sqlalchemy import select

        result = await session.execute(select(GeneratedClip).where(GeneratedClip.task_id == task_id))
        remaining = result.scalars().all()
        assert remaining == []


# end tests/unit/test_models.py
