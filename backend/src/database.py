import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database configuration - SQLite instead of PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./supoclip.db",  # Local SQLite database
)

# Create async engine with SQLite-specific configuration
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    connect_args=connect_args,
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for all models


class Base(DeclarativeBase):
    pass


# Dependency to get database session


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Initialize database


async def init_db() -> None:
    """Initialize database and apply migrations."""
    async with engine.begin() as conn:
        # Create all tables from models
        await conn.run_sync(Base.metadata.create_all)

        # Apply custom migrations if needed
        try:
            migration_path = (
                Path(__file__).parent.parent / "migrations" / "002_add_system_fonts.sql"
            )
            if migration_path.exists():
                with open(migration_path) as f:
                    sql = f.read()

                # For SQLite, we need to execute statements one by one.
                # We use a state machine to avoid splitting inside BEGIN...END blocks (common in triggers).

                statements = []
                current_stmt = []
                depth = 0
                for line in sql.splitlines():
                    clean_line = line.strip()
                    if not clean_line or clean_line.startswith("--"):
                        continue

                    current_stmt.append(line)
                    # Simple token-based depth tracking
                    upper_line = clean_line.upper()
                    if "BEGIN" in upper_line:
                        depth += 1
                    if "END" in upper_line:
                        depth -= 1

                    if clean_line.endswith(";") and depth <= 0:
                        statements.append("\n".join(current_stmt))
                        current_stmt = []

                if current_stmt:
                    statements.append("\n".join(current_stmt))

                for statement in statements:
                    if statement.strip():
                        await conn.execute(text(statement))

                logger.info("✅ Applied system_fonts migration")
        except Exception as e:
            logger.warning(f"⚠️ Migration already applied or failed: {e}")


# Close database connections


async def close_db():
    await engine.dispose()
