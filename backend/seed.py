#!/usr/bin/env python3
# start backend/seed.py

"""
Database seeding script for SupoClip.

This script initializes the SQLite database with default data for local development.
It creates the default "local-user" if it doesn't already exist.

Usage:
    python3 seed.py

Environment variables:
    DATABASE_URL - SQLite connection string (default: sqlite:///./supoclip.db)
    DEFAULT_USER_ID - User ID to create (default: local-user)
"""

import os
import sys
from datetime import datetime

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("❌ SQLAlchemy not found. Trying standard sqlite3...")
    import sqlite3

    # Fallback to sqlite3
    db_path = os.getenv("DATABASE_URL", "sqlite:///./supoclip.db").replace("sqlite:///", "")
    user_id = os.getenv("DEFAULT_USER_ID", "local-user")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if cursor.fetchone():
            print(f"✅ User '{user_id}' already exists")
            sys.exit(0)

        # Create default user
        now = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO users (id, name, email, emailVerified, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            "Local Development User",
            "local@localhost.local",
            0,
            now,
            now
        ))

        conn.commit()
        conn.close()
        print(f"✅ Created default user '{user_id}'")
        print("✨ Database seeding complete!")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        sys.exit(1)


def seed_database() -> None:
    """Initialize database with default data for local development."""
    # Get config from environment
    db_url = os.getenv("DATABASE_URL", "sqlite:///./supoclip.db")
    user_id = os.getenv("DEFAULT_USER_ID", "local-user")

    # Convert async connection string to sync if needed
    db_url = db_url.replace("sqlite+aiosqlite", "sqlite")

    print(f"🌱 Seeding database at: {db_url}")

    engine = create_engine(db_url)

    with engine.begin() as connection:
        # Check if default user already exists
        result = connection.execute(
            text("SELECT id FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )

        existing_user = result.fetchone()

        if existing_user:
            print(f"✅ User '{user_id}' already exists")
            return

        # Create default user for local development
        now = datetime.utcnow().isoformat()

        try:
            connection.execute(
                text("""
                    INSERT INTO users (id, name, email, emailVerified, createdAt, updatedAt)
                    VALUES (:id, :name, :email, :emailVerified, :createdAt, :updatedAt)
                """),
                {
                    "id": user_id,
                    "name": "Local Development User",
                    "email": "local@localhost.local",
                    "emailVerified": 0,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
            print(f"✅ Created default user '{user_id}'")

        except Exception as e:
            print(f"❌ Error creating user: {e}")
            raise


def main() -> None:
    """Entry point for database seeding."""
    try:
        seed_database()
        print("✨ Database seeding complete!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

# end backend/seed.py
