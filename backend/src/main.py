from .config import Config
from .logging_config import setup_logging, cleanup_old_logs
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import init_db, close_db, get_db, AsyncSessionLocal
from .api.routes.tasks import router as tasks_router
from .api.routes.fonts import router as fonts_router
from .workers.local_queue import get_job_queue
from .services.font_service import FontService
from .services.video_service_legacy import LegacySyncVideoService
from .services.video_service_async import AsyncVideoProcessingService
from .services.user_preferences_service import UserPreferencesService
from .dependencies import set_font_service, get_current_user
from .utils.font_options import parse_font_options

# Configure configuration and logging
config = Config()
setup_logging(config.get_log_level(), config.log_dir, "backend")

# Clean up old logs on startup
cleanup_old_logs(config.log_dir, config.log_retention_days)

logger = logging.getLogger(__name__)


async def initialize_font_service(db_session: AsyncSession) -> None:
    """Initialize font service with database session."""
    font_service = FontService(db_session=db_session, temp_dir=Path(config.temp_dir))
    set_font_service(font_service)

    logger.info("🚀 Initializing FontService...")

    # Load bundled fonts
    bundled = await font_service.get_bundled_fonts()
    await font_service.cache_fonts(bundled)
    logger.info(f"✅ Loaded {len(bundled)} bundled fonts")

    # Detect and cache system fonts in background
    asyncio.create_task(_detect_system_fonts_background(font_service))


async def _detect_system_fonts_background(font_service: FontService) -> None:
    """Background task to detect and cache system fonts."""
    try:
        logger.info("🔍 Starting background system font detection...")
        system_fonts = await font_service.detect_system_fonts()
        await font_service.cache_fonts(system_fonts)
        logger.info(f"✅ Detected and cached {len(system_fonts)} system fonts")
    except Exception as e:
        logger.error(f"❌ Background font detection failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()

        # Initialize font service
        async with AsyncSessionLocal() as session:
            await initialize_font_service(session)

        # Initialize job queue
        queue = get_job_queue()
        await queue.start_workers()
        logger.info("Job queue workers started")

        yield
    finally:
        # Shutdown job queue
        try:
            queue = get_job_queue()
            await queue.stop_workers()
            logger.info("Job queue workers stopped")
        except Exception as e:
            logger.error(f"Error stopping workers: {e}")

        await close_db()


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
        "message": "This is the SupoClip FastAPI-based API. Visit /docs for the API documentation."
    }


@app.get("/health/db")
async def check_database_health(db: AsyncSession = Depends(get_db)):
    """Check database connectivity"""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@app.post("/start")
async def start_task(request: Request, user_id: str = Depends(get_current_user)):
    """Start a new task for authenticated users (legacy synchronous endpoint)"""
    logger.info(f"Starting new task request for user {user_id}")

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

    logger.info(f"Processing request for authenticated user {user_id}")
    # Load and merge user preferences with request options
    async with AsyncSessionLocal() as db:
        try:
            # Use UserPreferencesService to handle all preference logic
            pref_service = UserPreferencesService(db)

            # Merge preferences: request > user prefs > defaults
            request_opts = {
                **parsed_font_opts,
                "clip_min_length": data.get("clip_min_length"),
                "clip_target_length": data.get("clip_target_length"),
                "clip_max_length": data.get("clip_max_length"),
                "custom_ai_prompt": data.get("custom_ai_prompt"),
                "output_resolution": data.get("output_resolution"),
            }

            preferences = await pref_service.merge_with_request_options(
                user_id, request_opts
            )
            logo_path = pref_service.get_logo_path(preferences)

            logger.info(f"User {user_id} preferences loaded and merged")

        except ValueError as e:
            logger.error(f"Error loading user preferences: {e}")
            raise HTTPException(status_code=404, detail="User not found")

        # Use legacy sync service
        service = LegacySyncVideoService(db, config)
        result = await service.process_video(
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
        return result


@app.post("/start-with-progress")
async def start_task_with_progress(
    request: Request, user_id: str = Depends(get_current_user)
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
    async with AsyncSessionLocal() as db:
        try:
            # Use UserPreferencesService to handle all preference logic
            pref_service = UserPreferencesService(db)

            # Merge preferences: request > user prefs > defaults
            request_opts = {
                **parsed_font_opts,
                "clip_min_length": data.get("clip_min_length"),
                "clip_target_length": data.get("clip_target_length"),
                "clip_max_length": data.get("clip_max_length"),
                "custom_ai_prompt": data.get("custom_ai_prompt"),
                "output_resolution": data.get("output_resolution"),
            }

            preferences = await pref_service.merge_with_request_options(
                user_id, request_opts
            )
            logo_path = pref_service.get_logo_path(preferences)

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


@app.get("/tasks/{task_id}/clips")
async def get_task_clips(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get all clips for a specific task"""
    try:
        # Get task and verify it exists
        task_result = await db.execute(
            text("SELECT * FROM tasks WHERE id = :task_id"), {"task_id": task_id}
        )
        task = task_result.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Get clips for this task
        clips_result = await db.execute(
            text(
                """
        SELECT id, filename, file_path, start_time, end_time, duration,
               text, relevance_score, reasoning, clip_order, created_at
        FROM generated_clips
        WHERE task_id = :task_id
        ORDER BY clip_order ASC
      """
            ),
            {"task_id": task_id},
        )
        clips = clips_result.fetchall()

        # Convert to list of dictionaries and add serving URLs
        clips_data = []
        for clip in clips:
            clip_data = {
                "id": clip.id,
                "filename": clip.filename,
                "file_path": clip.file_path,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "duration": clip.duration,
                "text": clip.text,
                "relevance_score": clip.relevance_score,
                "reasoning": clip.reasoning,
                "clip_order": clip.clip_order,
                "created_at": clip.created_at.isoformat(),
                # URL for frontend to access the clip
                "video_url": f"/clips/{clip.filename}",
            }
            clips_data.append(clip_data)

        return {"task_id": task_id, "clips": clips_data, "total_clips": len(clips_data)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving clips: {str(e)}")


@app.get("/tasks/{task_id}")
async def get_task_details(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get task details including clips"""
    try:
        # Get task details
        task_result = await db.execute(
            text(
                """
        SELECT t.*, s.title as source_title, s.type as source_type
        FROM tasks t
        LEFT JOIN sources s ON t.source_id = s.id
        WHERE t.id = :task_id
      """
            ),
            {"task_id": task_id},
        )
        task = task_result.fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Get clips count
        clips_count_result = await db.execute(
            text(
                "SELECT COUNT(*) as count FROM generated_clips WHERE task_id = :task_id"
            ),
            {"task_id": task_id},
        )
        clips_count_row = clips_count_result.fetchone()
        clips_count = clips_count_row.count if clips_count_row else 0

        task_data = {
            "id": task.id,
            "user_id": task.user_id,
            "source_id": task.source_id,
            "source_title": task.source_title,
            "source_type": task.source_type,
            "status": task.status,
            "generated_clips_ids": task.generated_clips_ids,
            "clips_count": clips_count,
            "font_family": task.font_family if hasattr(task, "font_family") else None,
            "font_size": task.font_size if hasattr(task, "font_size") else None,
            "font_color": task.font_color if hasattr(task, "font_color") else None,
            # Include progress_message for error reporting (Fix 3: User-visible error messages)
            "progress_message": (
                task.progress_message if hasattr(task, "progress_message") else None
            ),
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }

        return task_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task: {str(e)}")


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
        logger.error(f"Error retrieving transitions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving transitions: {str(e)}"
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
        logger.error(f"Error retrieving default prompt: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving default prompt: {str(e)}"
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
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading video: {str(e)}")


@app.post("/upload-logo")
async def upload_logo(request: Request, user_id: str = Depends(get_current_user)):
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

        # Update user record
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE users SET logo_file_path = :logo_path, logo_corner_position = :position WHERE id = :user_id"
                ),
                {
                    "logo_path": str(logo_path),
                    "position": corner_position,
                    "user_id": user_id,
                },
            )
            await db.commit()

        logger.info(f"Logo uploaded for user {user_id}: {logo_path}")

        return {
            "message": "Logo uploaded successfully",
            "logo_path": str(logo_path),
            "corner_position": corner_position,
        }

    except Exception as e:
        logger.error(f"Error uploading logo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading logo: {str(e)}")
