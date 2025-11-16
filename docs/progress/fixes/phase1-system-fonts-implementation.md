# Phase 1: System Fonts Detection Implementation Plan

**Date:** November 15, 2025
**Status:** Planning
**Target Branch:** `feature/system-fonts-detection`
**Total Estimated Effort:** 8-10 hours across 12 VUWs

---

## Executive Summary

This document provides a step-by-step implementation plan for Phase 1 of the SupoClip font system expansion. Phase 1 focuses on detecting system-installed fonts and making them available to users alongside bundled fonts.

**Phase 1 Scope:**
- Auto-detect fonts from system (macOS, Linux, Windows)
- Validate font compatibility with MoviePy/ImageMagick
- Cache detected fonts in SQLite database
- Display system fonts in font selector dropdown
- Add search functionality to find fonts by name
- Add refresh button to re-detect system fonts

**Phase 1 Deliverables:**
- 7 new backend files/modifications
- 2 frontend component enhancements
- 1 database schema extension
- 12 VUWs with 100% passing tests each
- Complete end-to-end integration

---

## Architecture Overview

### System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FontSelector Component                                  │   │
│  │  - Display bundled fonts (Tier 1)                        │   │
│  │  - Display system fonts (Tier 2)                         │   │
│  │  - Search functionality (fuzzy match)                    │   │
│  │  - Refresh button (re-detect system fonts)               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Font API Routes (/fonts.py)                             │   │
│  │  - GET /fonts - List all fonts (bundled + system)        │   │
│  │  - GET /fonts/search?q=name - Search fonts              │   │
│  │  - POST /fonts/refresh - Detect & cache system fonts     │   │
│  │  - GET /fonts/{name} - Serve font file                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                             ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FontService (font_service.py)                           │   │
│  │  - Detect system fonts (matplotlib)                      │   │
│  │  - Validate font compatibility (fonttools)               │   │
│  │  - Extract font metadata                                 │   │
│  │  - Cache management (SQLite)                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Database (SQLite)                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  system_fonts table                                      │   │
│  │  - font_id (UUID)                                        │   │
│  │  - name (string)                                         │   │
│  │  - family (string)                                       │   │
│  │  - style (string)                                        │   │
│  │  - weight (int)                                          │   │
│  │  - file_path (string)                                    │   │
│  │  - file_hash (string) - detect changes                   │   │
│  │  - is_valid (bool)                                       │   │
│  │  - detection_timestamp (datetime)                        │   │
│  │  - metadata_json (JSON)                                  │   │
│  │  - source (enum) - 'bundled' | 'system'                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Application Startup
    ↓
FontService.initialize()
    ├─ Check SQLite cache
    ├─ Load bundled fonts from backend/fonts/
    ├─ If cache invalid/empty:
    │   ├─ Detect system fonts (matplotlib)
    │   ├─ Validate each font (fonttools)
    │   ├─ Extract metadata
    │   └─ Cache in SQLite
    └─ Return cached fonts

User Requests Font Selector
    ↓
GET /fonts
    ├─ Query SQLite cache
    ├─ Separate: bundled vs system
    ├─ Format: {name, family, weight, style, source}
    └─ Return to frontend

User Searches for Font
    ↓
GET /fonts/search?q=arial
    ├─ Query SQLite (fuzzy match on name/family)
    └─ Return matching fonts

User Refreshes Fonts
    ↓
POST /fonts/refresh
    ├─ Clear SQLite cache
    ├─ Re-detect system fonts
    ├─ Validate and cache
    └─ Return updated fonts
```

### Database Schema

#### system_fonts Table

```sql
CREATE TABLE IF NOT EXISTS system_fonts (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    family VARCHAR(255) NOT NULL,
    style VARCHAR(50),                          -- 'normal', 'italic', etc.
    weight INTEGER,                             -- 100, 400, 700, etc.
    file_path VARCHAR(500),                     -- Full path to font file
    file_hash VARCHAR(64),                      -- SHA256 hash for change detection
    is_valid BOOLEAN DEFAULT TRUE,              -- Compatibility with MoviePy
    detection_timestamp TIMESTAMP,              -- When font was detected
    metadata_json JSON,                         -- Additional font metadata
    source VARCHAR(20) NOT NULL,                -- 'bundled' or 'system'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_system_fonts_family ON system_fonts(family);
CREATE INDEX idx_system_fonts_source ON system_fonts(source);
CREATE UNIQUE INDEX idx_system_fonts_name_file ON system_fonts(name, file_path);
```

---

## VUW Breakdown

### VUW 1: Add Dependencies and Create FontService Skeleton

**Objective:** Set up project dependencies and create the basic FontService class structure
**Time Estimate:** 30 minutes
**Files:**
- `backend/pyproject.toml` (MODIFY)
- `backend/src/services/font_service.py` (NEW)

#### Prerequisites
- Python 3.11+ (already installed)
- `uv` package manager available

#### Step-by-Step Instructions

1. **Update pyproject.toml with new dependencies**

Navigate to backend directory:
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
```

Add these dependencies to `pyproject.toml` under `[project] dependencies` section:
```
matplotlib>=3.8.0        # For system font detection
fonttools>=4.45.0        # For font validation and metadata
hashlib                  # Built-in (for file hashing)
```

2. **Create FontService skeleton**

Create new file: `/Users/cspenn/Documents/github/supoclip/backend/src/services/font_service.py`

```python
# start backend/src/services/font_service.py

"""
Font detection and management service for SupoClip.

Provides system-wide font detection, validation, and caching.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import asyncio
from datetime import datetime
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class FontMetadata:
    """Metadata for a single font file."""
    id: str
    name: str
    family: str
    style: Optional[str] = None
    weight: Optional[int] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    is_valid: bool = True
    detection_timestamp: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    source: str = "system"  # 'bundled' or 'system'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class FontService:
    """
    Service for managing system and bundled fonts.

    Responsibilities:
    - Detect system-installed fonts (cross-platform)
    - Validate fonts for MoviePy/ImageMagick compatibility
    - Extract font metadata
    - Cache detected fonts in SQLite
    - Provide search and filtering capabilities
    """

    def __init__(self, db_session=None, temp_dir: Optional[Path] = None):
        """
        Initialize FontService.

        Args:
            db_session: SQLAlchemy async session for database access
            temp_dir: Temporary directory for font processing
        """
        self.db_session = db_session
        self.temp_dir = temp_dir or Path("/tmp")
        self.bundled_fonts_dir = Path(__file__).parent.parent.parent / "fonts"
        self._font_cache: Optional[List[FontMetadata]] = None
        self._is_initialized = False

    async def initialize(self) -> None:
        """
        Initialize font service on startup.

        Loads bundled fonts and detects system fonts if cache is invalid.
        """
        logger.info("Initializing FontService...")
        # TODO: Implement in VUW 7
        self._is_initialized = True

    async def get_bundled_fonts(self) -> List[FontMetadata]:
        """
        Get list of bundled fonts from backend/fonts/ directory.

        Returns:
            List of FontMetadata objects for bundled fonts
        """
        # TODO: Implement in VUW 2
        return []

    async def detect_system_fonts(self) -> List[FontMetadata]:
        """
        Detect fonts installed on the system.

        Uses matplotlib.font_manager for cross-platform detection.

        Returns:
            List of detected FontMetadata objects
        """
        # TODO: Implement in VUW 2
        return []

    async def validate_font(self, font_path: Path) -> bool:
        """
        Validate font compatibility with MoviePy/ImageMagick.

        Args:
            font_path: Path to font file

        Returns:
            True if font is compatible, False otherwise
        """
        # TODO: Implement in VUW 3
        return False

    async def extract_font_metadata(self, font_path: Path) -> Optional[FontMetadata]:
        """
        Extract metadata from a font file.

        Args:
            font_path: Path to font file

        Returns:
            FontMetadata object or None if extraction fails
        """
        # TODO: Implement in VUW 4
        return None

    async def cache_fonts(self, fonts: List[FontMetadata]) -> None:
        """
        Cache detected fonts in SQLite database.

        Args:
            fonts: List of FontMetadata to cache
        """
        # TODO: Implement in VUW 5
        pass

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
        # TODO: Implement in VUW 8
        return []

    async def refresh_system_fonts(self) -> List[FontMetadata]:
        """
        Force refresh of system fonts (clear cache and re-detect).

        Returns:
            List of newly detected FontMetadata objects
        """
        # TODO: Implement in VUW 10
        return []

# end backend/src/services/font_service.py
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] `cd backend && uv sync` completes without errors
- [ ] File created: `/Users/cspenn/Documents/github/supoclip/backend/src/services/font_service.py`
- [ ] FontService class exists with all method signatures
- [ ] FontMetadata dataclass defined with proper type hints
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 1: Add dependencies and create FontService skeleton

- Add matplotlib and fonttools dependencies
- Create services/font_service.py with FontService class
- Define FontMetadata dataclass
- Stub all required methods with TODO comments"
```

---

### VUW 2: Implement System Font Detection

**Objective:** Implement cross-platform system font detection using matplotlib and fonttools
**Time Estimate:** 45 minutes
**Files:**
- `backend/src/services/font_service.py` (MODIFY)

#### Step-by-Step Instructions

1. **Import required modules at top of file**

Add to imports section:
```python
import matplotlib.font_manager as fm
from fontTools.ttLib import TTFont
from fontTools.ttLib.ttFont import TTFontFormatError
```

2. **Implement get_bundled_fonts() method**

Replace the stub in FontService:
```python
async def get_bundled_fonts(self) -> List[FontMetadata]:
    """
    Get list of bundled fonts from backend/fonts/ directory.

    Returns:
        List of FontMetadata objects for bundled fonts
    """
    bundled: List[FontMetadata] = []

    if not self.bundled_fonts_dir.exists():
        logger.warning(f"Bundled fonts directory not found: {self.bundled_fonts_dir}")
        return bundled

    for font_file in self.bundled_fonts_dir.glob("*.ttf"):
        try:
            metadata = await self.extract_font_metadata(font_file)
            if metadata:
                metadata.source = "bundled"
                bundled.append(metadata)
                logger.debug(f"Loaded bundled font: {metadata.name}")
        except Exception as e:
            logger.warning(f"Failed to load bundled font {font_file.name}: {e}")

    logger.info(f"Loaded {len(bundled)} bundled fonts")
    return bundled
```

3. **Implement detect_system_fonts() method**

Replace the stub:
```python
async def detect_system_fonts(self) -> List[FontMetadata]:
    """
    Detect fonts installed on the system.

    Uses matplotlib.font_manager for cross-platform detection.

    Returns:
        List of detected FontMetadata objects
    """
    detected: List[FontMetadata] = []

    # Use matplotlib's font manager for cross-platform detection
    # Works on macOS, Linux, Windows
    font_paths = fm.findSystemFonts()

    logger.info(f"Found {len(font_paths)} system font files")

    for font_path in font_paths:
        try:
            # Skip if font is in bundled directory
            if str(font_path).startswith(str(self.bundled_fonts_dir)):
                continue

            # Only process TTF fonts for consistency
            if not font_path.lower().endswith(('.ttf', '.otf')):
                continue

            path_obj = Path(font_path)

            # Skip if file is not readable
            if not path_obj.exists() or not path_obj.is_file():
                continue

            metadata = await self.extract_font_metadata(path_obj)
            if metadata and await self.validate_font(path_obj):
                metadata.source = "system"
                detected.append(metadata)
                logger.debug(f"Detected system font: {metadata.name}")

        except Exception as e:
            logger.debug(f"Failed to process font {font_path}: {e}")
            continue

    logger.info(f"Successfully detected {len(detected)} valid system fonts")
    return detected
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] Can import matplotlib.font_manager without errors
- [ ] `detect_system_fonts()` returns list (may be empty in test)
- [ ] `get_bundled_fonts()` finds TikTokSans-Regular.ttf font
- [ ] Logging output shows font detection progress
- [ ] No hardcoded paths (all use Path objects)
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 2: Implement system font detection

- Add matplotlib.font_manager imports
- Implement get_bundled_fonts() to load fonts from backend/fonts/
- Implement detect_system_fonts() using matplotlib
- Cross-platform detection (macOS, Linux, Windows)
- Filter to TTF/OTF files only
- Add comprehensive logging"
```

---

### VUW 3: Implement Font Validation for MoviePy Compatibility

**Objective:** Validate fonts work with MoviePy/ImageMagick using fonttools
**Time Estimate:** 40 minutes
**Files:**
- `backend/src/services/font_service.py` (MODIFY)

#### Step-by-Step Instructions

1. **Implement validate_font() method**

Replace stub with:
```python
async def validate_font(self, font_path: Path) -> bool:
    """
    Validate font compatibility with MoviePy/ImageMagick.

    Checks:
    1. File is readable and has valid TTF structure
    2. Font has required name table entries
    3. Font can be loaded by fonttools

    Args:
        font_path: Path to font file

    Returns:
        True if font is compatible, False otherwise
    """
    try:
        # Basic file checks
        if not font_path.exists() or not font_path.is_file():
            logger.debug(f"Font file not found: {font_path}")
            return False

        # Check file is readable
        if not font_path.stat().st_size > 0:
            logger.debug(f"Font file is empty: {font_path}")
            return False

        # Try to load with fonttools
        try:
            font = TTFont(str(font_path))
        except TTFontFormatError as e:
            logger.debug(f"Invalid TTF format {font_path}: {e}")
            return False
        except Exception as e:
            logger.debug(f"Cannot load font {font_path}: {e}")
            return False

        # Validate required tables for text rendering
        required_tables = {'head', 'hhea', 'maxp', 'hmtx'}
        if not required_tables.issubset(set(font.keys())):
            logger.debug(f"Font {font_path} missing required tables")
            return False

        # Check for at least one cmap table (character mapping)
        if 'cmap' not in font:
            logger.debug(f"Font {font_path} missing character mapping")
            return False

        logger.debug(f"Font validation passed: {font_path.name}")
        return True

    except Exception as e:
        logger.debug(f"Unexpected error validating {font_path}: {e}")
        return False
```

2. **Update detect_system_fonts() to validate before returning**

The method already calls `validate_font()`, so validation is built in.

3. **Test with bundled fonts**

Both bundled fonts should pass validation. Update any test later.

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] `validate_font()` returns True for TikTokSans-Regular.ttf
- [ ] `validate_font()` returns False for non-existent files
- [ ] `validate_font()` returns False for invalid font files
- [ ] fonttools TTFont can be imported and used
- [ ] Error handling prevents crashes on invalid fonts
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 3: Implement font validation for MoviePy compatibility

- Use fonttools.ttLib.TTFont for font validation
- Check for valid TTF structure and required tables
- Verify character mapping (cmap table) exists
- Graceful error handling for invalid fonts
- Log validation failures for debugging"
```

---

### VUW 4: Implement Font Metadata Extraction

**Objective:** Extract font metadata (family, style, weight) using fonttools
**Time Estimate:** 45 minutes
**Files:**
- `backend/src/services/font_service.py` (MODIFY)

#### Step-by-Step Instructions

1. **Implement extract_font_metadata() method**

Replace stub with:
```python
async def extract_font_metadata(self, font_path: Path) -> Optional[FontMetadata]:
    """
    Extract metadata from a font file using fonttools.

    Extracts:
    - Font family name
    - Font style (normal, italic, etc.)
    - Font weight (100, 400, 700, etc.)
    - File hash for change detection
    - Additional metadata as JSON

    Args:
        font_path: Path to font file

    Returns:
        FontMetadata object or None if extraction fails
    """
    try:
        if not font_path.exists():
            logger.debug(f"Font file not found: {font_path}")
            return None

        # Load font with fonttools
        try:
            font = TTFont(str(font_path))
        except Exception as e:
            logger.debug(f"Cannot load font {font_path} for metadata: {e}")
            return None

        # Extract font name
        font_name = font_path.stem  # Use filename as display name

        # Try to get family name from name table
        family_name = self._extract_name_from_font(font, "Family")
        if not family_name:
            family_name = font_name

        # Extract style (normal, italic, bold, etc.)
        style = self._extract_style_from_font(font, font_path)

        # Extract weight
        weight = self._extract_weight_from_font(font, font_path)

        # Calculate file hash for change detection
        file_hash = self._calculate_file_hash(font_path)

        # Extract additional metadata
        metadata_dict = self._extract_additional_metadata(font)

        # Create FontMetadata object
        metadata = FontMetadata(
            id=str(font_name).replace(" ", "-").lower(),
            name=font_name,
            family=family_name,
            style=style,
            weight=weight,
            file_path=str(font_path.absolute()),
            file_hash=file_hash,
            is_valid=True,
            detection_timestamp=datetime.now().isoformat(),
            metadata_json=metadata_dict,
            source="system"  # Override in calling code
        )

        logger.debug(f"Extracted metadata: {font_name} ({family_name}, {style}, w:{weight})")
        return metadata

    except Exception as e:
        logger.debug(f"Failed to extract metadata from {font_path}: {e}")
        return None

def _extract_name_from_font(self, font: TTFont, name_type: str) -> Optional[str]:
    """Extract name from font's name table."""
    try:
        if 'name' not in font:
            return None

        name_table = font['name']

        # Name IDs: 1=Family, 2=Subfamily, 4=Full name
        name_id_map = {"Family": 1, "Subfamily": 2, "Full": 4}
        target_id = name_id_map.get(name_type, 1)

        # Try Unicode name records first (platform 3)
        for record in name_table.names:
            if record.nameID == target_id and record.platformID == 3:
                try:
                    return record.toUnicode()
                except:
                    pass

        # Fallback to any platform
        for record in name_table.names:
            if record.nameID == target_id:
                try:
                    return record.toUnicode()
                except:
                    pass

        return None
    except Exception:
        return None

def _extract_style_from_font(self, font: TTFont, font_path: Path) -> Optional[str]:
    """Determine font style (normal, italic, bold, etc.)."""
    try:
        # Try from post table
        if 'post' in font:
            post = font['post']
            if hasattr(post, 'isFixedPitch'):
                return "monospace" if post.isFixedPitch else "normal"

        # Try from head table
        if 'head' in font:
            head = font['head']
            if hasattr(head, 'macStyle'):
                style_bits = head.macStyle
                if style_bits & 0x02:  # Italic bit
                    return "italic"
                if style_bits & 0x01:  # Bold bit
                    return "bold"

        # Infer from filename
        filename_lower = font_path.stem.lower()
        if "italic" in filename_lower:
            return "italic"
        if "bold" in filename_lower:
            return "bold"

        return "normal"
    except Exception:
        return "normal"

def _extract_weight_from_font(self, font: TTFont, font_path: Path) -> Optional[int]:
    """Determine font weight (100, 400, 700, etc.)."""
    try:
        # Try from OS/2 table
        if 'OS/2' in font:
            os2 = font['OS/2']
            if hasattr(os2, 'usWeightClass'):
                weight = os2.usWeightClass
                # Validate weight is in valid range
                if 100 <= weight <= 900 and weight % 100 == 0:
                    return weight

        # Try from head table
        if 'head' in font:
            head = font['head']
            if hasattr(head, 'macStyle'):
                style_bits = head.macStyle
                if style_bits & 0x01:  # Bold bit
                    return 700

        # Infer from filename
        filename_lower = font_path.stem.lower()
        if "light" in filename_lower:
            return 300
        if "regular" in filename_lower:
            return 400
        if "semibold" in filename_lower:
            return 600
        if "bold" in filename_lower:
            return 700
        if "black" in filename_lower:
            return 900

        return 400  # Default to normal weight
    except Exception:
        return 400

def _calculate_file_hash(self, font_path: Path) -> str:
    """Calculate SHA256 hash of font file for change detection."""
    try:
        sha256_hash = hashlib.sha256()
        with open(font_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]  # Use first 16 chars
    except Exception as e:
        logger.debug(f"Failed to calculate hash for {font_path}: {e}")
        return ""

def _extract_additional_metadata(self, font: TTFont) -> Dict[str, Any]:
    """Extract additional metadata about the font."""
    metadata = {}
    try:
        # Number of glyphs
        if 'maxp' in font:
            metadata['glyphs'] = font['maxp'].numGlyphs

        # Supported encodings
        if 'cmap' in font:
            encodings = []
            for table in font['cmap'].tables:
                encodings.append(f"platform{table.platformID}_enc{table.platEncID}")
            metadata['encodings'] = encodings[:3]  # Limit to first 3

        return metadata
    except Exception:
        return {}
```

2. **Add helper methods to FontService class**

The helper methods are defined above. They should be added to the FontService class.

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] `extract_font_metadata()` returns FontMetadata for valid fonts
- [ ] Family name extracted correctly from TikTokSans-Regular.ttf
- [ ] Weight correctly identified (400 for Regular, 700 for Bold if present)
- [ ] Style extracted or inferred from filename
- [ ] File hash calculated successfully
- [ ] No crashes on fonts with missing name tables
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 4: Implement font metadata extraction

- Extract family name, style, weight from TTF files
- Use fonttools name table parsing with fallbacks
- Calculate SHA256 file hash for change detection
- Infer metadata from filename when tables unavailable
- Extract additional metadata (glyph count, encodings)"
```

---

### VUW 5: Add SystemFont Database Model and Schema

**Objective:** Create database model for caching system fonts
**Time Estimate:** 40 minutes
**Files:**
- `backend/src/models.py` (MODIFY)
- `init.sql` (MODIFY)

#### Step-by-Step Instructions

1. **Add SystemFont model to backend/src/models.py**

Find the last line of the GeneratedClip class (around line 117). Add new model before the end of file:

```python
class SystemFont(Base):
    __tablename__ = "system_fonts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid_string)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    family: Mapped[str] = mapped_column(String(255), nullable=False)
    style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'normal', 'italic'
    weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 100, 400, 700, etc.
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    detection_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'system'"))  # 'bundled' or 'system'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Add check constraint for valid sources
    __table_args__ = (
        CheckConstraint("source IN ('bundled', 'system')", name="check_font_source"),
    )
```

2. **Add system_fonts table to init.sql**

Find the end of the `generated_clips` table (around line 76). Add new table:

```sql
-- System fonts table (for caching detected system fonts)
CREATE TABLE system_fonts (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name VARCHAR(255) NOT NULL UNIQUE,
    family VARCHAR(255) NOT NULL,
    style VARCHAR(50),                          -- 'normal', 'italic', 'bold', etc.
    weight INTEGER,                             -- 100, 200, 300, 400, 500, 600, 700, 800, 900
    file_path VARCHAR(500),                     -- Full absolute path to font file
    file_hash VARCHAR(64),                      -- SHA256 hash (first 16 chars) for change detection
    is_valid BOOLEAN NOT NULL DEFAULT true,     -- Compatibility with MoviePy/ImageMagick
    detection_timestamp TIMESTAMP WITH TIME ZONE,  -- When font was detected
    metadata_json JSON,                         -- Additional font metadata (glyphs, encodings, etc.)
    source VARCHAR(20) NOT NULL DEFAULT 'system',  -- 'bundled' or 'system'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_font_source CHECK (source IN ('bundled', 'system'))
);

-- Indexes for fast queries
CREATE INDEX idx_system_fonts_family ON system_fonts(family);
CREATE INDEX idx_system_fonts_source ON system_fonts(source);
CREATE INDEX idx_system_fonts_is_valid ON system_fonts(is_valid);
CREATE UNIQUE INDEX idx_system_fonts_name_file ON system_fonts(name, file_path);
```

3. **Update Prisma schema (frontend)**

Add to `frontend/prisma/schema.prisma`:

```prisma
model SystemFont {
  id                    String      @id @default(uuid())
  name                  String      @unique
  family                String
  style                 String?
  weight                Int?
  filePath              String?
  fileHash              String?
  isValid               Boolean     @default(true)
  detectionTimestamp    DateTime?
  metadataJson          Json?
  source                String      @default("system") // 'bundled' or 'system'
  createdAt             DateTime    @default(now())
  updatedAt             DateTime    @updatedAt

  @@index([family])
  @@index([source])
  @@unique([name, filePath])
}
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] SystemFont model has all required fields with correct types
- [ ] Models.py imports all new types (JSON for metadata_json)
- [ ] Check constraint for source in both SQL and Python
- [ ] init.sql syntax is valid
- [ ] Indexes created for performance (family, source, is_valid)
- [ ] Prisma schema updated with SystemFont model
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 5: Add SystemFont database model

- Add SystemFont SQLAlchemy model in models.py
- Create system_fonts table in init.sql
- Add indexes for family, source, is_valid
- Add check constraint for source enum
- Update Prisma schema for frontend access"
```

---

### VUW 6: Create Font API Routes

**Objective:** Create FastAPI endpoints for font operations
**Time Estimate:** 50 minutes
**Files:**
- `backend/src/api/routes/fonts.py` (NEW)
- `backend/src/main.py` (MODIFY) - Replace existing font endpoints

#### Step-by-Step Instructions

1. **Create new file: backend/src/api/routes/fonts.py**

```python
# start backend/src/api/routes/fonts.py

"""
Font API endpoints for SupoClip.

Provides endpoints for:
- List all fonts (bundled and system)
- Search fonts by name/family
- Refresh system font detection
- Serve font files
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import logging

from src.services.font_service import FontService, FontMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fonts", tags=["fonts"])

# Global FontService instance (initialized in main.py startup)
_font_service: Optional[FontService] = None


def set_font_service(service: FontService) -> None:
    """Set the global FontService instance."""
    global _font_service
    _font_service = service


def get_font_service() -> FontService:
    """Get the global FontService instance."""
    if _font_service is None:
        raise HTTPException(
            status_code=503,
            detail="Font service not initialized. Please try again later."
        )
    return _font_service


# Response Models
class FontInfo(BaseModel):
    """Response model for a single font."""
    id: str
    name: str
    family: str
    style: Optional[str] = None
    weight: Optional[int] = None
    source: str  # 'bundled' or 'system'


class FontsListResponse(BaseModel):
    """Response model for fonts list endpoint."""
    fonts: List[FontInfo]
    bundled_count: int
    system_count: int
    total_count: int


class FontSearchResponse(BaseModel):
    """Response model for font search."""
    results: List[FontInfo]
    query: str
    count: int


class FontRefreshResponse(BaseModel):
    """Response model for font refresh endpoint."""
    message: str
    detected_count: int
    system_fonts: List[FontInfo]
    total_fonts: int


# Endpoints

@router.get("", response_model=FontsListResponse)
async def list_fonts(
    source: Optional[str] = Query(None, description="Filter by source: 'bundled' or 'system'")
) -> FontsListResponse:
    """
    Get list of all available fonts.

    Query Parameters:
    - source: Optional filter ('bundled' or 'system')

    Returns:
        FontsListResponse with fonts organized by source
    """
    try:
        service = get_font_service()
        fonts = await service.get_all_fonts(source_filter=source)

        # Separate by source
        bundled = [f for f in fonts if f.source == "bundled"]
        system = [f for f in fonts if f.source == "system"]

        # Convert to response model
        font_infos = [
            FontInfo(
                id=f.id,
                name=f.name,
                family=f.family,
                style=f.style,
                weight=f.weight,
                source=f.source
            )
            for f in fonts
        ]

        return FontsListResponse(
            fonts=font_infos,
            bundled_count=len(bundled),
            system_count=len(system),
            total_count=len(fonts)
        )

    except Exception as e:
        logger.error(f"Error listing fonts: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing fonts: {str(e)}")


@router.get("/search")
async def search_fonts(
    q: str = Query(..., min_length=1, description="Search query")
) -> FontSearchResponse:
    """
    Search fonts by name or family with fuzzy matching.

    Query Parameters:
    - q: Required search query (minimum 1 character)

    Returns:
        FontSearchResponse with matching fonts
    """
    try:
        service = get_font_service()
        fonts = await service.get_all_fonts(search_query=q)

        font_infos = [
            FontInfo(
                id=f.id,
                name=f.name,
                family=f.family,
                style=f.style,
                weight=f.weight,
                source=f.source
            )
            for f in fonts
        ]

        return FontSearchResponse(
            results=font_infos,
            query=q,
            count=len(font_infos)
        )

    except Exception as e:
        logger.error(f"Error searching fonts: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching fonts: {str(e)}")


@router.post("/refresh")
async def refresh_fonts(background_tasks: BackgroundTasks) -> FontRefreshResponse:
    """
    Refresh system font detection.

    Clears cache and re-detects system fonts.
    Can be run in background for large systems.

    Returns:
        FontRefreshResponse with newly detected fonts
    """
    try:
        service = get_font_service()
        new_fonts = await service.refresh_system_fonts()

        # Get all fonts after refresh
        all_fonts = await service.get_all_fonts()

        font_infos = [
            FontInfo(
                id=f.id,
                name=f.name,
                family=f.family,
                style=f.style,
                weight=f.weight,
                source=f.source
            )
            for f in new_fonts
        ]

        return FontRefreshResponse(
            message=f"Detected {len(new_fonts)} system fonts",
            detected_count=len(new_fonts),
            system_fonts=font_infos,
            total_fonts=len(all_fonts)
        )

    except Exception as e:
        logger.error(f"Error refreshing fonts: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing fonts: {str(e)}")


@router.get("/{font_name}")
async def get_font_file(font_name: str):
    """
    Get font file for serving to frontend.

    Serves TTF/OTF font files for use in browser @font-face rules.

    Args:
        font_name: Font name or ID

    Returns:
        Font file with appropriate headers
    """
    try:
        service = get_font_service()
        fonts = await service.get_all_fonts()

        # Find font by name or ID
        font = None
        for f in fonts:
            if f.name == font_name or f.id == font_name:
                font = f
                break

        if not font or not font.file_path:
            raise HTTPException(status_code=404, detail=f"Font not found: {font_name}")

        # Return file with correct headers
        from pathlib import Path
        font_path = Path(font.file_path)

        if not font_path.exists():
            raise HTTPException(status_code=404, detail=f"Font file not found: {font.file_path}")

        # Return file response
        from fastapi.responses import FileResponse
        return FileResponse(
            path=font_path,
            media_type="font/ttf",
            headers={"Cache-Control": "public, max-age=86400"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving font {font_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving font: {str(e)}")

# end backend/src/api/routes/fonts.py
```

2. **Update backend/src/main.py - Replace old font endpoints**

Find the old `/fonts` endpoints (around line 669-710) and replace with:

```python
# Include the new fonts router
from src.api.routes.fonts import router as fonts_router, set_font_service

app.include_router(fonts_router)

# In the startup event, initialize font service:
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...

    # Initialize FontService
    from src.services.font_service import FontService
    font_service = FontService(db_session=None, temp_dir=Path(TEMP_DIR))
    await font_service.initialize()
    set_font_service(font_service)

    logger.info("FontService initialized and ready")
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] New file created: `backend/src/api/routes/fonts.py`
- [ ] All four endpoints defined (list, search, refresh, get_font_file)
- [ ] Response models properly typed (FontInfo, FontsListResponse, etc.)
- [ ] Error handling returns proper HTTP status codes
- [ ] Font service injection works correctly
- [ ] Old font endpoints removed from main.py
- [ ] Router included in FastAPI app
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 6: Create font API routes

- New file: api/routes/fonts.py with 4 endpoints
- GET /fonts - List all fonts with filtering
- GET /fonts/search?q=term - Search fonts
- POST /fonts/refresh - Refresh system fonts
- GET /fonts/{name} - Serve font file
- Remove old font endpoints from main.py"
```

---

### VUW 7: Implement FontService Database Caching

**Objective:** Implement database caching logic for detected fonts
**Time Estimate:** 45 minutes
**Files:**
- `backend/src/services/font_service.py` (MODIFY)

#### Step-by-Step Instructions

1. **Update imports and add database access**

Add to imports:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from src.models import SystemFont
from sqlalchemy.orm import sessionmaker
```

2. **Update __init__ to accept proper db_session**

Modify the `__init__` method:
```python
def __init__(self, db_session: Optional[AsyncSession] = None, temp_dir: Optional[Path] = None):
    """
    Initialize FontService.

    Args:
        db_session: SQLAlchemy async session for database access
        temp_dir: Temporary directory for font processing
    """
    self.db_session = db_session
    self.temp_dir = temp_dir or Path("/tmp")
    self.bundled_fonts_dir = Path(__file__).parent.parent.parent / "fonts"
    self._font_cache: Optional[List[FontMetadata]] = None
    self._is_initialized = False
```

3. **Implement cache_fonts() method**

Replace stub:
```python
async def cache_fonts(self, fonts: List[FontMetadata]) -> None:
    """
    Cache detected fonts in SQLite database.

    Args:
        fonts: List of FontMetadata to cache
    """
    if not self.db_session:
        logger.warning("Database session not available, skipping font cache")
        return

    try:
        for font in fonts:
            # Check if font already exists
            stmt = select(SystemFont).where(SystemFont.name == font.name)
            result = await self.db_session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing font
                existing.family = font.family
                existing.style = font.style
                existing.weight = font.weight
                existing.file_path = font.file_path
                existing.file_hash = font.file_hash
                existing.is_valid = font.is_valid
                existing.detection_timestamp = datetime.fromisoformat(font.detection_timestamp) if font.detection_timestamp else None
                existing.metadata_json = font.metadata_json
                existing.source = font.source
                logger.debug(f"Updated cached font: {font.name}")
            else:
                # Insert new font
                db_font = SystemFont(
                    id=font.id,
                    name=font.name,
                    family=font.family,
                    style=font.style,
                    weight=font.weight,
                    file_path=font.file_path,
                    file_hash=font.file_hash,
                    is_valid=font.is_valid,
                    detection_timestamp=datetime.fromisoformat(font.detection_timestamp) if font.detection_timestamp else None,
                    metadata_json=font.metadata_json,
                    source=font.source
                )
                self.db_session.add(db_font)
                logger.debug(f"Cached new font: {font.name}")

        # Commit all changes
        await self.db_session.commit()
        logger.info(f"Cached {len(fonts)} fonts in database")

    except Exception as e:
        await self.db_session.rollback()
        logger.error(f"Error caching fonts: {e}")
        raise
```

4. **Implement initialize() method**

Replace stub:
```python
async def initialize(self) -> None:
    """
    Initialize font service on startup.

    Loads bundled fonts and detects system fonts if cache is invalid.
    """
    logger.info("Initializing FontService...")

    try:
        # Load bundled fonts first
        bundled = await self.get_bundled_fonts()
        logger.info(f"Loaded {len(bundled)} bundled fonts")

        # Detect system fonts
        system = await self.detect_system_fonts()
        logger.info(f"Detected {len(system)} system fonts")

        # Combine and cache
        all_fonts = bundled + system

        if self.db_session:
            await self.cache_fonts(all_fonts)
            logger.info(f"Cached {len(all_fonts)} total fonts")

        # Store in memory cache
        self._font_cache = all_fonts
        self._is_initialized = True

        logger.info("FontService initialization complete")

    except Exception as e:
        logger.error(f"FontService initialization failed: {e}")
        self._is_initialized = False
        raise
```

5. **Implement get_all_fonts() with filtering**

Replace stub:
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
    try:
        # Return memory cache if available
        if self._font_cache is None:
            if self.db_session:
                # Load from database
                stmt = select(SystemFont)
                if source_filter:
                    stmt = stmt.where(SystemFont.source == source_filter)

                result = await self.db_session.execute(stmt)
                db_fonts = result.scalars().all()

                fonts = [
                    FontMetadata(
                        id=f.id,
                        name=f.name,
                        family=f.family,
                        style=f.style,
                        weight=f.weight,
                        file_path=f.file_path,
                        file_hash=f.file_hash,
                        is_valid=f.is_valid,
                        detection_timestamp=f.detection_timestamp.isoformat() if f.detection_timestamp else None,
                        metadata_json=f.metadata_json,
                        source=f.source
                    )
                    for f in db_fonts
                ]
            else:
                fonts = []
        else:
            # Use memory cache
            fonts = self._font_cache.copy()
            if source_filter:
                fonts = [f for f in fonts if f.source == source_filter]

        # Apply search filter
        if search_query:
            fonts = self._fuzzy_filter_fonts(fonts, search_query)

        return fonts

    except Exception as e:
        logger.error(f"Error getting all fonts: {e}")
        return []

def _fuzzy_filter_fonts(self, fonts: List[FontMetadata], query: str) -> List[FontMetadata]:
    """Filter fonts using fuzzy matching."""
    query_lower = query.lower()
    matches = []

    for font in fonts:
        # Check if query matches name or family (case-insensitive)
        if (query_lower in font.name.lower() or
            query_lower in font.family.lower()):
            matches.append(font)

    return matches
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] `initialize()` completes without errors
- [ ] `cache_fonts()` stores fonts in database
- [ ] `get_all_fonts()` retrieves cached fonts
- [ ] Filtering by source works (bundled vs system)
- [ ] Search query filters correctly
- [ ] Memory cache populated after initialize()
- [ ] Database fallback works when cache empty
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 7: Implement FontService database caching

- Implement cache_fonts() for SQLite persistence
- Implement initialize() for startup
- Implement get_all_fonts() with filtering
- Add fuzzy search matching for fonts
- Add memory cache with database fallback
- Handle database transactions properly"
```

---

### VUW 8: Implement Font Refresh Functionality

**Objective:** Implement refresh_system_fonts() to re-detect and cache fonts
**Time Estimate:** 35 minutes
**Files:**
- `backend/src/services/font_service.py` (MODIFY)

#### Step-by-Step Instructions

1. **Implement refresh_system_fonts() method**

Replace stub:
```python
async def refresh_system_fonts(self) -> List[FontMetadata]:
    """
    Force refresh of system fonts (clear cache and re-detect).

    Returns:
        List of newly detected FontMetadata objects
    """
    try:
        logger.info("Starting system font refresh...")

        # Clear memory cache
        self._font_cache = None

        # Clear database cache
        if self.db_session:
            try:
                stmt = delete(SystemFont).where(SystemFont.source == "system")
                await self.db_session.execute(stmt)
                await self.db_session.commit()
                logger.info("Cleared system fonts from database cache")
            except Exception as e:
                await self.db_session.rollback()
                logger.warning(f"Failed to clear database cache: {e}")

        # Re-detect system fonts
        detected = await self.detect_system_fonts()
        logger.info(f"Re-detected {len(detected)} system fonts")

        # Re-cache in database
        if self.db_session:
            await self.cache_fonts(detected)

        # Re-populate memory cache
        bundled = await self.get_bundled_fonts()
        self._font_cache = bundled + detected

        logger.info("System font refresh complete")
        return detected

    except Exception as e:
        logger.error(f"Error refreshing system fonts: {e}")
        raise
```

2. **Add utility method to check if font file has changed**

```python
async def _has_font_changed(self, font_path: Path) -> bool:
    """Check if font file has changed (hash mismatch)."""
    try:
        current_hash = self._calculate_file_hash(font_path)

        if self.db_session:
            stmt = select(SystemFont).where(SystemFont.file_path == str(font_path.absolute()))
            result = await self.db_session.execute(stmt)
            db_font = result.scalar_one_or_none()

            if db_font and db_font.file_hash != current_hash:
                logger.debug(f"Font file changed: {font_path.name}")
                return True

        return False
    except Exception:
        return False
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] `refresh_system_fonts()` clears memory cache
- [ ] Database system fonts deleted before refresh
- [ ] System fonts re-detected
- [ ] New fonts cached in database
- [ ] Memory cache repopulated with fresh data
- [ ] Returns list of detected fonts
- [ ] Logging shows refresh progress
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 8: Implement font refresh functionality

- Implement refresh_system_fonts() for cache clearing
- Clear memory and database caches
- Re-detect and re-cache system fonts
- Add _has_font_changed() utility for change detection
- Comprehensive logging for troubleshooting"
```

---

### VUW 9: Update Frontend FontSelector Component

**Objective:** Enhance frontend font selector with system fonts and search
**Time Estimate:** 50 minutes
**Files:**
- `frontend/src/components/FontSelector.tsx` (NEW)
- `frontend/src/app/settings/page.tsx` (MODIFY)

#### Step-by-Step Instructions

1. **Create new component: frontend/src/components/FontSelector.tsx**

```typescript
// start frontend/src/components/FontSelector.tsx

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { RefreshCw } from 'lucide-react';

interface FontOption {
  id: string;
  name: string;
  family: string;
  style?: string;
  weight?: number;
  source: 'bundled' | 'system';
}

interface FontSelectorProps {
  value?: string;
  onChange?: (fontName: string) => void;
  disabled?: boolean;
  showSearch?: boolean;
  showRefresh?: boolean;
}

export function FontSelector({
  value,
  onChange,
  disabled = false,
  showSearch = true,
  showRefresh = true,
}: FontSelectorProps) {
  const [fonts, setFonts] = useState<FontOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Fetch fonts on mount
  useEffect(() => {
    loadFonts();
  }, []);

  const loadFonts = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/fonts`);
      if (!response.ok) {
        throw new Error('Failed to load fonts');
      }

      const data = await response.json();
      setFonts(data.fonts || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Failed to load fonts:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      const response = await fetch(`${apiUrl}/fonts/refresh`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to refresh fonts');
      }

      await loadFonts();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Failed to refresh fonts:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Filter fonts based on search query
  const filteredFonts = useMemo(() => {
    if (!searchQuery) return fonts;

    return fonts.filter((font) =>
      font.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      font.family.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [fonts, searchQuery]);

  // Separate bundled and system fonts
  const bundledFonts = filteredFonts.filter((f) => f.source === 'bundled');
  const systemFonts = filteredFonts.filter((f) => f.source === 'system');

  if (error) {
    return (
      <div className="w-full p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
        {error}
        <button
          onClick={loadFonts}
          className="ml-2 underline font-medium hover:no-underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="w-full space-y-3">
      {/* Search Bar */}
      {showSearch && (
        <div className="flex gap-2">
          <Input
            placeholder="Search fonts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            disabled={disabled || loading}
            className="flex-1"
          />
          {showRefresh && (
            <Button
              onClick={handleRefresh}
              disabled={disabled || isRefreshing}
              size="sm"
              variant="outline"
              title="Refresh system fonts"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          )}
        </div>
      )}

      {/* Font Selector */}
      <Select value={value} onValueChange={onChange} disabled={disabled || loading}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder={loading ? 'Loading fonts...' : 'Select a font'} />
        </SelectTrigger>
        <SelectContent>
          {/* Bundled Fonts Group */}
          {bundledFonts.length > 0 && (
            <SelectGroup>
              <SelectLabel className="font-semibold">Bundled Fonts</SelectLabel>
              {bundledFonts.map((font) => (
                <SelectItem key={font.id} value={font.name}>
                  <span>{font.name}</span>
                  {font.style && <span className="text-gray-500"> ({font.style})</span>}
                </SelectItem>
              ))}
            </SelectGroup>
          )}

          {/* System Fonts Group */}
          {systemFonts.length > 0 && (
            <SelectGroup>
              <SelectLabel className="font-semibold">System Fonts</SelectLabel>
              {systemFonts.map((font) => (
                <SelectItem key={font.id} value={font.name}>
                  <span>{font.name}</span>
                  {font.style && <span className="text-gray-500"> ({font.style})</span>}
                </SelectItem>
              ))}
            </SelectGroup>
          )}

          {/* No Results */}
          {filteredFonts.length === 0 && (
            <div className="py-6 text-center text-sm text-gray-500">
              No fonts found {searchQuery && `matching "${searchQuery}"`}
            </div>
          )}
        </SelectContent>
      </Select>

      {/* Info Text */}
      {!loading && (
        <p className="text-xs text-gray-500">
          {bundledFonts.length} bundled • {systemFonts.length} system fonts available
        </p>
      )}
    </div>
  );
}

// end frontend/src/components/FontSelector.tsx
```

2. **Update frontend/src/app/settings/page.tsx**

Replace the old font loading code and font selector with:

```typescript
import { FontSelector } from '@/components/FontSelector';

// In the settings page component, replace the font selection section:

<div className="space-y-2">
  <label htmlFor="font-selector" className="block text-sm font-medium">
    Font Family
  </label>
  <FontSelector
    value={defaultFontFamily}
    onChange={(fontName) => setDefaultFontFamily(fontName)}
    showSearch={true}
    showRefresh={true}
  />
  <p className="text-xs text-gray-500">
    Select from bundled or system-installed fonts
  </p>
</div>
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] New component created: `frontend/src/components/FontSelector.tsx`
- [ ] Component exports properly
- [ ] TypeScript types correct (FontOption, FontSelectorProps)
- [ ] Search functionality filters fonts
- [ ] Refresh button calls /fonts/refresh endpoint
- [ ] Fonts separated into bundled and system groups
- [ ] Component renders in settings page
- [ ] No console errors
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 9: Update frontend FontSelector component

- Create new FontSelector.tsx component
- Add search functionality
- Add refresh button for system fonts
- Organize fonts by source (bundled vs system)
- Integrate into settings page
- Add loading and error states"
```

---

### VUW 10: Integration Testing and Bug Fixes

**Objective:** Test end-to-end integration and fix any issues
**Time Estimate:** 60 minutes
**Files:**
- All previous files (testing may require minor adjustments)

#### Step-by-Step Instructions

1. **Start backend services**

```bash
cd /Users/cspenn/Documents/github/supoclip

# If using Docker
docker-compose up -d postgres redis

# Wait for services to start (30 seconds)
sleep 30

# Run migrations
cd backend
uv venv .venv
source .venv/bin/activate
uv sync
```

2. **Run backend tests**

```bash
# From backend directory
pytest tests/ -v --tb=short 2>&1 | tee test_results.log

# Check for failures
grep -i "failed\|error" test_results.log || echo "All tests passed!"
```

3. **Start backend development server**

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

4. **Test API endpoints manually**

```bash
# In another terminal
# Test 1: Get fonts list
curl -s http://localhost:8000/fonts | python -m json.tool

# Test 2: Search fonts
curl -s "http://localhost:8000/fonts/search?q=arial" | python -m json.tool

# Test 3: Refresh fonts
curl -s -X POST http://localhost:8000/fonts/refresh | python -m json.tool

# Test 4: Get specific font
curl -s "http://localhost:8000/fonts/TikTokSans-Regular" -o /tmp/test.ttf
file /tmp/test.ttf  # Should show: TrueType Font data
```

5. **Start frontend and test UI**

```bash
cd /Users/cspenn/Documents/github/supoclip/frontend
npm install  # If needed
npm run dev
```

Visit http://localhost:3000/settings and test:
- Font selector loads fonts
- Search filters fonts
- Refresh button works
- Bundled vs system fonts visible

6. **Check for issues and log**

```bash
# Check backend logs
docker-compose logs backend | tail -50

# Run Python quality checks
cd backend
python -m pytest tests/ -v 2>&1 | tee test_results.log
./checkpython.sh
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] Backend API responds to all 4 font endpoints
- [ ] Fonts list includes bundled fonts
- [ ] Search endpoint works with query parameter
- [ ] Refresh endpoint detects system fonts
- [ ] Font files can be served and downloaded
- [ ] Frontend FontSelector component renders
- [ ] Search filter works in component
- [ ] Refresh button calls API successfully
- [ ] No console errors in browser
- [ ] No unhandled exceptions in backend logs
- [ ] Self-attestation: Confirm above checks passed

#### Known Issues and Fixes

**Issue: No system fonts detected**
- Expected on some systems (e.g., CI/container environments)
- Bundled fonts should still be available
- This is not an error condition

**Issue: Font file serving returns 404**
- Check file_path in database
- Verify path is absolute and readable
- Restart backend to refresh cache

**Issue: Frontend search doesn't work**
- Clear browser cache (Ctrl+Shift+Delete)
- Check browser console for fetch errors
- Verify NEXT_PUBLIC_API_URL is set

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 10: Integration testing and bug fixes

- Test end-to-end font detection flow
- Verify all API endpoints work
- Test frontend FontSelector component
- Manual testing of search and refresh
- Document known issues and limitations"
```

---

### VUW 11: Documentation and Code Comments

**Objective:** Add comprehensive documentation and code comments
**Time Estimate:** 40 minutes
**Files:**
- All Python files with docstrings
- All TypeScript files with comments
- New file: `docs/fonts.md`

#### Step-by-Step Instructions

1. **Create fonts documentation: docs/fonts.md**

```markdown
# Font System Documentation

## Overview

The SupoClip font system provides users with access to both bundled fonts and system-installed fonts for clip generation.

## Features

- **Bundled Fonts**: Pre-included high-quality fonts (TikTokSans-Regular, The Bold Font)
- **System Font Detection**: Automatically detect fonts installed on the system
- **Font Validation**: Ensure fonts are compatible with MoviePy/ImageMagick
- **Fuzzy Search**: Search fonts by name or family
- **Refresh Capability**: Re-detect system fonts on demand
- **Database Caching**: Cache fonts for fast access and performance

## Architecture

### Backend (FontService)

Located in `backend/src/services/font_service.py`

**Key Methods:**
- `initialize()` - Initialize on startup
- `detect_system_fonts()` - Find system fonts using matplotlib
- `validate_font()` - Check compatibility with fonttools
- `extract_font_metadata()` - Get font details
- `get_all_fonts()` - Retrieve cached fonts with filtering
- `refresh_system_fonts()` - Force re-detection

**Database Model:**
- `SystemFont` in `backend/src/models.py`
- Stores font metadata and cache

### API Routes

Located in `backend/src/api/routes/fonts.py`

**Endpoints:**
- `GET /fonts` - List all available fonts
- `GET /fonts/search?q=term` - Search fonts (fuzzy matching)
- `POST /fonts/refresh` - Refresh system fonts
- `GET /fonts/{name}` - Serve font file

### Frontend

Located in `frontend/src/components/FontSelector.tsx`

**Features:**
- Font selector dropdown
- Search input
- Refresh button
- Organized by source (bundled vs system)

## Usage

### For Users

1. Navigate to Settings page
2. Find the Font Family selector
3. Type to search fonts
4. Select desired font
5. Use Refresh button to find newly installed system fonts

### For Developers

**To use FontSelector component:**

```typescript
import { FontSelector } from '@/components/FontSelector';

<FontSelector
  value={selectedFont}
  onChange={handleFontChange}
  showSearch={true}
  showRefresh={true}
/>
```

**To call font APIs:**

```bash
# List fonts
curl http://localhost:8000/fonts

# Search fonts
curl "http://localhost:8000/fonts/search?q=arial"

# Refresh
curl -X POST http://localhost:8000/fonts/refresh
```

## Performance Considerations

- Fonts cached in SQLite for fast access
- Memory cache populated on startup
- File hash used to detect changes
- Fuzzy search uses simple string matching (scalable to 1000+ fonts)

## Platform Support

- **macOS**: Uses matplotlib.font_manager for system fonts
- **Linux**: Same as macOS (tested on Ubuntu)
- **Windows**: Same as above (uses registry via matplotlib)

## Known Limitations

1. OTF fonts supported but may have rendering differences
2. Font detection is one-time on startup (use refresh button to update)
3. Very large font collections (1000+) may impact search performance
4. Font metadata extraction depends on proper font tables

## Troubleshooting

**No system fonts showing?**
- Normal behavior on fresh systems or containers
- Click refresh button to force re-detection
- Bundled fonts are always available

**Font not displaying correctly?**
- Verify font is valid (validation checks this)
- Ensure MoviePy is installed
- Check backend logs for rendering errors

**Search not working?**
- Clear browser cache
- Refresh the page
- Check browser console for API errors

## Future Enhancements

- Font preview images
- Font categories (serif, sans-serif, monospace)
- Font permission system
- Custom font upload for premium users
- Font style/weight selection in UI
```

2. **Add docstring improvements**

All main functions already have docstrings. Verify they're comprehensive by checking:

```python
# In font_service.py, verify all methods have:
# - Description
# - Args with types
# - Returns with types
# - Raises section (if applicable)
```

3. **Add TypeScript comments**

Add comments to FontSelector component explaining complex logic:

```typescript
// Separate bundled and system fonts for clear organization
const bundledFonts = filteredFonts.filter((f) => f.source === 'bundled');
const systemFonts = filteredFonts.filter((f) => f.source === 'system');
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] docs/fonts.md created and comprehensive
- [ ] All Python functions have docstrings
- [ ] All TypeScript functions have JSDoc comments
- [ ] Code comments explain complex logic
- [ ] No TODOs left in production code
- [ ] Examples provided in documentation
- [ ] Troubleshooting section covers common issues
- [ ] Self-attestation: Confirm above checks passed

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 11: Documentation and code comments

- Create comprehensive docs/fonts.md
- Add complete docstrings to all methods
- Add TypeScript JSDoc comments
- Include usage examples
- Add troubleshooting guide"
```

---

### VUW 12: Performance Verification and Final Testing

**Objective:** Verify performance, run final tests, ensure no regressions
**Time Estimate:** 50 minutes
**Files:**
- All files (verification only, no changes)

#### Step-by-Step Instructions

1. **Run comprehensive test suite**

```bash
cd /Users/cspenn/Documents/github/supoclip

# Run all tests with coverage
pytest backend/tests/ -v --cov=src --cov-report=term-missing 2>&1 | tee coverage.log

# Should show:
# - All tests passing
# - Coverage > 70%
# - No errors or warnings
```

2. **Run code quality checks**

```bash
cd backend

# Run full quality check suite
./checkpython.sh 2>&1 | tee quality_check.log

# Expected output:
# - 0 errors from ruff
# - 0 errors from mypy
# - 0 errors from bandit
# - X passed in pytest (X > 0)
```

3. **Performance verification**

```bash
# Test font loading performance
cd /Users/cspenn/Documents/github/supoclip/backend

python -c "
import asyncio
import time
from src.services.font_service import FontService

async def test_performance():
    service = FontService()

    # Test initialization time
    start = time.time()
    await service.initialize()
    init_time = time.time() - start

    # Test get_all_fonts performance
    start = time.time()
    fonts = await service.get_all_fonts()
    get_time = time.time() - start

    print(f'Initialization: {init_time:.2f}s')
    print(f'Get all fonts: {get_time:.2f}s')
    print(f'Total fonts: {len(fonts)}')

    # Should be < 5 seconds
    assert init_time < 5, f'Initialization too slow: {init_time}s'
    assert get_time < 0.5, f'Get fonts too slow: {get_time}s'

asyncio.run(test_performance())
"
```

4. **Frontend performance check**

```bash
cd /Users/cspenn/Documents/github/supoclip/frontend

# Build frontend
npm run build 2>&1 | tee build.log

# Check for warnings
grep -i "warning" build.log | grep -v "node_modules" || echo "No warnings!"
```

5. **Regression testing - Verify existing features work**

```bash
# Test that existing font endpoint still works
curl -s http://localhost:8000/fonts | jq '.' > /tmp/fonts_new.json

# Verify bundled fonts present
grep -q "TikTokSans-Regular" /tmp/fonts_new.json && echo "Bundled fonts OK"

# Test clip generation still works (create sample clip)
curl -s -X POST http://localhost:8000/start -H "Content-Type: application/json" \
  -d '{"source": {"url": "test.com"}}' | jq '.status'
```

6. **Load test** (optional, if tools available)

```bash
# If ab (ApacheBench) installed:
ab -n 100 -c 10 http://localhost:8000/fonts

# Should handle 100 requests without issues
```

7. **Database consistency check**

```bash
# Verify database tables exist and have data
sqlite3 supoclip.db << EOF
SELECT COUNT(*) as font_count FROM system_fonts;
SELECT COUNT(*) as bundled_count FROM system_fonts WHERE source = 'bundled';
SELECT COUNT(*) as system_count FROM system_fonts WHERE source = 'system';
SELECT name FROM system_fonts LIMIT 5;
EOF
```

#### Verification Checklist

- [ ] Run `./checkpython.sh` - Must report **zero errors** with **100% passing tests**
- [ ] All tests pass (pytest output shows 100% passing)
- [ ] Code quality: 0 ruff errors, 0 mypy errors, 0 bandit warnings
- [ ] Test coverage > 70%
- [ ] Font initialization < 5 seconds
- [ ] Font querying < 0.5 seconds
- [ ] Frontend builds without warnings
- [ ] Existing font endpoints still work
- [ ] Clip generation unaffected by changes
- [ ] Database tables created correctly
- [ ] No regressions in existing features
- [ ] No console errors (backend or frontend)
- [ ] Self-attestation: Confirm above checks passed

#### Performance Benchmarks

Expected performance metrics:

| Operation | Target | Typical |
|-----------|--------|---------|
| Font initialization | < 5s | 0.5-2s |
| Get all fonts | < 0.5s | 0.01-0.1s |
| Search fonts | < 0.1s | 0.01s |
| Refresh fonts | < 5s | 1-3s |
| Serve font file | < 1s | 0.01-0.05s |

#### Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "VUW 12: Performance verification and final testing

- Run comprehensive test suite with coverage
- Verify code quality (ruff, mypy, bandit)
- Performance benchmarks (init, query, search)
- Regression testing of existing features
- Database consistency checks
- Load testing of API endpoints"
```

---

## Final Integration Checklist

After completing all 12 VUWs, verify:

### Backend
- [ ] `./checkpython.sh` passes with zero errors
- [ ] All 4 API endpoints working
- [ ] FontService fully implemented
- [ ] Database model created
- [ ] Cache mechanism working

### Frontend
- [ ] FontSelector component renders
- [ ] Search functionality working
- [ ] Refresh button calls API
- [ ] Settings page integrates component
- [ ] No TypeScript errors

### Database
- [ ] system_fonts table created
- [ ] Indexes created for performance
- [ ] Prisma schema updated
- [ ] Initial data seeded (bundled fonts)

### Documentation
- [ ] docs/fonts.md comprehensive
- [ ] Code comments complete
- [ ] All functions documented
- [ ] Examples provided

### Testing
- [ ] All existing tests pass
- [ ] No regressions
- [ ] Performance acceptable
- [ ] Load testing passed

---

## Rollback Procedure

If critical issues occur and rollback is needed:

```bash
# 1. Identify the problematic VUW
# 2. Revert to previous checkpoint
git reset --hard <previous_checkpoint_hash>

# 3. Or selectively revert files:
git checkout <hash> -- backend/src/services/font_service.py

# 4. Restart services
docker-compose restart backend

# 5. Verify working state
curl http://localhost:8000/fonts
./checkpython.sh
```

---

## Success Criteria

Phase 1 is complete when:

1. All 12 VUWs have passing verification checklists
2. `./checkpython.sh` reports zero errors with 100% passing tests
3. System fonts appear in font selector
4. Search functionality works
5. Refresh button detects new fonts
6. No regressions in existing features
7. Documentation complete
8. Performance benchmarks met

---

## Next Steps (Phase 2)

After Phase 1 completion, Phase 2 can implement:

- Font preview images
- Font categories (serif, sans-serif, monospace)
- Font style/weight selection in UI
- Custom font upload feature
- Advanced search with filters
- Font permission system

---

## Appendix A: Environment Setup

### macOS

```bash
# Install dependencies
brew install ffmpeg python@3.11

# Install uv
pip install uv

# Install Node.js (if needed)
brew install node@18
```

### Linux (Ubuntu)

```bash
# Install dependencies
sudo apt-get install ffmpeg python3.11 python3.11-venv

# Install uv
pip3 install uv

# Install Node.js (if needed)
sudo apt-get install nodejs npm
```

### Windows

```bash
# Install ffmpeg (via scoop or chocolatey)
scoop install ffmpeg
# or
choco install ffmpeg

# Install Python 3.11+ from python.org
# Install uv
pip install uv

# Install Node.js from nodejs.org
```

---

## Appendix B: Troubleshooting VUWs

### Issue: `matplotlib` not found

```bash
cd backend
uv sync  # Re-sync dependencies
```

### Issue: Font validation always fails

```bash
# Check fonttools version
python -c "from fontTools.ttLib import TTFont; print('OK')"

# Manually test a font file
python -c "
from fontTools.ttLib import TTFont
font = TTFont('/path/to/font.ttf')
print(font.keys())  # Should show required tables
"
```

### Issue: Database migration fails

```bash
# Reset database
rm supoclip.db
# Restart backend to recreate tables
```

### Issue: Frontend fonts not loading

```bash
# Check API URL
echo $NEXT_PUBLIC_API_URL
# Should be set to backend URL (e.g., http://localhost:8000)

# Clear Next.js cache
rm -rf .next
npm run build
```

---

## Appendix C: File Checklist

**Files to be created:**
- [ ] `backend/src/services/font_service.py` (NEW)
- [ ] `backend/src/api/routes/fonts.py` (NEW)
- [ ] `frontend/src/components/FontSelector.tsx` (NEW)
- [ ] `docs/fonts.md` (NEW)

**Files to be modified:**
- [ ] `backend/pyproject.toml` (dependencies)
- [ ] `backend/src/models.py` (SystemFont model)
- [ ] `backend/src/main.py` (initialize FontService, include router)
- [ ] `init.sql` (system_fonts table)
- [ ] `frontend/prisma/schema.prisma` (SystemFont model)
- [ ] `frontend/src/app/settings/page.tsx` (use FontSelector component)

**No changes needed:**
- All other backend files
- All other frontend files
- All database migration files
- Configuration files

---

**Document Version:** 1.0
**Last Updated:** November 15, 2025
**Status:** Ready for Implementation
**Estimated Total Time:** 8-10 hours
**Recommended Team:** 1-2 developers
