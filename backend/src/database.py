# start backend/src/database.py
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .config import Config

logger = logging.getLogger(__name__)

# Database configuration - SQLite instead of PostgreSQL
DATABASE_URL = Config().database_url

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


def _parse_sql_statements(sql: str) -> list[str]:
    """Parse SQL file into individual statements, respecting BEGIN...END blocks.

    SQLite requires executing statements one by one. This parser uses a simple
    state machine to avoid splitting inside BEGIN...END blocks (common in triggers).

    Args:
        sql: Raw SQL file content

    Returns:
        List of individual SQL statements
    """
    statements = []
    current_stmt: list[str] = []
    depth = 0

    for line in sql.splitlines():
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("--"):
            continue

        current_stmt.append(line)

        # Simple token-based depth tracking for BEGIN...END blocks
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

    return statements


async def _apply_migration_file(conn, migration_path: Path, description: str) -> None:
    """Apply a single migration file.

    Args:
        conn: Database connection
        migration_path: Path to the SQL migration file
        description: Description for logging
    """
    if not migration_path.exists():
        return

    sql = migration_path.read_text()

    statements = _parse_sql_statements(sql)
    for statement in statements:
        if statement.strip():
            await conn.execute(text(statement))

    logger.info(f"✅ Applied {description} migration")


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
            await _apply_migration_file(conn, migration_path, "system_fonts")
        except Exception as e:
            logger.warning(f"⚠️ Migration already applied or failed: {e}")


# Close database connections


async def close_db():
    await engine.dispose()

# end backend/src/database.py
