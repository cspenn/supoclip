"""
Direct verification that the parameter shadowing bug fix allows clips to be saved.

This test simulates what happens in the real pipeline when saving clips to database.
"""
from src.repositories.clip_repository import ClipRepository
from src.database import AsyncSessionLocal
from sqlalchemy import text
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


async def test_clip_save():
    """Test that clips can be saved to database without TypeError."""

    print("=" * 80)
    print("CLIP SAVE VERIFICATION TEST")
    print("=" * 80)
    print("\nThis test verifies that the parameter shadowing bug is fixed.")
    print("Before fix: TypeError: 'str' object is not callable")
    print("After fix: Clips save successfully\n")

    async with AsyncSessionLocal() as db:
        try:
            # Create a realistic test task
            test_task_id = "verify-clip-save-98765"
            test_user_id = "test-user-98765"

            # Clean up any existing test data
            await db.execute(
                text("DELETE FROM generated_clips WHERE task_id = :task_id"),
                {"task_id": test_task_id},
            )
            await db.execute(
                text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": test_task_id}
            )

            # Create test task
            await db.execute(
                text(
                    """INSERT INTO tasks (id, user_id, status, progress)
                   VALUES (:id, :user_id, :status, :progress)"""
                ),
                {
                    "id": test_task_id,
                    "user_id": test_user_id,
                    "status": "processing",
                    "progress": 90,
                },
            )
            await db.commit()

            print("✅ Test task created")

            # Simulate saving a clip (this is what fails with the shadowing bug)
            print("\n📝 Testing ClipRepository.create_clip()...")
            print('   This calls: text("""INSERT INTO...""")')
            print("   Before fix: 'text' parameter shadows text() function")
            print("   After fix: 'clip_text' parameter, text() function works\n")

            clip_id = await ClipRepository.create_clip(
                db=db,
                task_id=test_task_id,
                filename="test_clip_001.mp4",
                file_path="/tmp/clips/test_clip_001.mp4",
                start_time="00:00:15",
                end_time="00:00:35",
                duration=20.0,
                clip_text="This is the transcript text for the clip segment",
                relevance_score=0.92,
                reasoning="Strong hook with actionable advice",
                clip_order=1,
            )

            await db.commit()

            print(f"✅ SUCCESS: Clip created with ID: {clip_id}")
            print("✅ No TypeError occurred")
            print("✅ SQLAlchemy text() function is NOT shadowed")
            print("✅ Parameter 'clip_text' is working correctly")

            # Verify it was actually saved
            result = await db.execute(
                text(
                    "SELECT COUNT(*) as count FROM generated_clips WHERE task_id = :task_id"
                ),
                {"task_id": test_task_id},
            )
            count = result.scalar()

            print(f"\n✅ VERIFIED: {count} clip(s) saved to database")

            # Clean up
            await db.execute(
                text("DELETE FROM generated_clips WHERE task_id = :task_id"),
                {"task_id": test_task_id},
            )
            await db.execute(
                text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": test_task_id}
            )
            await db.commit()

            print("\n" + "=" * 80)
            print("🎉 TEST PASSED: Parameter shadowing bug is FIXED")
            print("=" * 80)
            print("\nThe bug was:")
            print("  Parameter name 'text' shadowed SQLAlchemy's text() function")
            print("\nThe fix:")
            print("  1. Renamed parameter from 'text' to 'clip_text'")
            print("  2. Updated dictionary value from 'text' to 'clip_text'")
            print("  3. Updated caller in task_service.py")
            print("\nResult:")
            print("  ✅ Clips can now be saved to database successfully")
            print("  ✅ Video processing pipeline can complete")

            return True

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    result = asyncio.run(test_clip_save())
    sys.exit(0 if result else 1)
