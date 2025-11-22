#!/usr/bin/env python3
"""Migration script to convert relative logo paths to absolute paths.

This script updates the users table to ensure all logo_file_path values
are stored as absolute paths for consistent resolution across the application.

Usage:
    python -m scripts.migrate_logo_paths

The script will:
1. Find all users with logo_file_path set
2. Convert any relative paths to absolute paths
3. Update the database with the corrected paths
"""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import text

from src.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_logo_paths():
    """Convert relative logo paths to absolute paths in database."""
    logger.info("Starting logo path migration...")

    async with AsyncSessionLocal() as db:
        # Find all users with logo paths
        result = await db.execute(
            text(
                "SELECT id, logo_file_path FROM users WHERE logo_file_path IS NOT NULL"
            )
        )
        users = result.fetchall()

        logger.info(f"Found {len(users)} users with logo paths")

        updated_count = 0
        for user_id, logo_path in users:
            if not logo_path:
                continue

            path_obj = Path(logo_path)

            # Check if already absolute
            if path_obj.is_absolute():
                logger.info(f"User {user_id}: Path already absolute: {logo_path}")
                continue

            # Convert to absolute
            absolute_path = path_obj.resolve()

            # Only update if the file exists
            if absolute_path.exists():
                await db.execute(
                    text("UPDATE users SET logo_file_path = :path WHERE id = :user_id"),
                    {"path": str(absolute_path), "user_id": user_id},
                )
                updated_count += 1
                logger.info(f"User {user_id}: Updated {logo_path} -> {absolute_path}")
            else:
                logger.warning(
                    f"User {user_id}: Logo file not found at {absolute_path}"
                )

        await db.commit()
        logger.info(f"Migration complete. Updated {updated_count} paths.")


if __name__ == "__main__":
    asyncio.run(migrate_logo_paths())
