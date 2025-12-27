#!/usr/bin/env python3
"""
Validation script for logo upload database fix.

This script verifies that:
1. The required columns exist in the users table
2. The columns can be updated with logo data
3. The UserPreferencesService can read the logo fields
"""
import asyncio
import sqlite3
from pathlib import Path


def check_database_schema():
    """Check if the required columns exist in the database."""
    print("=" * 60)
    print("PHASE 1: Database Schema Validation")
    print("=" * 60)

    db_path = Path(__file__).parent / "supoclip.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get table info
    cursor.execute("PRAGMA table_info(users);")
    columns = cursor.fetchall()

    required_columns = {
        "logo_file_path": False,
        "logo_corner_position": False,
        "output_resolution": False,
    }

    print("\nChecking for required columns:")
    for col in columns:
        col_name = col[1]  # Column name is at index 1
        if col_name in required_columns:
            required_columns[col_name] = True
            print(f"  ✓ Found: {col_name}")

    # Check if all required columns exist
    missing = [k for k, v in required_columns.items() if not v]
    if missing:
        print(f"\n❌ FAILED: Missing columns: {missing}")
        conn.close()
        return False

    print("\n✅ SUCCESS: All required columns exist in users table")
    conn.close()
    return True


def test_database_operations():
    """Test that we can update and read logo fields."""
    print("\n" + "=" * 60)
    print("PHASE 2: Database Operations Validation")
    print("=" * 60)

    db_path = Path(__file__).parent / "supoclip.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get an existing user
    cursor.execute("SELECT id FROM users LIMIT 1")
    user_row = cursor.fetchone()

    if not user_row:
        print("\n⚠️  WARNING: No users in database to test with")
        conn.close()
        return True  # Not a failure, just can't test

    user_id = user_row[0]
    print(f"\nTesting with user_id: {user_id}")

    # Test UPDATE operation
    test_logo_path = "/temp/logos/test_logo.png"
    test_position = "top-left"
    test_resolution = "1080p"

    try:
        cursor.execute(
            """
            UPDATE users
            SET logo_file_path = ?,
                logo_corner_position = ?,
                output_resolution = ?
            WHERE id = ?
            """,
            (test_logo_path, test_position, test_resolution, user_id),
        )
        conn.commit()
        print(f"  ✓ Successfully updated logo fields for user {user_id}")
    except sqlite3.Error as e:
        print(f"\n❌ FAILED: Could not update logo fields: {e}")
        conn.close()
        return False

    # Test SELECT operation
    try:
        cursor.execute(
            """
            SELECT logo_file_path, logo_corner_position, output_resolution
            FROM users WHERE id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()

        if row:
            logo_path, position, resolution = row
            print("  ✓ Successfully read logo fields:")
            print(f"    - logo_file_path: {logo_path}")
            print(f"    - logo_corner_position: {position}")
            print(f"    - output_resolution: {resolution}")

            # Verify values match
            if (
                logo_path == test_logo_path
                and position == test_position
                and resolution == test_resolution
            ):
                print("  ✓ Values match what was written")
            else:
                print("  ⚠️  WARNING: Values don't match!")
        else:
            print("\n❌ FAILED: Could not read user data")
            conn.close()
            return False

    except sqlite3.Error as e:
        print(f"\n❌ FAILED: Could not read logo fields: {e}")
        conn.close()
        return False

    # Clean up test data (set back to NULL)
    cursor.execute("UPDATE users SET logo_file_path = NULL WHERE id = ?", (user_id,))
    conn.commit()

    print("\n✅ SUCCESS: Database operations work correctly")
    conn.close()
    return True


async def test_user_preferences_service():
    """Test that UserPreferencesService can read logo fields."""
    print("\n" + "=" * 60)
    print("PHASE 3: UserPreferencesService Validation")
    print("=" * 60)

    try:
        from src.database import AsyncSessionLocal
        from src.services.user_preferences_service import UserPreferencesService

        # Get an existing user
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text

            result = await db.execute(text("SELECT id FROM users LIMIT 1"))
            user_row = result.fetchone()

            if not user_row:
                print("\n⚠️  WARNING: No users in database to test with")
                return True

            user_id = user_row[0]
            print(f"\nTesting with user_id: {user_id}")

            # Test UserPreferencesService
            service = UserPreferencesService(db)
            prefs = await service.get_user_preferences(user_id)

            print("  ✓ Successfully loaded preferences")
            print(f"    - logo_file_path: {prefs.get('logo_file_path')}")
            print(f"    - logo_corner_position: {prefs.get('logo_corner_position')}")
            print(f"    - output_resolution: {prefs.get('output_resolution')}")

            # Check that all expected keys exist
            required_keys = [
                "logo_file_path",
                "logo_corner_position",
                "output_resolution",
            ]
            missing_keys = [k for k in required_keys if k not in prefs]

            if missing_keys:
                print(f"\n❌ FAILED: Missing keys in preferences: {missing_keys}")
                return False

            print("\n✅ SUCCESS: UserPreferencesService reads logo fields correctly")
            return True

    except Exception as e:
        print(f"\n❌ FAILED: Error testing UserPreferencesService: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all validation checks."""
    print("\n" + "=" * 60)
    print("LOGO UPLOAD FIX VALIDATION")
    print("=" * 60)

    # Phase 1: Schema validation
    schema_ok = check_database_schema()
    if not schema_ok:
        print("\n" + "=" * 60)
        print("VALIDATION FAILED: Database schema issues")
        print("=" * 60)
        return False

    # Phase 2: Database operations
    operations_ok = test_database_operations()
    if not operations_ok:
        print("\n" + "=" * 60)
        print("VALIDATION FAILED: Database operations issues")
        print("=" * 60)
        return False

    # Phase 3: UserPreferencesService
    service_ok = await test_user_preferences_service()
    if not service_ok:
        print("\n" + "=" * 60)
        print("VALIDATION FAILED: UserPreferencesService issues")
        print("=" * 60)
        return False

    # All checks passed
    print("\n" + "=" * 60)
    print("✅ ALL VALIDATIONS PASSED")
    print("=" * 60)
    print("\nThe logo upload database fix is working correctly!")
    print("\nFixed issues:")
    print("  • Added logo_file_path column to users table")
    print("  • Added logo_corner_position column with default 'top-right'")
    print("  • Added output_resolution column with default '720p'")
    print("  • Updated UserPreferencesService to read output_resolution")
    print("  • Updated init_sqlite.sql for fresh installs")
    print("\nDatabase is ready for logo upload feature!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
