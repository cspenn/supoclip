"""
Media API routes (fonts, transitions, uploads).
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
import logging
import uuid
import aiofiles

from ...config import Config

logger = logging.getLogger(__name__)
config = Config()
router = APIRouter(tags=["media"])


@router.get("/fonts")
async def get_available_fonts():
    """Get list of available fonts."""
    try:
        fonts_dir = Path(__file__).parent.parent.parent.parent / "fonts"
        if not fonts_dir.exists():
            return {"fonts": [], "message": "Fonts directory not found"}

        font_files = []
        for font_file in fonts_dir.glob("*.ttf"):
            font_name = font_file.stem
            font_files.append({
                "name": font_name,
                "display_name": font_name.replace("-", " ").replace("_", " ").title(),
                "file_path": str(font_file)
            })

        logger.info(f"Found {len(font_files)} available fonts")
        return {"fonts": font_files}

    except Exception as e:
        logger.error(f"Error retrieving fonts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving fonts: {str(e)}")


@router.get("/fonts/{font_name}")
async def get_font_file(font_name: str):
    """Serve a specific font file."""
    try:
        fonts_dir = Path(__file__).parent.parent.parent.parent / "fonts"
        font_path = fonts_dir / f"{font_name}.ttf"

        if not font_path.exists():
            raise HTTPException(status_code=404, detail="Font not found")

        return FileResponse(
            path=str(font_path),
            media_type="font/ttf",
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving font {font_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving font: {str(e)}")


@router.get("/transitions")
async def get_available_transitions():
    """Get list of available transition effects."""
    try:
        from ...video_utils import get_available_transitions
        transitions = get_available_transitions()

        transition_info = []
        for transition_path in transitions:
            transition_file = Path(transition_path)
            transition_info.append({
                "name": transition_file.stem,
                "display_name": transition_file.stem.replace("_", " ").replace("-", " ").title(),
                "file_path": transition_path
            })

        logger.info(f"Found {len(transition_info)} available transitions")
        return {"transitions": transition_info}

    except Exception as e:
        logger.error(f"Error retrieving transitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving transitions: {str(e)}")


@router.post("/upload")
async def upload_video(request: Request):
    """Upload a video to the server."""
    try:
        # Get the form data
        form_data = await request.form()
        video_file = form_data.get("video")

        if not video_file or not hasattr(video_file, 'filename'):
            raise HTTPException(status_code=400, detail="No video file provided")

        # Create uploads directory
        uploads_dir = Path(config.temp_dir) / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_extension = Path(video_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        video_path = uploads_dir / unique_filename

        # Save the uploaded file
        async with aiofiles.open(video_path, 'wb') as f:
            content = await video_file.read()
            await f.write(content)

        logger.info(f"✅ Video uploaded successfully to: {video_path}")

        return {
            "message": "Video uploaded successfully",
            "video_path": str(video_path)
        }
    except Exception as e:
        logger.error(f"❌ Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading video: {str(e)}")
