# start backend/src/api/routes/fonts.py

"""Font management API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Any
import logging

from ...services.font_service import FontService
from ...dependencies import get_font_service

router = APIRouter(prefix="/fonts", tags=["fonts"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_fonts(
    source: str = Query(None, description="Filter by source: 'bundled' or 'system'"),
    service: FontService = Depends(get_font_service),
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
    service: FontService = Depends(get_font_service),
) -> List[Dict[str, Any]]:
    """
    Search for fonts by name or family.

    Query Parameters:
    - q: Search term (required)

    Returns:
        List of matching font metadata objects
    """
    if not q or len(q) < 2:
        raise HTTPException(
            status_code=400, detail="Search query must be at least 2 characters"
        )

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
    service: FontService = Depends(get_font_service),
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
    font_name: str, service: FontService = Depends(get_font_service)
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
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to serve font {font_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve font file")


# end backend/src/api/routes/fonts.py
