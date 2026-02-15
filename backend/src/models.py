# start backend/src/models.py
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Boolean,
    Float,
    Integer,
    Text,
    text,
    JSON,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import uuid

from .database import Base


def generate_uuid_string():
    """Generate a UUID as a string for compatibility with Prisma"""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid_string
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    emailVerified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=func.now(),
    )

    # Additional fields for backend compatibility
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Default font preferences
    default_font_family: Mapped[str | None] = mapped_column(
        String(100), nullable=True, server_default=text("'TikTokSans-Regular'")
    )
    default_font_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("'24'")
    )
    default_font_color: Mapped[str | None] = mapped_column(
        String(7), nullable=True, server_default=text("'#FFFFFF'")
    )

    # Clip length preferences
    default_clip_min_length: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("'10'")
    )
    default_clip_target_length: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("'30'")
    )
    default_clip_max_length: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("'45'")
    )

    # Custom AI prompt
    custom_ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Logo branding preferences
    logo_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_corner_position: Mapped[str | None] = mapped_column(
        String(20), nullable=True, server_default=text("'top-right'")
    )
    output_resolution: Mapped[str | None] = mapped_column(
        String(10), nullable=True, server_default=text("'720p'")
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "logo_corner_position IN ('top-left', 'top-right', 'bottom-left', 'bottom-right')",
            name="check_logo_corner_position",
        ),
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="user", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid_string
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    # Use JSON for SQLite compatibility (works with both SQLite and PostgreSQL)
    generated_clips_ids: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )

    # Font customization fields
    font_family: Mapped[str | None] = mapped_column(
        String(100), nullable=True, server_default=text("'TikTokSans-Regular'")
    )
    font_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("'24'")
    )
    font_color: Mapped[str | None] = mapped_column(
        String(7), nullable=True, server_default=text("'#FFFFFF'")
    )  # Hex color code

    # Progress tracking fields
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("'0'")
    )
    progress_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")
    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="tasks")
    generated_clips: Mapped[list["GeneratedClip"]] = relationship(
        "GeneratedClip", back_populates="task", cascade="all, delete-orphan"
    )
    output_resolution: Mapped[str | None] = mapped_column(
        String(10), nullable=True, server_default=text("'720p'")
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid_string
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Add check constraint for type enum
    __table_args__ = (
        CheckConstraint(
            "type IN ('youtube', 'video_url', 'upload')", name="check_source_type"
        ),
    )

    # Relationships - Source can have multiple tasks
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="source")

    def decide_source_type(self, source_url: str) -> str:
        """Decide which type of source this is."""
        if "youtube" in source_url:
            return "youtube"
        return "video_url"


class GeneratedClip(Base):
    __tablename__ = "generated_clips"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid_string
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    start_time: Mapped[str] = mapped_column(String(20), nullable=False)  # MM:SS format
    end_time: Mapped[str] = mapped_column(String(20), nullable=False)  # MM:SS format
    duration: Mapped[float] = mapped_column(
        Float, nullable=False
    )  # Duration in seconds
    text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Transcript text for this clip
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # AI reasoning for selection
    clip_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Order within the task
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="generated_clips")


class SystemFont(Base):
    __tablename__ = "system_fonts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid_string
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    family: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'normal', 'italic', etc.
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 100, 400, 700, etc.
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detection_timestamp: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # ISO8601 string
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'bundled' or 'system'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('bundled', 'system')", name="check_system_fonts_source"
        ),
    )

# end backend/src/models.py
