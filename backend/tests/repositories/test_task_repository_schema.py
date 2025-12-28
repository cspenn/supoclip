"""
Test suite to verify database schema includes progress and progress_message columns.

These tests validate that the schema migration was successful and
progress tracking fields work correctly.
"""
import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, User
from src.repositories.task_repository import TaskRepository


@pytest.fixture
async def test_db():
    """Create a test database with the current schema."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    # Create tables using current schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(test_db: AsyncSession):
    """Create a test user."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        name="Test User",
        email="test@example.com",
        emailVerified=False
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_task_creation_without_progress(test_db: AsyncSession, test_user: User):
    """
    Test that task creation works (doesn't use progress columns).

    This test SHOULD PASS - it validates that basic task creation still works.
    """
    source_id = str(uuid.uuid4())

    # Create task without progress fields
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    assert task_id is not None
    assert len(task_id) == 36  # UUID format

    # Verify task was created
    task = await TaskRepository.get_task_by_id(test_db, task_id)
    assert task is not None
    assert task["status"] == "queued"
    assert task["user_id"] == test_user.id


@pytest.mark.asyncio
async def test_task_status_update_with_progress_succeeds(test_db: AsyncSession, test_user: User):
    """
    Test that task status update with progress works correctly.

    Validates that the schema includes progress and progress_message columns.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Update with progress - this should succeed now
    await TaskRepository.update_task_status(
        db=test_db,
        task_id=task_id,
        status="processing",
        progress=50,
        progress_message="Processing video..."
    )

    # Verify the update
    task = await TaskRepository.get_task_by_id(test_db, task_id)
    assert task is not None
    assert task["status"] == "processing"
    assert task["progress"] == 50
    assert task["progress_message"] == "Processing video..."


@pytest.mark.asyncio
async def test_task_status_update_with_progress_message_only_succeeds(test_db: AsyncSession, test_user: User):
    """
    Test error handler pattern: update status with progress_message.

    This pattern is used by error handlers to store error messages.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Update with progress_message (error handler pattern)
    await TaskRepository.update_task_status(
        db=test_db,
        task_id=task_id,
        status="error",
        progress_message="An error occurred"
    )

    # Verify the update
    task = await TaskRepository.get_task_by_id(test_db, task_id)
    assert task is not None
    assert task["status"] == "error"
    assert task["progress_message"] == "An error occurred"


@pytest.mark.asyncio
async def test_task_get_returns_default_progress_values(test_db: AsyncSession, test_user: User):
    """
    Test that reading tasks returns default progress values.

    Progress defaults to 0, progress_message defaults to None.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Get task - should return default values for progress fields
    task = await TaskRepository.get_task_by_id(test_db, task_id)

    assert task is not None
    assert task["id"] == task_id
    assert task["status"] == "queued"

    # Progress defaults to 0, progress_message defaults to None
    assert task["progress"] == 0, "Progress should default to 0"
    assert task["progress_message"] is None, "Progress message should default to None"


@pytest.mark.asyncio
async def test_multiple_progress_updates_work(test_db: AsyncSession, test_user: User):
    """
    Test that multiple progress updates work correctly.

    Validates that database connections are properly managed during updates.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Perform multiple updates
    for i in range(5):
        await TaskRepository.update_task_status(
            db=test_db,
            task_id=task_id,
            status="processing",
            progress=i * 20,
            progress_message=f"Step {i + 1}"
        )

    # Session should still be usable
    task = await TaskRepository.get_task_by_id(test_db, task_id)
    assert task is not None, "Session should still work after updates"
    assert task["status"] == "processing"
    assert task["progress"] == 80  # Last update was 4 * 20
    assert task["progress_message"] == "Step 5"
