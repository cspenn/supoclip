from .config import Config
from .logging_config import setup_logging, cleanup_old_logs
from pathlib import Path
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import get_db
from .api.routes.tasks import router as tasks_router
from .api.routes.fonts import router as fonts_router
from .dependencies import get_current_user
from .utils.font_options import parse_font_options
from .services.user_preferences_service import UserPreferencesService
from .services.video_service_async import AsyncVideoProcessingService
from .lifecycle import lifespan

# Configure configuration and logging
config = Config()
setup_logging(config.get_log_level(), config.log_dir, "backend")

# Clean up old logs on startup
cleanup_old_logs(config.log_dir, config.log_retention_days)

logger = logging.getLogger(__name__)


app = FastAPI(
    title="SupoClip API",
    description="Python-based backend for SupoClip",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(tasks_router)
app.include_router(fonts_router)

# Mount static files for serving clips
clips_dir = Path(config.temp_dir) / "clips"
clips_dir.mkdir(parents=True, exist_ok=True)
app.mount("/clips", StaticFiles(directory=str(clips_dir)), name="clips")


@app.get("/")
def read_root():
    return {
        "name": "SupoClip API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "architecture": "FastAPI + SQLite + Local MLX",
        "message": "This is the SupoClip FastAPI-based API. Visit /docs for the API documentation.",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
async def check_database_health(db: AsyncSession = Depends(get_db)):
    """Check database connectivity"""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@app.post("/start", status_code=410)
async def start_task(request: Request, user_id: str = Depends(get_current_user)):
    """
    DEPRECATED: Start a new task for authenticated users.

    This endpoint is legacy and synchronous. It has been replaced by /start-with-progress.
    """
    logger.warning(f"DEPRECATED: User {user_id} accessed legacy /start endpoint.")
    return {
        "error": "This endpoint is deprecated and no longer functional.",
        "message": "Please use /start-with-progress for asynchronous video processing.",
        "docs": "/docs",
    }


@app.post("/start-with-progress")
async def start_task_with_progress(
    request: Request,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new task and return task ID for SSE tracking (async endpoint)"""

    logger.info(f"Starting async task request for user {user_id}")

    data = await request.json()
    raw_source = data.get("source")

    # Get font customization options from request using centralized utility
    parsed_font_opts = parse_font_options(data)

    logger.info(
        f"Request data - URL: {raw_source.get('url') if raw_source else 'None'}, User ID: {user_id}"
    )

    if not raw_source or not raw_source.get("url"):
        logger.error("Source URL is missing")
        raise HTTPException(status_code=400, detail="Source URL is required")

    # Validate user_id and load preferences
    try:
        # Use UserPreferencesService to handle all preference logic
        pref_service = UserPreferencesService(db)

        # Merge preferences: request > user prefs > defaults
        request_opts = parsed_font_opts | {
            "clip_min_length": data.get("clip_min_length"),
            "clip_target_length": data.get("clip_target_length"),
            "clip_max_length": data.get("clip_max_length"),
            "custom_ai_prompt": data.get("custom_ai_prompt"),
            "output_resolution": data.get("output_resolution"),
        }

        preferences = await pref_service.merge_with_request_options(
            user_id, request_opts
        )
        logo_path_obj = pref_service.get_logo_path(preferences)
        logo_path = str(logo_path_obj) if logo_path_obj else None

        logger.info(f"User {user_id} preferences loaded and merged")

    except ValueError as e:
        logger.error(f"Error loading user preferences: {e}")
        raise HTTPException(status_code=404, detail="User not found")

    # Use async video processing service
    service = AsyncVideoProcessingService(db, config)
    task_id = await service.create_task(
        raw_source=raw_source,
        user_id=user_id,
        font_family=preferences["font_family"],
        font_size=preferences["font_size"],
        font_color=preferences["font_color"],
    )

    # Start processing in background
    asyncio.create_task(
        service.process_video_async(
            task_id=task_id,
            raw_source=raw_source,
            user_id=user_id,
            font_family=preferences["font_family"],
            font_size=preferences["font_size"],
            font_color=preferences["font_color"],
            clip_min_length=preferences["clip_min_length"],
            clip_target_length=preferences["clip_target_length"],
            clip_max_length=preferences["clip_max_length"],
            custom_ai_prompt=preferences["custom_ai_prompt"],
            logo_path=logo_path,
            logo_corner_position=preferences["logo_corner_position"],
            output_resolution=preferences["output_resolution"],
        )
    )

    return {"task_id": task_id, "message": "Task started successfully"}


@app.get("/transitions")
async def get_available_transitions():
    """Get list of available transition effects"""
    try:
        from .video_utils import get_available_transitions

        transitions = get_available_transitions()

        transition_info = []
        for transition_path in transitions:
            transition_file = Path(transition_path)
            transition_info.append(
                {
                    "name": transition_file.stem,
                    "display_name": transition_file.stem.replace("_", " ")
                    .replace("-", " ")
                    .title(),
                    "file_path": transition_path,
                }
            )

        logger.info(f"Found {len(transition_info)} available transitions")
        return {"transitions": transition_info}

    except Exception as e:
        logger.error(f"Error retrieving transitions: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving transitions: {e}"
        )


@app.get("/default-prompt")
async def get_default_ai_prompt():
    """Get the default AI system prompt used for transcript analysis"""
    try:
        from .ai import simplified_system_prompt

        logger.info("Retrieving default AI prompt")
        return {
            "prompt": simplified_system_prompt,
            "description": "Default system prompt for AI-powered clip selection",
        }

    except Exception as e:
        logger.error(f"Error retrieving default prompt: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving default prompt: {e}"
        )


# endpoint to upload a video
@app.post("/upload")
async def upload_video(request: Request):
    """Upload a video to the server"""
    try:
        import aiofiles

        # Get the form data
        form_data = await request.form()
        video_file = form_data.get("video")

        if not video_file or not hasattr(video_file, "filename"):
            raise HTTPException(status_code=400, detail="No video file provided")

        # Create uploads directory
        uploads_dir = Path(config.temp_dir) / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename to avoid conflicts
        import uuid

        if not video_file.filename:
            raise HTTPException(
                status_code=400, detail="Video file must have a filename"
            )
        file_extension = Path(video_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        video_path = uploads_dir / unique_filename

        # Save the uploaded file
        if isinstance(video_file, str):
            raise TypeError("Expected UploadFile object")
        async with aiofiles.open(video_path, "wb") as f:
            content = await video_file.read()
            await f.write(content)

        logger.info(f"Video uploaded successfully to: {video_path}")

        return {"message": "Video uploaded successfully", "video_path": str(video_path)}
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading video: {e}")


@app.post("/upload-logo")
async def upload_logo(
    request: Request,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload logo image for user branding"""
    try:
        from PIL import Image
        import aiofiles

        logger.info(f"Logo upload request from user {user_id}")

        form_data = await request.form()
        logo_file = form_data.get("logo")
        corner_position = form_data.get("corner_position", "top-right")

        if not logo_file or not hasattr(logo_file, "filename"):
            raise HTTPException(status_code=400, detail="No logo file provided")

        # Validate file type
        if not logo_file.filename:
            raise HTTPException(
                status_code=400, detail="Logo file must have a filename"
            )
        allowed_extensions = {".png", ".jpg", ".jpeg"}
        file_extension = Path(logo_file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, detail="Only PNG and JPG files allowed"
            )

        # Create logos directory
        logos_dir = Path(config.temp_dir) / "logos"
        logos_dir.mkdir(parents=True, exist_ok=True)

        # Save original file temporarily
        temp_filename = f"{user_id}_original{file_extension}"
        temp_path = logos_dir / temp_filename

        if isinstance(logo_file, str):
            raise TypeError("Expected UploadFile object")
        async with aiofiles.open(temp_path, "wb") as f:
            content = await logo_file.read()
            await f.write(content)

        # Resize logo to 60px on longest side (preserve aspect ratio)
        with Image.open(temp_path) as img:
            # Convert to RGBA for transparency support
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Calculate resize dimensions
            width, height = img.size
            longest_side = max(width, height)
            scale_factor = 60 / longest_side
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)

            # Resize
            resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save resized logo
            logo_filename = f"{user_id}_logo.png"
            logo_path = logos_dir / logo_filename
            logo_path = logo_path.resolve()  # Convert to absolute path
            resized.save(logo_path, "PNG")

        # Delete temp file
        temp_path.unlink()

        # Update user record via service
        pref_service = UserPreferencesService(db)
        await pref_service.update_user_logo(user_id, str(logo_path), corner_position)

        return {
            "message": "Logo uploaded successfully",
            "logo_path": str(logo_path),
            "corner_position": corner_position,
        }

    except Exception as e:
        logger.error(f"Error uploading logo: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading logo: {e}")


def run_dev():
    """Entry point for the dev server with automatic port selection."""
    import uvicorn
    import socket

    def find_available_port(start_port: int, max_attempts: int = 100) -> int:
        """Find an available port starting from start_port."""
        port = start_port
        while port < start_port + max_attempts:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    # Do NOT use SO_REUSEADDR here because we want to detect if it's truly busy
                    s.bind(("0.0.0.0", port))
                    return port
                except OSError:
                    port += 1
        return start_port

    # Start from configured default port
    start_port = Config.DEFAULT_BACKEND_PORT
    chosen_port = find_available_port(start_port)

    logger.info(f"🟢 Starting SupoClip Backend on port {chosen_port}")
    if chosen_port != start_port:
        logger.info(f"🟡 Port {start_port} was busy, shifted to {chosen_port}")

    # Run uvicorn with reload enabled
    # We use the factory string "src.main:app" to support reload
    uvicorn.run("src.main:app", host="0.0.0.0", port=chosen_port, reload=True)


if __name__ == "__main__":
    run_dev()
