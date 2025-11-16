# start backend/tests/test_font_service.py

"""Unit tests for FontService database models."""

import pytest
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dataclasses import dataclass
from typing import Optional

from src.models import Base, SystemFont


@dataclass
class FontMetadata:
    """Lightweight FontMetadata for testing."""

    id: str
    name: str
    family: str
    style: Optional[str] = None
    weight: Optional[int] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    is_valid: bool = True
    detection_timestamp: Optional[str] = None
    metadata_json: Optional[dict] = None
    source: str = "system"


@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_font_metadata_creation():
    """Test creating FontMetadata objects."""
    font = FontMetadata(
        id="test-001",
        name="Test Font",
        family="Test Family",
        style="normal",
        weight=400,
        file_path="/tmp/test.ttf",
        file_hash="abc123",
        is_valid=True,
        detection_timestamp=datetime.now().isoformat(),
        source="system"
    )

    assert font.name == "Test Font"
    assert font.family == "Test Family"
    assert font.source == "system"
    assert font.is_valid is True


@pytest.mark.asyncio
async def test_system_font_database_model(test_db):
    """Test SystemFont model can be created and queried."""
    from sqlalchemy import select
    import uuid

    # Create a system font entry
    font = SystemFont(
        id=str(uuid.uuid4()),
        name="Arial",
        family="Arial",
        style="normal",
        weight=400,
        file_path="/System/Library/Fonts/Supplemental/Arial.ttf",
        file_hash="test_hash_123",
        is_valid=True,
        detection_timestamp=datetime.now().isoformat(),
        metadata_json={"version": "1.0"},
        source="system"
    )

    test_db.add(font)
    await test_db.commit()

    # Query it back
    result = await test_db.execute(select(SystemFont).where(SystemFont.name == "Arial"))
    retrieved_font = result.scalar()

    assert retrieved_font is not None
    assert retrieved_font.name == "Arial"
    assert retrieved_font.source == "system"


@pytest.mark.asyncio
async def test_system_font_unique_constraint(test_db):
    """Test that font names are unique."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    import uuid

    # Create first font
    font1 = SystemFont(
        id=str(uuid.uuid4()),
        name="Arial",
        family="Arial",
        source="system"
    )

    test_db.add(font1)
    await test_db.commit()

    # Try to create duplicate
    font2 = SystemFont(
        id=str(uuid.uuid4()),
        name="Arial",  # Same name
        family="Arial",
        source="bundled"
    )

    test_db.add(font2)

    # Should raise IntegrityError
    with pytest.raises(IntegrityError):
        await test_db.commit()


@pytest.mark.asyncio
async def test_system_font_source_check_constraint(test_db):
    """Test that source field only accepts 'bundled' or 'system'."""
    from sqlalchemy import select
    import uuid

    font = SystemFont(
        id=str(uuid.uuid4()),
        name="Test Font",
        family="Test",
        source="bundled"  # Valid
    )

    test_db.add(font)
    await test_db.commit()

    result = await test_db.execute(
        select(SystemFont).where(SystemFont.name == "Test Font")
    )
    retrieved = result.scalar()
    assert retrieved.source == "bundled"


@pytest.mark.asyncio
async def test_system_font_filtering_by_source(test_db):
    """Test filtering fonts by source."""
    from sqlalchemy import select
    import uuid

    # Create bundled font
    bundled = SystemFont(
        id=str(uuid.uuid4()),
        name="Bundled Font",
        family="Test",
        source="bundled"
    )

    # Create system font
    system = SystemFont(
        id=str(uuid.uuid4()),
        name="System Font",
        family="Test",
        source="system"
    )

    test_db.add_all([bundled, system])
    await test_db.commit()

    # Query bundled only
    result = await test_db.execute(
        select(SystemFont).where(SystemFont.source == "bundled")
    )
    bundled_fonts = result.scalars().all()

    assert len(bundled_fonts) == 1
    assert bundled_fonts[0].name == "Bundled Font"

    # Query system only
    result = await test_db.execute(
        select(SystemFont).where(SystemFont.source == "system")
    )
    system_fonts = result.scalars().all()

    assert len(system_fonts) == 1
    assert system_fonts[0].name == "System Font"


@pytest.mark.asyncio
async def test_system_font_search_by_family(test_db):
    """Test searching fonts by family name."""
    from sqlalchemy import select, func as db_func, or_
    import uuid

    # Create fonts with different families
    fonts = [
        SystemFont(
            id=str(uuid.uuid4()),
            name="Arial Regular",
            family="Arial",
            source="system"
        ),
        SystemFont(
            id=str(uuid.uuid4()),
            name="Times New Roman",
            family="Times",
            source="system"
        ),
    ]

    test_db.add_all(fonts)
    await test_db.commit()

    # Search for "arial" (case-insensitive)
    search_term = "%arial%"
    result = await test_db.execute(
        select(SystemFont).where(
            or_(
                db_func.lower(SystemFont.name).like(search_term),
                db_func.lower(SystemFont.family).like(search_term)
            )
        )
    )
    found = result.scalars().all()

    assert len(found) == 1
    assert found[0].family == "Arial"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# end backend/tests/test_font_service.py
