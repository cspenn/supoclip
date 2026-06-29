# start src/models.py
"""SQLAlchemy ORM models for SupoClip.

Three tables only — all Better Auth / User / Source / SystemFont complexity removed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db_base import Base


def _new_uuid() -> str:
    """Generate a fresh UUID4 as a plain string.

    Returns:
        UUID string in canonical 8-4-4-4-12 form.
    """
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Return the current UTC time.

    Returns:
        Current UTC datetime (timezone-aware).
    """
    return datetime.now(UTC)


class Task(Base):
    """A video processing job submitted by the user.

    Tracks the lifecycle of processing a single source video from intake
    through transcription, AI analysis, and clip generation.

    Attributes:
        id: UUID primary key.
        source_url: YouTube URL or uploaded filename.
        source_type: One of ``'youtube'`` or ``'upload'``.
        status: One of ``'pending'``, ``'processing'``, ``'completed'``, ``'failed'``.
        progress: Integer 0-100 representing completion percentage.
        progress_message: Human-readable status message (nullable).
        settings_json: JSON blob of processing settings used (nullable).
        error_message: Error detail when status is ``'failed'`` (nullable).
        created_at: UTC datetime when the row was created.
        updated_at: UTC datetime of the last update.
        clips: Related GeneratedClip rows (cascade delete).
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'youtube'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    progress_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    clips: Mapped[list["GeneratedClip"]] = relationship("GeneratedClip", back_populates="task", cascade="all, delete-orphan")


class GeneratedClip(Base):
    """A short clip produced from a Task source video.

    Stores metadata about each generated clip including timing, AI scoring,
    and the filename used to serve the clip from the static file directory.

    Attributes:
        id: UUID primary key.
        task_id: Foreign key to the parent Task (CASCADE delete).
        filename: Clip filename served from ``TEMP_DIR/clips/``.
        start_time: Start offset in the source video (seconds).
        end_time: End offset in the source video (seconds).
        duration: Computed length ``end_time - start_time`` (seconds).
        title: Clip title suggested by the AI (nullable).
        transcript_text: Verbatim transcript words for this clip (nullable).
        score: AI relevance score 0.0-1.0 (nullable).
        created_at: UTC datetime when the row was created.
        task: Back-reference to the parent Task.
    """

    __tablename__ = "generated_clips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="clips")


class UserPreferences(Base):
    """Singleton row storing the user's global application preferences.

    There is always exactly one row with ``id = 1``. Callers should use
    ``session.get(UserPreferences, 1)`` and create the row if absent.

    Attributes:
        id: Always 1 — enforces singleton pattern.
        font_family: Font face for generated subtitles.
        font_size: Subtitle font size in points.
        font_color: Subtitle text colour as hex (e.g. ``'#FFFFFF'``).
        font_stroke_color: Subtitle stroke colour as hex.
        font_stroke_width: Stroke width in pixels.
        font_shadow_offset: Drop-shadow offset in pixels.
        subtitle_position_y: Vertical subtitle position as a percentage from top.
        min_clip_length: Minimum acceptable clip length in seconds.
        max_clip_length: Maximum acceptable clip length in seconds.
        output_resolution: Target resolution string (e.g. ``'1080p'``).
        ai_prompt: Custom system prompt to override the default AI prompt (nullable).
        logo_path: Filesystem path to the branding logo (nullable).
        updated_at: UTC datetime of the last update.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    font_family: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'Arial'"))
    font_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("24"))
    font_color: Mapped[str] = mapped_column(String(7), nullable=False, server_default=text("'#FFFFFF'"))
    font_stroke_color: Mapped[str] = mapped_column(String(7), nullable=False, server_default=text("'#000000'"))
    font_stroke_width: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("2.0"))
    font_shadow_offset: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    subtitle_position_y: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("75"))
    min_clip_length: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("15"))
    max_clip_length: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("45"))
    output_resolution: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'1080p'"))
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


# end src/models.py
