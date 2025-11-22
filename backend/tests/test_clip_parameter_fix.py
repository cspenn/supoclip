"""
Test to verify the parameter shadowing bug fix in clip_repository.py

This test verifies that:
1. The 'text' parameter has been renamed to 'clip_text'
2. The SQLAlchemy text() function is no longer shadowed
3. Clips can be saved to the database successfully
"""
from src.config import Config
from src.repositories.clip_repository import ClipRepository
import asyncio
import sys
from pathlib import Path
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


async def test_parameter_shadowing_fix():
    """Test that the text parameter shadowing bug is fixed."""

    config = Config()

    # Create a test database session
    engine = create_async_engine(config.database_url, echo=False)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as db:
        try:
            # First, create a test task
            test_task_id = "test-task-clip-fix-12345"
            test_user_id = "test-user-12345"

            # Check if task exists, if not create it
            check_task = await db.execute(
                sql_text("SELECT id FROM tasks WHERE id = :task_id"),
                {"task_id": test_task_id},
            )
            if not check_task.fetchone():
                await db.execute(
                    sql_text(
                        """
                        INSERT INTO tasks (id, user_id, status, progress)
                        VALUES (:id, :user_id, :status, :progress)
                    """
                    ),
                    {
                        "id": test_task_id,
                        "user_id": test_user_id,
                        "status": "testing",
                        "progress": 100,
                    },
                )
                await db.commit()

            # Now test the create_clip method
            print("Testing ClipRepository.create_clip()...")

            clip_id = await ClipRepository.create_clip(
                db=db,
                task_id=test_task_id,
                filename="test_clip.mp4",
                file_path="/tmp/test_clip.mp4",
                start_time="00:00:10",
                end_time="00:00:30",
                duration=20.0,
                clip_text="This is test clip text content",  # Using clip_text parameter
                relevance_score=0.95,
                reasoning="Test clip for parameter fix verification",
                clip_order=1,
            )

            await db.commit()

            print(f"✅ SUCCESS: Created clip with ID: {clip_id}")
            print("✅ The 'clip_text' parameter is working correctly")
            print("✅ SQLAlchemy text() function is no longer shadowed")

            # Verify the clip was saved
            verify = await db.execute(
                sql_text("SELECT text FROM generated_clips WHERE id = :clip_id"),
                {"clip_id": clip_id},
            )
            saved_text = verify.scalar()

            assert (
                saved_text == "This is test clip text content"
            ), f"Expected text not saved. Got: {saved_text}"

            print("✅ VERIFIED: Clip text was saved correctly to database")

            # Clean up
            await db.execute(
                sql_text("DELETE FROM generated_clips WHERE task_id = :task_id"),
                {"task_id": test_task_id},
            )
            await db.execute(
                sql_text("DELETE FROM tasks WHERE id = :task_id"),
                {"task_id": test_task_id},
            )
            await db.commit()

            print("\n🎉 All tests passed! The parameter shadowing bug is fixed.")
            return True

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            await engine.dispose()


if __name__ == "__main__":
    result = asyncio.run(test_parameter_shadowing_fix())
    sys.exit(0 if result else 1)
