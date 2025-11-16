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
    "sqlite+aiosqlite:///./supoclip.db"  # Local SQLite database
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
            migration_path = Path(__file__).parent.parent / "migrations" / "002_add_system_fonts.sql"
            if migration_path.exists():
                with open(migration_path) as f:
                    sql = f.read()
                    # For SQLite, we need to execute statements one by one
                    # Split on semicolon and execute each statement
                    statements = [s.strip() for s in sql.split(';') if s.strip()]
                    for statement in statements:
                        await conn.execute(text(statement))
                logger.info("✅ Applied system_fonts migration")
        except Exception as e:
            logger.warning(f"⚠️ Migration already applied or failed: {e}")

# Close database connections
async def close_db():
    await engine.dispose()
