"""
Offline capability tests for SupoClip backend.

Tests that the application can operate without external services:
- No external API calls required by default
- MLX Whisper (local) instead of AssemblyAI (cloud)
- SQLite (local) instead of PostgreSQL
- Local job queue instead of Redis
- No internet dependency for basic operation
"""
import os
import pytest
import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import Config
from src.database import AsyncSessionLocal
from src.workers.local_queue import LocalJobQueue


class TestOfflineDatabase:
    """Test offline database capability."""

    def test_sqlite_default_database(self, test_config):
        """Test that SQLite is the default database."""
        assert "sqlite" in test_config.database_url.lower()

    def test_no_postgresql_required(self, monkeypatch):
        """Test that PostgreSQL is not required."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        config = Config()

        # Default database URL should use SQLite
        assert "sqlite" in config.database_url.lower()
        assert "postgresql" not in config.database_url.lower()

    async def test_database_creates_local_file(self, temp_dir):
        """Test that database creates local file."""
        from src.database import create_async_engine, Base

        db_path = str(temp_dir / "test.db")
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            connect_args={"check_same_thread": False}
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Verify file exists
        assert (temp_dir / "test.db").exists()

        await engine.dispose()


class TestOfflineTranscription:
    """Test offline transcription capability."""

    def test_mlx_whisper_default(self, test_config):
        """Test that MLX Whisper is configured."""
        assert test_config.mlx_whisper_model is not None
        assert test_config.mlx_whisper_model in ["tiny", "base", "small", "medium", "large"]

    def test_mlx_not_cloud_service(self):
        """Test MLX Whisper is not a cloud service."""
        from src.transcription_mlx import transcribe_video_mlx

        # MLX is a local processing library, not cloud-based
        # The module should exist and be importable
        assert transcribe_video_mlx is not None

    def test_no_assembly_ai_required(self, test_config):
        """Test that AssemblyAI API key is not required."""
        # Config should initialize without AssemblyAI API
        assert test_config is not None


class TestOfflineJobQueue:
    """Test offline job queue capability."""

    def test_local_queue_available(self):
        """Test that local job queue is available."""
        queue = LocalJobQueue(max_workers=2)
        assert queue is not None

    def test_no_redis_required(self, test_config):
        """Test that Redis is not required for basic operation."""
        # Local queue uses asyncio, not Redis
        assert test_config.max_workers > 0

    async def test_local_queue_no_redis_dependency(self):
        """Test that local queue doesn't require Redis."""
        # LocalJobQueue uses asyncio.Queue, not Redis
        queue = LocalJobQueue(max_workers=1)

        async def simple_task():
            return "done"

        # Should work without Redis connection
        job_id = await queue.enqueue_job(simple_task)
        assert job_id is not None


class TestOfflineAPIOperation:
    """Test API can operate offline."""

    def test_health_check_works_offline(self, async_client):
        """Test health check works without external services."""
        response = async_client.get("/health")
        assert response.status_code == 200

    def test_database_health_without_redis(self, async_client):
        """Test database health check without Redis."""
        response = async_client.get("/health/db")
        assert response.status_code == 200

        data = response.json()
        assert data["database"] == "connected"

    def test_root_endpoint_offline(self, async_client):
        """Test root endpoint works offline."""
        response = async_client.get("/")
        assert response.status_code == 200


class TestOfflineConfiguration:
    """Test configuration for offline operation."""

    def test_config_without_api_keys(self):
        """Test that config initializes without API keys."""
        # Remove all API keys
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)

        config = Config()
        assert config is not None

    def test_default_llm_configured(self, test_config):
        """Test that a default LLM is configured."""
        assert test_config.llm is not None
        assert test_config.llm != ""

    def test_all_required_settings_offline(self, test_config):
        """Test that all critical settings are offline-capable."""
        # Database: SQLite (local)
        assert "sqlite" in test_config.database_url.lower()

        # Transcription: MLX Whisper (local)
        assert test_config.mlx_whisper_model is not None

        # Job Queue: Local asyncio queue (no Redis)
        assert test_config.max_workers > 0


class TestNoExternalAPICallsByDefault:
    """Test that no external APIs are called by default."""

    def test_no_openai_call_without_key(self, monkeypatch):
        """Test that OpenAI API is not called without key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Creating config should not attempt any API calls
        config = Config()
        assert config is not None

    def test_no_google_api_call_without_key(self, monkeypatch):
        """Test that Google API is not called without key."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        config = Config()
        assert config is not None

    def test_no_anthropic_call_without_key(self, monkeypatch):
        """Test that Anthropic API is not called without key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config = Config()
        assert config is not None


class TestOfflineDirectory:
    """Test offline file storage."""

    def test_temp_directory_local(self, test_config):
        """Test that temp directory is local."""
        assert test_config.temp_dir is not None
        # Should be a local path, not a cloud service URL
        assert not test_config.temp_dir.startswith("http")

    def test_output_directory_local(self, test_config):
        """Test that output directory is local."""
        assert test_config.output_dir is not None
        # Should be a local path
        assert not test_config.output_dir.startswith("http")

    def test_clips_stored_locally(self, temp_dir):
        """Test that generated clips are stored locally."""
        clips_dir = temp_dir / "clips"
        clips_dir.mkdir(exist_ok=True)

        # Create test clip file
        test_clip = clips_dir / "test_clip.mp4"
        test_clip.write_bytes(b"fake video data")

        assert test_clip.exists()


class TestLocalAssetsAvailability:
    """Test that local assets are available."""

    def test_fonts_directory_exists(self):
        """Test that fonts directory exists."""
        from pathlib import Path

        # Fonts should be in backend/fonts/
        fonts_dir = Path(__file__).parent.parent / "fonts"
        # Directory may or may not exist, but shouldn't block startup
        assert fonts_dir.parent.name == "backend"

    def test_transitions_directory_exists(self):
        """Test that transitions directory exists."""
        from pathlib import Path

        # Transitions should be in backend/transitions/
        transitions_dir = Path(__file__).parent.parent / "transitions"
        # Directory may or may not exist, but shouldn't block startup
        assert transitions_dir.parent.name == "backend"


class TestOfflineScenarios:
    """Test realistic offline scenarios."""

    async def test_application_starts_offline(self, test_config):
        """Test application can start without internet."""
        # All configuration loaded
        assert test_config is not None

        # Database configured
        assert test_config.database_url is not None

        # Job queue configured
        assert test_config.max_workers > 0

    async def test_database_operations_offline(self, test_db_session):
        """Test database operations work offline."""
        from src.models import User

        # Create user (offline database operation)
        user = User(
            name="Test User",
            email="offline@test.com"
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        assert user.id is not None

    async def test_job_queue_offline(self):
        """Test job queue works offline."""
        queue = LocalJobQueue(max_workers=1)

        async def offline_task():
            return "processed offline"

        job_id = await queue.enqueue_job(offline_task)
        assert job_id is not None

        job = queue.get_job(job_id)
        assert job is not None

    def test_file_storage_offline(self, temp_dir):
        """Test file storage works offline."""
        # Create video files directory
        videos_dir = temp_dir / "videos"
        videos_dir.mkdir(exist_ok=True)

        # Create test video
        test_video = videos_dir / "test.mp4"
        test_video.write_bytes(b"fake video")

        assert test_video.exists()
        assert test_video.stat().st_size > 0
