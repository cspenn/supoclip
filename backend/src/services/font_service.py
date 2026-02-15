# start backend/src/services/font_service.py

"""Font detection and management service."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from datetime import datetime
import hashlib
import uuid

import matplotlib.font_manager as fm
from fontTools.ttLib import TTFont  # type: ignore
from fontTools.ttLib.ttFont import TTLibError  # type: ignore
from sqlalchemy import select, func as db_func, or_
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


@dataclass
class FontMetadata:
    """Metadata for a font file."""

    id: str | None = None
    name: str = ""
    family: str = ""
    style: str | None = None
    weight: int | None = None
    file_path: str | None = None
    file_hash: str | None = None
    is_valid: bool = True
    detection_timestamp: str | None = None
    metadata_json: dict[str, Any] | None = None
    source: str = "bundled"  # 'bundled' or 'system'


class FontNameExtractor:
    """Extract specific names from font files."""

    @staticmethod
    def extract_from_name_table(name_table, name_id: int) -> str | None:
        """Extract specific name from font name table by nameID.

        Args:
            name_table: Font name table from fontTools
            name_id: ID of name to extract (1=family, 2=style, 4=full)

        Returns:
            Extracted name string or None if not found
        """
        for record in name_table.names:
            if record.nameID == name_id:
                try:
                    return record.toUnicode()
                except Exception:
                    return None
        return None

    @staticmethod
    def extract_all_names(name_table) -> dict[str, str | None]:
        """Extract family, style, and full name from font.

        Args:
            name_table: Font name table from fontTools

        Returns:
            Dictionary with family, style, and full_name keys
        """
        return {
            "family": FontNameExtractor.extract_from_name_table(name_table, 1),
            "style": FontNameExtractor.extract_from_name_table(name_table, 2),
            "full_name": FontNameExtractor.extract_from_name_table(name_table, 4),
        }


class FontWeightExtractor:
    """Extract weight information from font files."""

    @staticmethod
    def extract_weight(font: TTFont) -> int | None:
        """Extract font weight from OS/2 table if available.

        Args:
            font: TTFont object from fontTools

        Returns:
            Weight class value or None if not available
        """
        if "OS/2" in font:
            return font["OS/2"].usWeightClass
        return None


class FontService:
    """Service for detecting, validating, and managing fonts."""

    def __init__(self, db_session=None, temp_dir: Path = Path("/tmp")):
        """
        Initialize FontService.

        Args:
            db_session: Optional database session for caching
            temp_dir: Directory for temporary files
        """
        self.db_session = db_session
        self.temp_dir = temp_dir
        self.bundled_fonts_dir = Path(__file__).parent.parent.parent / "fonts"

        logger.info("🎨 FontService initialized")

    async def get_bundled_fonts(self) -> list[FontMetadata]:
        """
        Get all bundled fonts from backend/fonts directory.

        Returns:
            List of FontMetadata for bundled fonts
        """
        logger.info("📦 Getting bundled fonts...")

        if not self.bundled_fonts_dir.exists():
            logger.warning(
                f"⚠️ Bundled fonts directory not found: {self.bundled_fonts_dir}"
            )
            return []

        bundled_fonts = []

        # Find all .ttf and .otf files
        font_files = list(self.bundled_fonts_dir.glob("*.ttf")) + list(
            self.bundled_fonts_dir.glob("*.otf")
        )

        logger.info(
            f"🔍 Found {len(font_files)} font files in {self.bundled_fonts_dir}"
        )

        for font_path in font_files:
            try:
                # Validate font
                if not await self.validate_font(font_path):
                    logger.warning(f"⚠️ Invalid font file: {font_path}")
                    continue

                # Extract metadata
                metadata = await self.extract_font_metadata(font_path)
                if metadata:
                    metadata.source = "bundled"
                    bundled_fonts.append(metadata)
                    logger.debug(f"✅ Loaded bundled font: {metadata.name}")

            except Exception as e:
                logger.error(f"❌ Failed to load font {font_path}: {e}")

        logger.info(f"✅ Loaded {len(bundled_fonts)} bundled fonts")
        return bundled_fonts

    async def detect_system_fonts(self) -> list[FontMetadata]:
        """
        Detect system-installed fonts using matplotlib.font_manager.

        Returns:
            List of FontMetadata for system fonts
        """
        logger.info("🔍 Detecting system fonts...")

        system_fonts = []

        try:
            # Use matplotlib's font_manager to find all system fonts
            font_list = fm.findSystemFonts(fontpaths=None, fontext="ttf")

            logger.info(f"📊 Found {len(font_list)} TrueType fonts on system")

            for font_path_str in font_list:
                try:
                    font_path = Path(font_path_str)

                    # Validate font exists and is readable
                    if not font_path.exists() or not font_path.is_file():
                        continue

                    # Validate font
                    if not await self.validate_font(font_path):
                        continue

                    # Extract metadata
                    metadata = await self.extract_font_metadata(font_path)
                    if metadata:
                        metadata.source = "system"
                        system_fonts.append(metadata)

                except Exception as e:
                    logger.debug(
                        f"⚠️ Failed to process system font {font_path_str}: {e}"
                    )

            logger.info(f"✅ Detected {len(system_fonts)} valid system fonts")

        except Exception as e:
            logger.error(f"❌ System font detection failed: {e}")

        return system_fonts

    async def extract_font_metadata(self, font_path: Path) -> FontMetadata | None:
        """
        Extract metadata from a font file using fontTools.

        Args:
            font_path: Path to font file

        Returns:
            FontMetadata object or None if extraction fails
        """
        try:
            # Open font file with fontTools
            font = TTFont(str(font_path))

            # Extract all names using helper class
            names = FontNameExtractor.extract_all_names(font["name"])

            # Use filename without extension as name if full_name not available
            name = names["full_name"] or font_path.stem

            # Extract weight using helper class
            weight = FontWeightExtractor.extract_weight(font)

            # Compute file hash
            file_hash = await self.compute_file_hash(font_path)

            # Create metadata object
            metadata = FontMetadata(
                id=str(uuid.uuid4()),
                name=name,
                family=names["family"] or name,
                style=names["style"],
                weight=weight,
                file_path=str(font_path),
                file_hash=file_hash,
                is_valid=True,
                detection_timestamp=datetime.now().isoformat(),
                metadata_json={
                    "file_size": font_path.stat().st_size,
                    "file_extension": font_path.suffix,
                },
                source="bundled",  # Will be overridden by caller
            )

            font.close()
            return metadata

        except Exception as e:
            logger.debug(f"⚠️ Failed to extract metadata from {font_path}: {e}")
            return None

    async def validate_font(self, font_path: Path) -> bool:
        """
        Validate that a font file is readable and usable by MoviePy/ImageMagick.

        Uses fonttools to validate font structure and required tables.
        Supports both TTF and OTF formats.

        Args:
            font_path: Path to font file

        Returns:
            True if font is valid and usable, False otherwise
        """
        try:
            # Check file exists and is readable
            if not font_path.exists() or not font_path.is_file():
                logger.debug(f"⚠️ Font file not found or not accessible: {font_path}")
                return False

            # Check file is readable
            if not font_path.stat().st_size > 0:
                logger.debug(f"⚠️ Font file is empty: {font_path}")
                return False

            # Try to load with fontTools TTFont
            try:
                font = TTFont(str(font_path))
            except (TTLibError, Exception) as e:
                logger.debug(f"⚠️ Failed to load font {font_path}: {e}")
                return False

            # Check for required tables (minimal set for valid TTF/OTF)
            # head: font header
            # hhea: horizontal header
            # maxp: maximum profile
            # hmtx: horizontal metrics
            # cmap: character to glyph mapping (critical for text rendering)
            required_tables = ["head", "hhea", "maxp", "hmtx", "cmap"]

            has_all_required = True
            for table in required_tables:
                if table not in font:
                    logger.debug(
                        f"⚠️ Font missing required table '{table}': {font_path}"
                    )
                    has_all_required = False
                    break

            # Close font to free resources
            font.close()

            if has_all_required:
                logger.debug(f"✅ Font validated successfully: {font_path.name}")

            return has_all_required

        except Exception as e:
            logger.debug(f"⚠️ Font validation exception for {font_path}: {e}")
            return False

    async def compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of a font file.

        Args:
            file_path: Path to font file

        Returns:
            Hex-encoded SHA256 hash
        """
        try:
            sha256_hash = hashlib.sha256()

            with file_path.open("rb") as f:
                # Read file in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            return sha256_hash.hexdigest()

        except Exception as e:
            logger.warning(f"⚠️ Failed to compute hash for {file_path}: {e}")
            return ""

    async def cache_fonts(self, fonts: list[FontMetadata]) -> None:
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
            from ..models import SystemFont

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
                            source=font.source,
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
            logger.info("✅ Successfully cached fonts")

        except Exception as e:
            logger.error(f"❌ Font caching failed: {e}")
            if self.db_session:
                await self.db_session.rollback()

    async def get_all_fonts(
        self, search_query: str | None = None, source_filter: str | None = None
    ) -> list[FontMetadata]:
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
            from ..models import SystemFont

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
                        db_func.lower(SystemFont.name).like(search_term),
                        db_func.lower(SystemFont.family).like(search_term),
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
                    source=f.source,
                )
                for f in db_fonts
            ]

            logger.debug(f"📋 Retrieved {len(fonts)} fonts from database")
            return fonts

        except Exception as e:
            logger.error(f"❌ Failed to retrieve fonts: {e}")
            return []

    async def get_font_by_name(self, font_name: str) -> FontMetadata | None:
        """
        Get a specific font by name.

        Args:
            font_name: Name of the font

        Returns:
            FontMetadata object or None if not found
        """
        logger.debug(f"🔎 Looking up font: {font_name}")

        # Get all fonts and search for exact or case-insensitive match
        all_fonts = await self.get_all_fonts()
        font_name_lower = font_name.lower()

        for font in all_fonts:
            # Exact match on name
            if font.name.lower() == font_name_lower:
                return font
            # Match on family name
            if font.family and font.family.lower() == font_name_lower:
                return font

        logger.debug(f"⚠️ Font not found: {font_name}")
        return None

    async def refresh_system_fonts(self) -> int:
        """
        Force refresh of system fonts.

        Returns:
            Number of fonts detected
        """
        logger.info("🔄 Refreshing system fonts...")

        try:
            # Detect all system fonts
            system_fonts = await self.detect_system_fonts()

            # Cache them to database
            await self.cache_fonts(system_fonts)

            logger.info(f"✅ Refreshed {len(system_fonts)} system fonts")
            return len(system_fonts)
        except Exception as e:
            logger.error(f"❌ Failed to refresh system fonts: {e}")
            return 0


# end backend/src/services/font_service.py
