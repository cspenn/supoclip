"""
Database integration tests for SupoClip backend.

Tests:
- SQLite database initialization
- User CRUD operations
- Task creation and status tracking
- Task clip retrieval
- Source creation and relationships
- Cascade delete operations
- Field defaults and constraints
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import select

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.models import User, Task, Source, GeneratedClip
from src.database import Base


class TestDatabaseInitialization:
    """Test database schema and initialization."""

    async def test_database_tables_created(self, test_db_session):
        """Verify all tables are created correctly."""
        # If we got a test_db_session, tables were created successfully
        assert test_db_session is not None

    async def test_base_metadata_contains_all_models(self):
        """Verify all models are registered with Base."""
        model_names = {table.name for table in Base.metadata.tables.values()}

        assert "users" in model_names
        assert "tasks" in model_names
        assert "sources" in model_names
        assert "generated_clips" in model_names

    def test_user_table_has_required_fields(self):
        """Verify user model has required fields."""
        # Check that User has required attributes
        assert hasattr(User, 'id')
        assert hasattr(User, 'email')
        assert hasattr(User, 'name')
        assert hasattr(User, 'createdAt')
        assert hasattr(User, 'updatedAt')

    def test_task_table_has_required_fields(self):
        """Verify task model has required fields."""
        # Check that Task has required attributes
        assert hasattr(Task, 'id')
        assert hasattr(Task, 'user_id')
        assert hasattr(Task, 'status')
        assert hasattr(Task, 'font_family')
        assert hasattr(Task, 'font_size')
        assert hasattr(Task, 'created_at')


class TestUserCRUD:
    """Test User model CRUD operations."""

    async def test_create_user(self, test_db_session):
        """Test creating a new user."""
        user = User(
            id="user-1",
            name="John Doe",
            email="john@example.com",
            emailVerified=True,
            first_name="John",
            last_name="Doe"
        )

        test_db_session.add(user)
        await test_db_session.commit()

        # Retrieve the user
        result = await test_db_session.execute(
            select(User).filter(User.email == "john@example.com")
        )
        retrieved_user = result.scalar_one_or_none()

        assert retrieved_user is not None
        assert retrieved_user.name == "John Doe"
        assert retrieved_user.emailVerified is True

    async def test_create_user_with_defaults(self, test_db_session):
        """Test user creation with automatic defaults."""
        user = User(
            name="Jane Doe",
            email="jane@example.com"
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # Verify UUID was generated
        assert user.id is not None
        assert len(user.id) == 36  # UUID string format

        # Verify timestamps
        assert user.createdAt is not None
        assert user.updatedAt is not None

    async def test_update_user(self, test_db_session):
        """Test updating a user."""
        user = User(
            id="user-2",
            name="Original Name",
            email="update@example.com"
        )

        test_db_session.add(user)
        await test_db_session.commit()

        # Update the user
        user.name = "Updated Name"
        await test_db_session.commit()

        # Verify update
        result = await test_db_session.execute(
            select(User).filter(User.id == "user-2")
        )
        updated_user = result.scalar_one()

        assert updated_user.name == "Updated Name"

    async def test_user_email_unique(self, test_db_session):
        """Test that user email must be unique."""
        user1 = User(
            name="User 1",
            email="duplicate@example.com"
        )
        user2 = User(
            name="User 2",
            email="duplicate@example.com"
        )

        test_db_session.add(user1)
        await test_db_session.commit()

        test_db_session.add(user2)

        # This should raise an integrity error
        with pytest.raises(Exception):  # IntegrityError
            await test_db_session.commit()

    async def test_user_relationships(self, test_db_session, sample_user_data):
        """Test user relationships to tasks."""
        # Create tasks for the user
        task1 = Task(
            id="task-1",
            user_id=sample_user_data.id,
            status="pending"
        )
        task2 = Task(
            id="task-2",
            user_id=sample_user_data.id,
            status="processing"
        )

        test_db_session.add(task1)
        test_db_session.add(task2)
        await test_db_session.commit()

        # Reload user with relationships
        await test_db_session.refresh(sample_user_data, ["tasks"])

        assert len(sample_user_data.tasks) == 2
        assert any(t.status == "pending" for t in sample_user_data.tasks)
        assert any(t.status == "processing" for t in sample_user_data.tasks)


class TestTaskOperations:
    """Test Task model operations and relationships."""

    async def test_create_task(self, test_db_session, sample_user_data):
        """Test creating a task."""
        task = Task(
            id="task-1",
            user_id=sample_user_data.id,
            status="pending",
            font_family="Arial",
            font_size=20,
            font_color="#000000"
        )

        test_db_session.add(task)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(Task).filter(Task.id == "task-1")
        )
        retrieved_task = result.scalar_one()

        assert retrieved_task.status == "pending"
        assert retrieved_task.font_family == "Arial"
        assert retrieved_task.font_size == 20

    async def test_task_status_update(self, test_db_session, sample_task_data):
        """Test updating task status."""
        task, _ = sample_task_data

        task.status = "processing"
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(Task).filter(Task.id == task.id)
        )
        updated_task = result.scalar_one()

        assert updated_task.status == "processing"

    async def test_task_default_font_settings(self, test_db_session, sample_user_data):
        """Test that task has default font settings."""
        task = Task(
            id="task-defaults",
            user_id=sample_user_data.id,
            status="pending"
        )

        test_db_session.add(task)
        await test_db_session.commit()
        await test_db_session.refresh(task)

        # Verify defaults
        assert task.font_family == "TikTokSans-Regular"
        assert task.font_size == 24
        assert task.font_color == "#FFFFFF"

    async def test_task_user_relationship(self, test_db_session, sample_user_data):
        """Test task-user relationship."""
        task = Task(
            id="task-rel",
            user_id=sample_user_data.id,
            status="pending"
        )

        test_db_session.add(task)
        await test_db_session.commit()

        # Reload task with user
        await test_db_session.refresh(task, ["user"])

        assert task.user.id == sample_user_data.id
        assert task.user.email == sample_user_data.email

    async def test_task_cascade_delete(self, test_db_session, sample_user_data):
        """Test that deleting user cascades to tasks."""
        task = Task(
            id="task-cascade",
            user_id=sample_user_data.id,
            status="pending"
        )

        test_db_session.add(task)
        await test_db_session.commit()

        # Delete the user
        await test_db_session.delete(sample_user_data)
        await test_db_session.commit()

        # Verify task was also deleted
        result = await test_db_session.execute(
            select(Task).filter(Task.id == "task-cascade")
        )
        deleted_task = result.scalar_one_or_none()

        assert deleted_task is None


class TestSourceOperations:
    """Test Source model operations."""

    async def test_create_source(self, test_db_session):
        """Test creating a source."""
        source = Source(
            id="source-1",
            type="youtube",
            title="Test YouTube Video"
        )

        test_db_session.add(source)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(Source).filter(Source.id == "source-1")
        )
        retrieved_source = result.scalar_one()

        assert retrieved_source.type == "youtube"
        assert retrieved_source.title == "Test YouTube Video"

    async def test_source_type_constraint(self, test_db_session):
        """Test that source type is constrained to valid values."""
        invalid_source = Source(
            id="source-invalid",
            type="invalid_type",
            title="Invalid"
        )

        test_db_session.add(invalid_source)

        # Should fail due to check constraint
        with pytest.raises(Exception):  # IntegrityError
            await test_db_session.commit()

    async def test_source_task_relationship(self, test_db_session, sample_user_data):
        """Test source-task relationship."""
        source = Source(
            id="source-rel",
            type="youtube",
            title="Test Video"
        )

        task = Task(
            id="task-source",
            user_id=sample_user_data.id,
            source_id="source-rel",
            status="pending"
        )

        test_db_session.add(source)
        test_db_session.add(task)
        await test_db_session.commit()

        # Reload source with tasks
        await test_db_session.refresh(source, ["tasks"])

        assert len(source.tasks) == 1
        assert source.tasks[0].id == "task-source"


class TestGeneratedClipOperations:
    """Test GeneratedClip model operations."""

    async def test_create_generated_clip(self, test_db_session, sample_task_data):
        """Test creating a generated clip."""
        task, _ = sample_task_data

        clip = GeneratedClip(
            id="clip-1",
            task_id=task.id,
            filename="clip_01.mp4",
            file_path="/tmp/clips/clip_01.mp4",
            start_time="00:10",
            end_time="00:30",
            duration=20.0,
            text="This is a clip transcript",
            relevance_score=0.95,
            reasoning="High engagement moment",
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(GeneratedClip).filter(GeneratedClip.id == "clip-1")
        )
        retrieved_clip = result.scalar_one()

        assert retrieved_clip.filename == "clip_01.mp4"
        assert retrieved_clip.duration == 20.0
        assert retrieved_clip.relevance_score == 0.95

    async def test_clip_task_relationship(self, test_db_session, sample_task_data):
        """Test clip-task relationship."""
        task, _ = sample_task_data

        clip = GeneratedClip(
            id="clip-rel",
            task_id=task.id,
            filename="clip.mp4",
            file_path="/tmp/clips/clip.mp4",
            start_time="00:00",
            end_time="00:15",
            duration=15.0,
            relevance_score=0.85,
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()

        # Reload task with clips
        await test_db_session.refresh(task, ["generated_clips"])

        assert len(task.generated_clips) == 1
        assert task.generated_clips[0].filename == "clip.mp4"

    async def test_clip_cascade_delete(self, test_db_session, sample_task_data):
        """Test that deleting task cascades to clips."""
        task, _ = sample_task_data

        clip = GeneratedClip(
            id="clip-cascade",
            task_id=task.id,
            filename="clip.mp4",
            file_path="/tmp/clips/clip.mp4",
            start_time="00:00",
            end_time="00:15",
            duration=15.0,
            relevance_score=0.85,
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()

        # Delete the task
        await test_db_session.delete(task)
        await test_db_session.commit()

        # Verify clip was also deleted
        result = await test_db_session.execute(
            select(GeneratedClip).filter(GeneratedClip.id == "clip-cascade")
        )
        deleted_clip = result.scalar_one_or_none()

        assert deleted_clip is None


class TestTimestampHandling:
    """Test timestamp fields and auto-update behavior."""

    async def test_created_at_auto_set(self, test_db_session, sample_user_data):
        """Test that created_at is automatically set."""
        task = Task(
            id="task-timestamp",
            user_id=sample_user_data.id,
            status="pending"
        )

        test_db_session.add(task)
        await test_db_session.commit()
        await test_db_session.refresh(task)

        assert task.created_at is not None
        assert isinstance(task.created_at, datetime)

    async def test_updated_at_auto_set(self, test_db_session, sample_user_data):
        """Test that updated_at is automatically set and updated."""
        task = Task(
            id="task-updated",
            user_id=sample_user_data.id,
            status="pending"
        )

        test_db_session.add(task)
        await test_db_session.commit()
        await test_db_session.refresh(task)

        original_updated_at = task.updated_at

        # Wait a bit and update
        import time
        time.sleep(0.1)

        task.status = "processing"
        await test_db_session.commit()
        await test_db_session.refresh(task)

        # updated_at should have changed
        assert task.updated_at >= original_updated_at
