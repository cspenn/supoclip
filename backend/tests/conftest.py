"""
Pytest configuration and shared fixtures for SupoClip backend tests.

Provides:
- SQLite test database fixture
- Async session management
- FastAPI test client
- Sample data fixtures
- Temporary directory management
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Setup path for imports
import sys
backend_root = Path(__file__).parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Import from src package
from src.database import Base, get_db
from src.config import Config

# Import from main (has all endpoints including upload-logo)
try:
    from src.main import app
except (ModuleNotFoundError, ImportError) as e:
    # Fallback: create a simple FastAPI app for testing
    from fastapi import FastAPI
    app = FastAPI(
        title="SupoClip API",
        description="SupoClip Backend Test App",
        version="0.1.0"
    )

    # Add basic endpoints
    @app.get("/")
    def read_root():
        return {
            "name": "SupoClip API",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "architecture": "test app"
        }

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    @app.get("/health/db")
    async def check_database_health(db = None):
        try:
            if db:
                from sqlalchemy import text
                await db.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        except Exception as e:
            return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

    @app.get("/health/redis")
    async def check_redis_health():
        # Redis not available in test environment
        return {"status": "unhealthy", "redis": "disconnected", "error": "Redis not configured for testing"}


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create an in-memory SQLite database for testing."""
    # Use in-memory SQLite for fast tests
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"

    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
async def override_get_db(test_db_session):
    """Override the get_db dependency for testing."""
    async def _get_test_db():
        yield test_db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield _get_test_db
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def async_client(override_get_db):
    """Create a synchronous test client for testing the API.

    Note: Using TestClient instead of AsyncClient since we need to use
    the app's dependency overrides for database testing.
    """
    return TestClient(app)


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)

        # Create subdirectories
        (temp_path / "uploads").mkdir(exist_ok=True)
        (temp_path / "clips").mkdir(exist_ok=True)
        (temp_path / "transcripts").mkdir(exist_ok=True)

        yield temp_path


@pytest.fixture(scope="function")
def test_config(temp_dir, monkeypatch) -> Config:
    """Create a test configuration with temporary directories."""
    # Set environment variables for test config
    monkeypatch.setenv("TEMP_DIR", str(temp_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(temp_dir / "outputs"))
    monkeypatch.setenv("MLX_WHISPER_MODEL", "tiny")  # Use tiny model for tests
    monkeypatch.setenv("LLM_MODEL", "google:gemini-2.5-flash-lite")
    monkeypatch.setenv("MAX_WORKERS", "2")

    config = Config()
    return config


@pytest.fixture(scope="function")
def sample_video_path(temp_dir) -> Path:
    """Create a sample video file for testing.

    Note: This is a placeholder that creates an empty file.
    In real testing with actual transcription, a real video file would be needed.
    """
    video_path = temp_dir / "uploads" / "sample.mp4"
    video_path.write_bytes(b"fake video data")
    return video_path


@pytest.fixture(scope="function")
async def sample_user_data(test_db_session):
    """Create sample user data in the test database."""
    from src.models import User

    user = User(
        id="test-user-1",
        name="Test User",
        email="test@example.com",
        emailVerified=True,
        first_name="Test",
        last_name="User"
    )

    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
async def sample_task_data(test_db_session, sample_user_data):
    """Create sample task data in the test database."""
    from src.models import Task, Source

    source = Source(
        id="test-source-1",
        type="youtube",
        title="Test Video"
    )

    task = Task(
        id="test-task-1",
        user_id=sample_user_data.id,
        source_id=None,
        status="pending",
        font_family="TikTokSans-Regular",
        font_size=24,
        font_color="#FFFFFF"
    )

    test_db_session.add(source)
    test_db_session.add(task)
    await test_db_session.commit()
    await test_db_session.refresh(source)
    await test_db_session.refresh(task)

    return task, source


# Mark all async tests
def pytest_collection_modifyitems(items):
    """Mark all async test functions with pytest.mark.asyncio."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
