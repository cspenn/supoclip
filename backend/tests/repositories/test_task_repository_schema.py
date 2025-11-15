"""
Test suite to reproduce database schema mismatch issues.

This test SHOULD FAIL until the database schema is fixed to include
progress and progress_message columns.

Expected failure: sqlite3.OperationalError: no such column: progress
"""
import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from src.models import Base, User, Task
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
async def test_task_status_update_with_progress_fails(test_db: AsyncSession, test_user: User):
    """
    Reproduces: Task status update with progress fails due to missing column.

    Expected: Update should set status, progress, and progress_message
    Actual: Fails with "no such column: progress"

    This test SHOULD FAIL until the schema is fixed.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Attempt to update with progress - THIS SHOULD FAIL
    with pytest.raises(OperationalError) as exc_info:
        await TaskRepository.update_task_status(
            db=test_db,
            task_id=task_id,
            status="processing",
            progress=0,
            progress_message="Starting..."
        )

    # Verify the specific error
    error_message = str(exc_info.value)
    assert "no such column: progress" in error_message.lower(), \
        f"Expected 'no such column: progress', got: {error_message}"


@pytest.mark.asyncio
async def test_task_status_update_with_progress_message_only_fails(test_db: AsyncSession, test_user: User):
    """
    Reproduces: Error handler fails when trying to save progress_message.

    Expected: Update should set status and progress_message (during error handling)
    Actual: Fails with "no such column: progress_message"

    This test SHOULD FAIL until the schema is fixed.
    This is critical because error handlers use this pattern!
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Attempt to update with only progress_message (error handler pattern)
    with pytest.raises(OperationalError) as exc_info:
        await TaskRepository.update_task_status(
            db=test_db,
            task_id=task_id,
            status="error",
            progress_message="An error occurred"
        )

    # Verify the specific error
    error_message = str(exc_info.value)
    assert "no such column: progress_message" in error_message.lower(), \
        f"Expected 'no such column: progress_message', got: {error_message}"


@pytest.mark.asyncio
async def test_task_get_with_progress_gracefully_handles_missing_columns(test_db: AsyncSession, test_user: User):
    """
    Test that reading tasks gracefully handles missing progress columns.

    The repository uses getattr() with defaults, so reads should work.
    This test SHOULD PASS even with missing columns.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Get task - should return None for progress fields
    task = await TaskRepository.get_task_by_id(test_db, task_id)

    assert task is not None
    assert task["id"] == task_id
    assert task["status"] == "queued"

    # These should be None due to getattr() defaults
    assert task["progress"] is None, "Should gracefully return None for missing progress"
    assert task["progress_message"] is None, "Should gracefully return None for missing progress_message"


@pytest.mark.asyncio
async def test_connection_cleanup_after_failed_update(test_db: AsyncSession, test_user: User):
    """
    Test that database connections are properly cleaned up after failed updates.

    This validates hypothesis #2 - that failed transactions should still clean up properly.
    """
    source_id = str(uuid.uuid4())

    # Create a task
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Attempt multiple failed updates
    for i in range(5):
        try:
            await TaskRepository.update_task_status(
                db=test_db,
                task_id=task_id,
                status="processing",
                progress=i * 10,
                progress_message=f"Step {i}"
            )
        except OperationalError:
            # Expected to fail
            pass

    # Session should still be usable for other operations
    # This verifies connections aren't leaked
    task = await TaskRepository.get_task_by_id(test_db, task_id)
    assert task is not None, "Session should still work after failed updates"
    assert task["status"] == "queued", "Status should be unchanged"
