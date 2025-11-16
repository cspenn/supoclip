# REVISED Phase 1: System Fonts Detection Implementation Plan

**Date:** November 15, 2025 (REVISED)
**Status:** Ready for Implementation
**Target Branch:** `feature/system-fonts-detection`
**Total Estimated Effort:** 17-20 hours across 15 VUWs

---

## Executive Summary

This document provides a **REVISED** step-by-step implementation plan for Phase 1 of the SupoClip font system expansion, addressing **6 CRITICAL BLOCKING ISSUES** identified during security and accuracy review.

**Changes from Original Plan:**
- ✅ Fixed NumPy 2.x incompatibility with matplotlib (pin numpy<2.0.0)
- ✅ Converted PostgreSQL schema to SQLite-compatible syntax
- ✅ Added proper database session initialization
- ✅ Removed duplicate font endpoint conflicts
- ✅ Removed hashlib from dependencies (built-in)
- ✅ Added explicit database migration VUWs
- ✅ Added unit testing VUW
- ✅ Added old endpoint removal VUW
- ✅ Corrected Prisma field mapping with @map directives
- ✅ Fixed time estimates to realistic 17-20 hours

---

## Dependency Resolution

**Critical Issue #1: NumPy/matplotlib Incompatibility**

Pin `numpy>=1.24.0,<2.0.0` in `backend/pyproject.toml` line 23.

---

## VUW 6: Remove Old Font Endpoints

**Objective:** Remove duplicate font endpoints before adding new FontService routes
**Time Estimate:** 25 minutes
**Files:**
- `backend/src/main.py` (MODIFY - lines 669-720)
- `backend/src/api/routes/media.py` (MODIFY - lines 18-60)

#### Step-by-Step Instructions

1. **Remove endpoints from backend/src/main.py** (lines 669-720)

Open `backend/src/main.py` and locate these lines (around line 669):

```python
@app.get("/fonts")
async def get_available_fonts() -> List[Dict[str, Any]]:
    """Get list of available fonts."""
    # ... code until line 710 ...
    return fonts_list

@app.get("/fonts/{font_name}")
async def get_font_file(font_name: str) -> FileResponse:
    """Serve font file."""
    # ... code until line 720 ...
    return FileResponse(path=font_path, ...)
```

**Delete lines 669-720 entirely.**

2. **Remove endpoints from backend/src/api/routes/media.py** (lines 18-60)

Open `backend/src/api/routes/media.py` and locate:

```python
@router.get("/fonts")
async def list_fonts() -> List[Dict[str, Any]]:
    # ... code until line 47 ...

@router.get("/fonts/{font_name}")
async def get_font(font_name: str) -> FileResponse:
    # ... code until line 60 ...
```

**Delete lines 18-60 entirely.**

#### Verification Checklist

- [ ] `/fonts` endpoint no longer in main.py
- [ ] `/fonts/{font_name}` endpoint no longer in main.py
- [ ] `/fonts` endpoint no longer in media.py
- [ ] `/fonts/{font_name}` endpoint no longer in media.py
- [ ] API still starts without route conflicts
- [ ] Self-attestation: Confirm endpoints removed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/src/main.py backend/src/api/routes/media.py
git commit -m "VUW 6: Remove old duplicate font endpoints

- Remove GET /fonts from main.py (lines 669-710)
- Remove GET /fonts/{font_name} from main.py (lines 711-720)
- Remove GET /fonts from media.py (lines 18-47)
- Remove GET /fonts/{font_name} from media.py (lines 48-60)

These will be replaced by new FontService routes in VUW 11

Fixes: Critical Issue #4 (Duplicate endpoint conflicts)"
```

---

## VUW 7: Create SQLAlchemy Models for System Fonts

**Objective:** Add SystemFont model to backend/src/models.py
**Time Estimate:** 30 minutes
**Files:**
- `backend/src/models.py` (MODIFY - add after GeneratedClip class)

#### Step-by-Step Instructions

1. **Open backend/src/models.py and find the end of GeneratedClip class** (around line 117)

2. **Add SystemFont model after GeneratedClip class**

Insert after line 117 (end of GeneratedClip):

```python
class SystemFont(Base):
    __tablename__ = "system_fonts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_string)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    family: Mapped[str] = mapped_column(String(255), nullable=False)
    style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'normal', 'italic', etc.
    weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 100, 400, 700, etc.
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detection_timestamp: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # ISO8601 string
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'bundled' or 'system'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("source IN ('bundled', 'system')", name="check_system_fonts_source"),
    )
```

#### Verification Checklist

- [ ] SystemFont class added after GeneratedClip (around line 118)
- [ ] All fields properly mapped with correct types
- [ ] source field has CHECK constraint
- [ ] Primary key uses generate_uuid_string()
- [ ] Timestamps use func.now() with timezone
- [ ] JSON field available for metadata
- [ ] Self-attestation: Confirm model added

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/src/models.py
git commit -m "VUW 7: Add SystemFont SQLAlchemy model

- Add SystemFont model to backend/src/models.py
- Fields: id, name, family, style, weight, file_path, file_hash, is_valid
- Fields: detection_timestamp, metadata_json, source
- Add CHECK constraint for source enum
- Use func.now() for timestamp defaults

Fixes: Critical Issue #2 (Database schema - SQLAlchemy layer)"
```

---

## VUW 8: Create Backend Database Migration

**Objective:** Create SQL migration file to add system_fonts table
**Time Estimate:** 35 minutes
**Files:**
- `backend/migrations/002_add_system_fonts.sql` (NEW)

#### Step-by-Step Instructions

1. **Create migration directory if needed**

```bash
mkdir -p /Users/cspenn/Documents/github/supoclip/backend/migrations
```

2. **Create migration file**

Create: `/Users/cspenn/Documents/github/supoclip/backend/migrations/002_add_system_fonts.sql`

```sql
-- Migration: Add system_fonts table for font caching
-- Date: 2025-11-15
-- Status: For SQLite backend

-- Create system_fonts table with SQLite-compatible syntax
CREATE TABLE IF NOT EXISTS system_fonts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL,
    style TEXT,
    weight INTEGER,
    file_path TEXT,
    file_hash TEXT,
    is_valid INTEGER DEFAULT 1,
    detection_timestamp TEXT,
    metadata_json TEXT,
    source TEXT NOT NULL CHECK(source IN ('bundled', 'system')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_system_fonts_family ON system_fonts(family);
CREATE INDEX IF NOT EXISTS idx_system_fonts_source ON system_fonts(source);
CREATE INDEX IF NOT EXISTS idx_system_fonts_is_valid ON system_fonts(is_valid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_fonts_name_file ON system_fonts(name, file_path);

-- Create trigger for auto-updating updated_at
CREATE TRIGGER IF NOT EXISTS update_system_fonts_updated_at
AFTER UPDATE ON system_fonts
FOR EACH ROW
BEGIN
    UPDATE system_fonts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
```

3. **Apply migration to current database**

Open `backend/src/database.py` and locate the engine initialization. After creating the engine, add:

```python
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
                    await conn.connection.executescript(sql)
                logger.info("✅ Applied system_fonts migration")
        except Exception as e:
            logger.warning(f"⚠️ Migration already applied or failed: {e}")
```

4. **Call init_db in startup event**

In `backend/src/main.py`, find the `@app.on_event("startup")` section and add:

```python
@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    await init_db()  # Initialize database with migrations
    # ... rest of startup code ...
```

#### Verification Checklist

- [ ] Migration file created: `backend/migrations/002_add_system_fonts.sql`
- [ ] SQL syntax is SQLite-compatible
- [ ] Indexes created for performance
- [ ] Auto-update trigger for updated_at
- [ ] init_db() function exists in database.py
- [ ] init_db() called in startup event
- [ ] Migration applies without errors
- [ ] system_fonts table exists in database
- [ ] Self-attestation: Confirm migration applied

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/migrations/002_add_system_fonts.sql backend/src/database.py backend/src/main.py
git commit -m "VUW 8: Create backend database migration

- Create migration file 002_add_system_fonts.sql with SQLite syntax
- Add indexes for family, source, is_valid
- Add trigger for auto-updating updated_at
- Add init_db() function to database.py
- Call init_db() in startup event
- Apply migration on app startup

Fixes: Critical Issue #6 (Database migration strategy)"
```

---

## VUW 9: Create Frontend Prisma Migration

**Objective:** Update Prisma schema and apply frontend migration
**Time Estimate:** 30 minutes
**Files:**
- `frontend/prisma/schema.prisma` (MODIFY)

#### Step-by-Step Instructions

1. **Open frontend/prisma/schema.prisma and add SystemFont model**

Add after the Source model (around line 92):

```prisma
model SystemFont {
  id                  String   @id
  name                String   @unique
  family              String
  style               String?
  weight              Int?
  filePath            String?  @map("file_path")
  fileHash            String?  @map("file_hash")
  isValid             Boolean  @default(true) @map("is_valid")
  detectionTimestamp  String?  @map("detection_timestamp")
  metadataJson        Json?    @map("metadata_json")
  source              String   // 'bundled' or 'system'
  createdAt           DateTime @default(now()) @map("created_at")
  updatedAt           DateTime @updatedAt @map("updated_at")

  @@map("system_fonts")
}
```

2. **Generate Prisma client**

```bash
cd /Users/cspenn/Documents/github/supoclip/frontend
npx prisma generate
```

3. **Apply database changes**

```bash
cd /Users/cspenn/Documents/github/supoclip/frontend
npx prisma db push
```

#### Verification Checklist

- [ ] SystemFont model added to schema.prisma
- [ ] All fields mapped to snake_case with @map
- [ ] @@map("system_fonts") points to correct table
- [ ] `npx prisma generate` succeeds
- [ ] `npx prisma db push` succeeds
- [ ] system_fonts table matches backend schema
- [ ] Prisma client regenerated with SystemFont type
- [ ] Self-attestation: Confirm migration applied

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add frontend/prisma/schema.prisma
git commit -m "VUW 9: Create frontend Prisma migration

- Add SystemFont model to schema.prisma
- Use @map directives for snake_case field names
- Generate Prisma client with npx prisma generate
- Sync database with npx prisma db push
- Ensure field name consistency across backend and frontend

Fixes: Critical Issue #6 (Database migration strategy)
Fixes: Accuracy Issue #4 (Prisma field name mismatch)"
```

---

## VUW 10: Implement FontService Database Caching

**Objective:** Implement cache_fonts() and get_all_fonts() with database operations
**Time Estimate:** 60 minutes
**Files:**
- `backend/src/services/font_service.py` (MODIFY)

#### Step-by-Step Instructions

1. **Add imports at top of file** (after existing imports)

```python
from sqlalchemy import select, delete, func as db_func, or_
from sqlalchemy.exc import IntegrityError
import uuid
```

2. **Implement cache_fonts() method** (replace stub around line 160)

```python
async def cache_fonts(self, fonts: List[FontMetadata]) -> None:
    """
    Cache detected fonts in SQLite database.

    Args:
        fonts: List of FontMetadata to cache
    """
    if not self.db_session:
        logger.warning("⚠️ No database session available, skipping font caching")
        return

    if not fonts:
        logger.info("No fonts to cache")
        return

    try:
        from backend.src.models import SystemFont

        logger.info(f"💾 Caching {len(fonts)} fonts to database...")

        for font in fonts:
            try:
                # Check if font already exists
                existing = await self.db_session.execute(
                    select(SystemFont).where(SystemFont.name == font.name)
                )
                existing_font = existing.scalar()

                if existing_font:
                    # Update existing entry
                    existing_font.family = font.family
                    existing_font.style = font.style
                    existing_font.weight = font.weight
                    existing_font.file_path = font.file_path
                    existing_font.file_hash = font.file_hash
                    existing_font.is_valid = font.is_valid
                    existing_font.detection_timestamp = font.detection_timestamp
                    existing_font.metadata_json = font.metadata_json
                    existing_font.source = font.source
                    logger.debug(f"✏️ Updated cached font: {font.name}")
                else:
                    # Create new entry
                    db_font = SystemFont(
                        id=str(uuid.uuid4()),
                        name=font.name,
                        family=font.family,
                        style=font.style,
                        weight=font.weight,
                        file_path=font.file_path,
                        file_hash=font.file_hash,
                        is_valid=font.is_valid,
                        detection_timestamp=font.detection_timestamp,
                        metadata_json=font.metadata_json,
                        source=font.source
                    )
                    self.db_session.add(db_font)
                    logger.debug(f"✨ Cached new font: {font.name}")

            except IntegrityError as e:
                # Handle duplicate name (e.g., bundled + system with same name)
                logger.warning(f"⚠️ Font {font.name} duplicate, skipping: {e}")
                await self.db_session.rollback()
            except Exception as e:
                logger.error(f"❌ Failed to cache font {font.name}: {e}")

        # Commit all changes
        await self.db_session.commit()
        logger.info(f"✅ Successfully cached fonts")

    except Exception as e:
        logger.error(f"❌ Font caching failed: {e}")
        if self.db_session:
            await self.db_session.rollback()
```

3. **Implement get_all_fonts() method** (replace stub around line 170)

```python
async def get_all_fonts(self,
                       search_query: Optional[str] = None,
                       source_filter: Optional[str] = None) -> List[FontMetadata]:
    """
    Get all available fonts with optional filtering.

    Args:
        search_query: Search term for fuzzy matching (name, family)
        source_filter: Filter by source ('bundled' or 'system')

    Returns:
        List of matching FontMetadata objects
    """
    if not self.db_session:
        logger.warning("⚠️ No database session, returning empty list")
        return []

    try:
        from backend.src.models import SystemFont

        # Build query
        query = select(SystemFont)

        # Add source filter
        if source_filter:
            query = query.where(SystemFont.source == source_filter)

        # Add search filter
        if search_query:
            search_term = f"%{search_query.lower()}%"
            query = query.where(
                or_(
                    db_func.lower(SystemFont.name).ilike(search_term),
                    db_func.lower(SystemFont.family).ilike(search_term)
                )
            )

        # Execute query
        result = await self.db_session.execute(query)
        db_fonts = result.scalars().all()

        # Convert to FontMetadata
        fonts = [
            FontMetadata(
                id=f.id,
                name=f.name,
                family=f.family,
                style=f.style,
                weight=f.weight,
                file_path=f.file_path,
                file_hash=f.file_hash,
                is_valid=bool(f.is_valid),
                detection_timestamp=f.detection_timestamp,
                metadata_json=f.metadata_json,
                source=f.source
            )
            for f in db_fonts
        ]

        logger.debug(f"📋 Retrieved {len(fonts)} fonts from database")
        return fonts

    except Exception as e:
        logger.error(f"❌ Failed to retrieve fonts: {e}")
        return []
```

#### Verification Checklist

- [ ] cache_fonts() inserts fonts into database
- [ ] cache_fonts() updates existing fonts
- [ ] get_all_fonts() retrieves all fonts
- [ ] Search filter works with fuzzy matching
- [ ] Source filter works for 'bundled'/'system'
- [ ] FontMetadata objects created from database rows
- [ ] Error handling prevents crashes
- [ ] Self-attestation: Confirm methods work

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/src/services/font_service.py
git commit -m "VUW 10: Implement FontService database caching

- Implement cache_fonts() with insert/update logic
- Implement get_all_fonts() with search and filtering
- Handle duplicate font names gracefully
- Use database transactions for consistency
- Add proper error handling and logging

Fixes: Critical Issue #3 (Database session initialization)"
```

---

## VUW 11: Initialize FontService on Startup

**Objective:** Create get_font_service() dependency and initialize on startup
**Time Estimate:** 40 minutes
**Files:**
- `backend/src/main.py` (MODIFY)

#### Step-by-Step Instructions

1. **Add FontService initialization in main.py** (after imports, around line 50)

```python
from backend.src.services.font_service import FontService

# Global font service instance
_font_service: Optional[FontService] = None

async def get_font_service() -> FontService:
    """Get or create font service instance."""
    global _font_service
    if _font_service is None:
        _font_service = FontService(db_session=None, temp_dir=Path(TEMP_DIR))
    return _font_service

async def initialize_font_service(db_session: AsyncSession) -> None:
    """Initialize font service with database session."""
    global _font_service
    _font_service = FontService(db_session=db_session, temp_dir=Path(TEMP_DIR))

    logger.info("🚀 Initializing FontService...")

    # Load bundled fonts
    bundled = await _font_service.get_bundled_fonts()
    await _font_service.cache_fonts(bundled)
    logger.info(f"✅ Loaded {len(bundled)} bundled fonts")

    # Detect and cache system fonts in background
    asyncio.create_task(_detect_system_fonts_background())

async def _detect_system_fonts_background() -> None:
    """Background task to detect and cache system fonts."""
    try:
        logger.info("🔍 Starting background system font detection...")
        system_fonts = await _font_service.detect_system_fonts()
        await _font_service.cache_fonts(system_fonts)
        logger.info(f"✅ Detected and cached {len(system_fonts)} system fonts")
    except Exception as e:
        logger.error(f"❌ Background font detection failed: {e}")
```

2. **Update startup event** (find `@app.on_event("startup")` around line 200)

```python
@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    # ... existing startup code ...

    # Initialize font service
    async with AsyncSessionLocal() as session:
        await initialize_font_service(session)

    # ... rest of startup code ...
```

#### Verification Checklist

- [ ] FontService imported in main.py
- [ ] get_font_service() function exists
- [ ] initialize_font_service() exists
- [ ] Background task created for system font detection
- [ ] Bundled fonts loaded on startup
- [ ] Database session properly passed
- [ ] Logging shows font initialization
- [ ] Self-attestation: Confirm initialization works

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/src/main.py
git commit -m "VUW 11: Initialize FontService on startup

- Add get_font_service() dependency function
- Add initialize_font_service() with database session
- Load bundled fonts synchronously
- Detect system fonts in background task
- Update startup event to initialize font service

Fixes: Critical Issue #3 (Database session initialization)"
```

---

## VUW 12: Create Font API Routes

**Objective:** Create new font API endpoints using FontService
**Time Estimate:** 60 minutes
**Files:**
- `backend/src/api/routes/fonts.py` (NEW - ~200 lines)

#### Step-by-Step Instructions

1. **Create new file: backend/src/api/routes/fonts.py**

```python
# start backend/src/api/routes/fonts.py

"""Font management API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Dict, Any
import logging

from backend.src.services.font_service import FontService, FontMetadata
from backend.src.main import get_font_service

router = APIRouter(prefix="/fonts", tags=["fonts"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_fonts(
    source: str = Query(None, description="Filter by source: 'bundled' or 'system'"),
    service: FontService = Depends(get_font_service)
) -> List[Dict[str, Any]]:
    """
    Get all available fonts.

    Query Parameters:
    - source: Filter by source ('bundled' or 'system'). If not provided, returns all.

    Returns:
        List of font metadata objects
    """
    try:
        fonts = await service.get_all_fonts(source_filter=source)

        return [
            {
                "id": f.id,
                "name": f.name,
                "family": f.family,
                "style": f.style,
                "weight": f.weight,
                "source": f.source,
            }
            for f in fonts
        ]
    except Exception as e:
        logger.error(f"❌ Failed to list fonts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list fonts")


@router.get("/search")
async def search_fonts(
    q: str = Query(..., description="Search query for font name or family"),
    service: FontService = Depends(get_font_service)
) -> List[Dict[str, Any]]:
    """
    Search for fonts by name or family.

    Query Parameters:
    - q: Search term (required)

    Returns:
        List of matching font metadata objects
    """
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")

    try:
        fonts = await service.get_all_fonts(search_query=q)

        return [
            {
                "id": f.id,
                "name": f.name,
                "family": f.family,
                "style": f.style,
                "weight": f.weight,
                "source": f.source,
            }
            for f in fonts
        ]
    except Exception as e:
        logger.error(f"❌ Failed to search fonts: {e}")
        raise HTTPException(status_code=500, detail="Failed to search fonts")


@router.post("/refresh")
async def refresh_fonts(
    service: FontService = Depends(get_font_service)
) -> Dict[str, Any]:
    """
    Force refresh of system fonts.

    Clears cache and re-detects system-installed fonts.
    This is an async operation that may take several seconds.

    Returns:
        Status object with number of fonts detected
    """
    try:
        logger.info("🔄 Refreshing system fonts...")

        # Detect system fonts
        system_fonts = await service.detect_system_fonts()

        # Cache them
        await service.cache_fonts(system_fonts)

        logger.info(f"✅ Refreshed {len(system_fonts)} system fonts")

        return {
            "status": "success",
            "message": f"Detected and cached {len(system_fonts)} system fonts",
            "count": len(system_fonts),
        }
    except Exception as e:
        logger.error(f"❌ Font refresh failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh fonts")


@router.get("/{font_name}")
async def get_font_file(
    font_name: str,
    service: FontService = Depends(get_font_service)
) -> FileResponse:
    """
    Serve a font file by name.

    Parameters:
    - font_name: Font name to serve

    Returns:
        Font file with appropriate headers
    """
    try:
        # Get font metadata
        fonts = await service.get_all_fonts()
        font = next((f for f in fonts if f.name == font_name), None)

        if not font or not font.file_path:
            raise HTTPException(status_code=404, detail=f"Font '{font_name}' not found")

        font_path = Path(font.file_path)

        # Security: Validate path is readable
        if not font_path.exists() or not font_path.is_file():
            logger.warning(f"⚠️ Font file not found: {font_path}")
            raise HTTPException(status_code=404, detail="Font file not found")

        logger.debug(f"📥 Serving font file: {font_name}")

        return FileResponse(
            path=font_path,
            media_type="font/ttf",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Disposition": f"inline; filename={font_name}.ttf",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to serve font {font_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve font file")

# end backend/src/api/routes/fonts.py
```

2. **Include router in main.py** (after imports, around line 100)

```python
from backend.src.api.routes.fonts import router as fonts_router

# In app creation
app.include_router(fonts_router)
```

#### Verification Checklist

- [ ] File created: `backend/src/api/routes/fonts.py` (~200 lines)
- [ ] GET /fonts endpoint returns font list
- [ ] GET /fonts?source=bundled filters by source
- [ ] GET /fonts/search?q=arial searches fonts
- [ ] POST /fonts/refresh detects system fonts
- [ ] GET /fonts/{font_name} serves font file
- [ ] All endpoints use FontService dependency
- [ ] Error handling with proper HTTP status codes
- [ ] Self-attestation: Confirm endpoints work

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/src/api/routes/fonts.py backend/src/main.py
git commit -m "VUW 12: Create Font API routes

- Create fonts.py with 4 new endpoints
- GET /fonts - List all fonts with optional source filter
- GET /fonts/search?q=term - Search fonts by name/family
- POST /fonts/refresh - Detect and cache system fonts
- GET /fonts/{font_name} - Serve font file
- Use FontService dependency injection
- Add proper error handling and logging"
```

---

## VUW 13: Create Frontend Font Selector Component

**Objective:** Create React component for font selection with search
**Time Estimate:** 75 minutes
**Files:**
- `frontend/src/components/FontSelector.tsx` (NEW - ~300 lines)

#### Step-by-Step Instructions

1. **Create component file: frontend/src/components/FontSelector.tsx**

```typescript
// start frontend/src/components/FontSelector.tsx

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Search, RefreshCw, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Font {
  id: string;
  name: string;
  family: string;
  style?: string;
  weight?: number;
  source: "bundled" | "system";
}

interface FontSelectorProps {
  value?: string;
  onChange?: (fontName: string) => void;
  placeholder?: string;
}

export function FontSelector({
  value,
  onChange,
  placeholder = "Select a font...",
}: FontSelectorProps) {
  const [fonts, setFonts] = useState<Font[]>([]);
  const [filteredFonts, setFilteredFonts] = useState<Font[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Fetch fonts on mount
  useEffect(() => {
    fetchFonts();
  }, []);

  // Filter fonts when search query changes
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredFonts(fonts);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = fonts.filter(
        (f) =>
          f.name.toLowerCase().includes(query) ||
          f.family.toLowerCase().includes(query)
      );
      setFilteredFonts(filtered);
    }
  }, [searchQuery, fonts]);

  const fetchFonts = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/fonts`);
      if (!response.ok) {
        throw new Error(`Failed to fetch fonts: ${response.statusText}`);
      }

      const data = await response.json();
      setFonts(data);
      setFilteredFonts(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Font fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setIsRefreshing(true);
      setError(null);

      const response = await fetch(`${apiUrl}/fonts/refresh`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Refresh failed: ${response.statusText}`);
      }

      // Refetch font list after refresh
      await fetchFonts();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Font refresh error:", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSelectFont = (fontName: string) => {
    onChange?.(fontName);
    setIsOpen(false);
    setSearchQuery("");
  };

  const selectedFont = fonts.find((f) => f.name === value);
  const bundledFonts = filteredFonts.filter((f) => f.source === "bundled");
  const systemFonts = filteredFonts.filter((f) => f.source === "system");

  return (
    <div className="relative w-full">
      {/* Dropdown trigger button */}
      <Button
        variant="outline"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full justify-between"
      >
        <span className="truncate">
          {selectedFont ? selectedFont.name : placeholder}
        </span>
        <ChevronDown className="ml-2 h-4 w-4 opacity-50" />
      </Button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
          {/* Search bar */}
          <div className="p-3 border-b border-gray-200">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search fonts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                  autoFocus
                />
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleRefresh}
                disabled={isRefreshing}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>

          {/* Font list */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center text-gray-500">Loading fonts...</div>
            ) : error ? (
              <div className="p-4 text-center text-red-500 text-sm">{error}</div>
            ) : filteredFonts.length === 0 ? (
              <div className="p-4 text-center text-gray-500">No fonts found</div>
            ) : (
              <>
                {/* Bundled fonts section */}
                {bundledFonts.length > 0 && (
                  <>
                    <div className="px-3 py-2 text-xs font-semibold text-gray-500 bg-gray-50">
                      Bundled Fonts
                    </div>
                    {bundledFonts.map((font) => (
                      <button
                        key={font.id}
                        onClick={() => handleSelectFont(font.name)}
                        className="w-full px-3 py-2 text-left hover:bg-blue-50 flex justify-between items-center"
                      >
                        <div>
                          <div className="font-medium">{font.name}</div>
                          <div className="text-xs text-gray-500">
                            {font.family} {font.style && `• ${font.style}`}{" "}
                            {font.weight && `• ${font.weight}`}
                          </div>
                        </div>
                        {value === font.name && (
                          <div className="text-blue-600">✓</div>
                        )}
                      </button>
                    ))}
                  </>
                )}

                {/* System fonts section */}
                {systemFonts.length > 0 && (
                  <>
                    <div className="px-3 py-2 text-xs font-semibold text-gray-500 bg-gray-50 border-t">
                      System Fonts ({systemFonts.length})
                    </div>
                    {systemFonts.map((font) => (
                      <button
                        key={font.id}
                        onClick={() => handleSelectFont(font.name)}
                        className="w-full px-3 py-2 text-left hover:bg-blue-50 flex justify-between items-center"
                      >
                        <div>
                          <div className="font-medium">{font.name}</div>
                          <div className="text-xs text-gray-500">
                            {font.family} {font.style && `• ${font.style}`}{" "}
                            {font.weight && `• ${font.weight}`}
                          </div>
                        </div>
                        {value === font.name && (
                          <div className="text-blue-600">✓</div>
                        )}
                      </button>
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Close dropdown when clicking outside */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}

// end frontend/src/components/FontSelector.tsx
```

2. **Update frontend/src/app/settings/page.tsx to use new component**

Find the font selector section (around line 250) and replace with:

```typescript
import { FontSelector } from "@/components/FontSelector";

// In the render/return section:
<div className="space-y-2">
  <label className="text-sm font-medium">Font</label>
  <FontSelector
    value={fontFamily}
    onChange={setFontFamily}
    placeholder="Select a font..."
  />
</div>
```

#### Verification Checklist

- [ ] File created: `frontend/src/components/FontSelector.tsx` (~300 lines)
- [ ] Component fetches fonts from API on mount
- [ ] Search filter works for font name and family
- [ ] Bundled and system fonts displayed in separate sections
- [ ] Refresh button triggers POST /fonts/refresh
- [ ] Selected font shows checkmark
- [ ] Dropdown closes on selection
- [ ] Error handling displays messages
- [ ] Settings page updated to use component
- [ ] Self-attestation: Confirm component works

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add frontend/src/components/FontSelector.tsx frontend/src/app/settings/page.tsx
git commit -m "VUW 13: Create FontSelector React component

- Create FontSelector.tsx with dropdown UI
- Fetch fonts from GET /fonts endpoint
- Search functionality with real-time filtering
- Bundled/system fonts in separate sections
- Refresh button to detect new system fonts
- Integration with settings page
- Error handling and loading states"
```

---

## VUW 14: Create Unit Tests

**Objective:** Add pytest tests for FontService
**Time Estimate:** 90 minutes
**Files:**
- `backend/tests/test_font_service.py` (NEW - ~400 lines)

#### Step-by-Step Instructions

1. **Create test file: backend/tests/test_font_service.py**

```python
# start backend/tests/test_font_service.py

"""Unit tests for FontService."""

import pytest
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.src.services.font_service import FontService, FontMetadata
from backend.src.models import Base, SystemFont


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


@pytest.fixture
def font_service(test_db):
    """Create FontService instance with test database."""
    temp_dir = Path("/tmp/test_fonts")
    temp_dir.mkdir(exist_ok=True)
    return FontService(db_session=test_db, temp_dir=temp_dir)


@pytest.mark.asyncio
async def test_font_service_initialization(font_service):
    """Test FontService initializes without errors."""
    assert font_service is not None
    assert font_service.bundled_fonts_dir.exists()


@pytest.mark.asyncio
async def test_get_bundled_fonts(font_service):
    """Test fetching bundled fonts."""
    fonts = await font_service.get_bundled_fonts()

    # Should find at least TikTokSans-Regular.ttf
    assert isinstance(fonts, list)
    assert any(f.name == "TikTokSans-Regular" for f in fonts)


@pytest.mark.asyncio
async def test_extract_font_metadata(font_service):
    """Test metadata extraction from font file."""
    bundled = await font_service.get_bundled_fonts()
    assert len(bundled) > 0

    font = bundled[0]
    assert font.name is not None
    assert font.family is not None
    assert font.file_path is not None


@pytest.mark.asyncio
async def test_validate_font(font_service):
    """Test font validation."""
    bundled = await font_service.get_bundled_fonts()
    assert len(bundled) > 0

    font_path = Path(bundled[0].file_path)
    is_valid = await font_service.validate_font(font_path)
    assert is_valid is True


@pytest.mark.asyncio
async def test_validate_invalid_font(font_service):
    """Test validation of invalid font file."""
    invalid_path = Path("/tmp/not_a_font.ttf")
    is_valid = await font_service.validate_font(invalid_path)
    assert is_valid is False


@pytest.mark.asyncio
async def test_cache_fonts(font_service):
    """Test caching fonts to database."""
    # Create test metadata
    test_font = FontMetadata(
        id="test-font-001",
        name="Test Font",
        family="Test",
        style="normal",
        weight=400,
        file_path="/tmp/test.ttf",
        file_hash="abc123",
        is_valid=True,
        detection_timestamp=datetime.now().isoformat(),
        source="system"
    )

    await font_service.cache_fonts([test_font])

    # Verify in database
    fonts = await font_service.get_all_fonts()
    assert any(f.name == "Test Font" for f in fonts)


@pytest.mark.asyncio
async def test_get_all_fonts(font_service):
    """Test retrieving all fonts."""
    # Cache some test fonts
    test_fonts = [
        FontMetadata(
            id=f"test-{i}",
            name=f"Test Font {i}",
            family="Test",
            style="normal",
            weight=400,
            file_path=f"/tmp/test{i}.ttf",
            file_hash="abc123",
            is_valid=True,
            detection_timestamp=datetime.now().isoformat(),
            source="system"
        )
        for i in range(3)
    ]

    await font_service.cache_fonts(test_fonts)

    fonts = await font_service.get_all_fonts()
    assert len(fonts) >= 3
    assert all(isinstance(f, FontMetadata) for f in fonts)


@pytest.mark.asyncio
async def test_search_fonts(font_service):
    """Test font search functionality."""
    # Cache test fonts
    test_fonts = [
        FontMetadata(
            id="arial-001",
            name="Arial",
            family="Arial",
            source="system"
        ),
        FontMetadata(
            id="times-001",
            name="Times New Roman",
            family="Times",
            source="system"
        ),
    ]

    await font_service.cache_fonts(test_fonts)

    # Search for Arial
    results = await font_service.get_all_fonts(search_query="arial")
    assert any(f.name == "Arial" for f in results)
    assert not any(f.name == "Times New Roman" for f in results)


@pytest.mark.asyncio
async def test_source_filter(font_service):
    """Test filtering fonts by source."""
    test_fonts = [
        FontMetadata(
            id="bundled-001",
            name="Bundled Font",
            family="Test",
            source="bundled"
        ),
        FontMetadata(
            id="system-001",
            name="System Font",
            family="Test",
            source="system"
        ),
    ]

    await font_service.cache_fonts(test_fonts)

    bundled = await font_service.get_all_fonts(source_filter="bundled")
    assert any(f.source == "bundled" for f in bundled)
    assert not any(f.source == "system" for f in bundled)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# end backend/tests/test_font_service.py
```

2. **Run tests**

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
pytest tests/test_font_service.py -v
```

#### Verification Checklist

- [ ] File created: `backend/tests/test_font_service.py` (~400 lines)
- [ ] All tests import correctly
- [ ] pytest can discover tests
- [ ] `test_font_service_initialization` passes
- [ ] `test_get_bundled_fonts` finds TikTokSans-Regular.ttf
- [ ] `test_validate_font` validates correctly
- [ ] `test_cache_fonts` stores to database
- [ ] `test_search_fonts` filters by query
- [ ] `test_source_filter` filters by source
- [ ] All 9+ tests pass
- [ ] Self-attestation: Confirm tests pass

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add backend/tests/test_font_service.py
git commit -m "VUW 14: Add unit tests for FontService

- Create test_font_service.py with 9+ unit tests
- Test initialization, bundled fonts, metadata extraction
- Test font validation (valid and invalid)
- Test database caching and retrieval
- Test search and filtering functionality
- All tests use in-memory SQLite database
- ~400 lines of comprehensive test coverage"
```

---

## VUW 15: Integration Testing and Verification

**Objective:** Perform end-to-end integration testing
**Time Estimate:** 120 minutes
**Files:** None (manual testing)

#### Step-by-Step Instructions

1. **Start backend with font service**

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8008
```

Expected logs:
```
🚀 Initializing FontService...
✅ Loaded X bundled fonts
🔍 Starting background system font detection...
✅ Detected and cached Y system fonts
```

2. **Test API endpoints**

```bash
# List all fonts
curl http://localhost:8008/fonts

# Search fonts
curl "http://localhost:8008/fonts/search?q=arial"

# Filter by source
curl "http://localhost:8008/fonts?source=bundled"

# Refresh fonts
curl -X POST http://localhost:8008/fonts/refresh

# Serve font file
curl http://localhost:8008/fonts/TikTokSans-Regular -o test.ttf
```

3. **Start frontend**

```bash
cd /Users/cspenn/Documents/github/supoclip/frontend
npm run dev
```

4. **Test in browser**

- Navigate to http://localhost:3000/settings
- Click "Font" dropdown
- Verify fonts load from backend
- Search for "arial"
- Click refresh button
- Verify font selection works
- Verify changes save to preferences

5. **Verify database**

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
sqlite3 supoclip.db "SELECT COUNT(*) FROM system_fonts;"
sqlite3 supoclip.db "SELECT name, source FROM system_fonts LIMIT 10;"
```

#### Verification Checklist

- [ ] Backend starts with "FontService initialized"
- [ ] GET /fonts returns list of fonts
- [ ] GET /fonts?source=bundled filters correctly
- [ ] GET /fonts/search?q=arial finds fonts
- [ ] POST /fonts/refresh detects system fonts
- [ ] GET /fonts/{name} serves font file
- [ ] Frontend FontSelector component loads
- [ ] Search works in dropdown
- [ ] Refresh button detects new fonts
- [ ] Font selection updates preferences
- [ ] Database contains system_fonts table
- [ ] Bundled and system fonts both cached
- [ ] runningCheckpython.sh shows 100% passing
- [ ] Self-attestation: Confirm all integration tests pass

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 15: Integration testing and verification

- Verified backend API endpoints work
- Tested font listing, search, refresh
- Verified frontend FontSelector component
- Confirmed database persistence
- Validated end-to-end font detection workflow
- All systems integrated and functional

Phase 1 Complete: System Fonts Detection
- 15 sequential VUWs completed
- All critical issues fixed
- 100% test coverage
- Ready for Phase 2: Google Fonts integration"
```

---

## Summary

This revised plan addresses all 6 critical blocking issues and includes:

**VUWs 1-5:** Foundation (dependencies, services, validation, metadata)
**VUW 6:** Old endpoint removal
**VUWs 7-9:** Database models and migrations
**VUWs 10-12:** FontService implementation and API routes
**VUW 13:** Frontend React component
**VUW 14:** Unit tests
**VUW 15:** Integration testing

**Total Effort:** 17-20 hours
**Status:** Ready for implementation
