from .youtube_utils import *
from .video_utils import *
from .ai import *
from .config import Config
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/backend.log')
    ]
)

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from .models import User, Task, Source, GeneratedClip
from .database import init_db, close_db, get_db, AsyncSessionLocal

config = Config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        yield
    finally:
        await close_db()

app = FastAPI(
    title="SupoClip API",
    description="Python-based backend for SupoClip",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def start_task(request: Request):
  """Start a new task for authenticated users"""
  logger.info("🚀 Starting new task request")

  data = await request.json()
  headers = request.headers

  raw_source = data.get("source")
  user_id = headers.get("user_id")

  logger.info(f"📝 Request data - URL: {raw_source.get('url') if raw_source else 'None'}, User ID: {user_id}")

  if not raw_source or not raw_source.get("url"):
    logger.error("❌ Source URL is missing")
    raise HTTPException(status_code=400, detail="Source URL is required")

  if not user_id:
    logger.error("❌ User ID is missing")
    raise HTTPException(status_code=401, detail="User authentication required")

  # Validate user_id is a valid string and user exists
  if not user_id or len(user_id.strip()) == 0:
    logger.error(f"❌ Invalid user ID format: {user_id}")
    raise HTTPException(status_code=400, detail="Invalid user ID format")

  logger.info(f"🔍 Checking if user {user_id} exists in database")
  # Check if user exists in database
  async with AsyncSessionLocal() as db:
    user_exists = await db.execute(
      text("SELECT 1 FROM users WHERE id = :user_id"),
      {"user_id": user_id}
    )
    if not user_exists.fetchone():
      logger.error(f"❌ User {user_id} not found in database")
      raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"✅ User {user_id} found in database")

    source = Source()
    source.type = source.decide_source_type(raw_source["url"])
    logger.info(f"📺 Source type detected: {source.type}")

    if source.type == "youtube":
        logger.info("🎬 Getting YouTube video title")
        source.title = get_youtube_video_title(raw_source["url"])
        logger.info(f"📝 Video title: {source.title}")
    else:
        source.title = raw_source["title"]
        logger.info(f"📝 Custom title: {source.title}")

    relevant_segments_json = []
    clips_info = []
    relevant_parts = None

    logger.info("💾 Saving source and creating task in database")
    async with AsyncSessionLocal() as db:
        db.add(source)
        await db.flush()
        logger.info(f"✅ Source saved with ID: {source.id}")

        task = Task(
            user_id=user_id,
            source_id=source.id,
            generated_clips_ids=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        db.add(task)
        await db.commit()
        logger.info(f"✅ Task created with ID: {task.id}")

        if source.type == "youtube":
            logger.info("⬇️ Starting YouTube video download")
            video_path = download_youtube_video(raw_source["url"])
            if video_path:
                logger.info(f"✅ Video downloaded to: {video_path}")
                logger.info("🎤 Starting transcript generation with Whisper")
                transcript = get_video_transcript(video_path)
                logger.info(f"✅ Transcript generated (length: {len(transcript)} characters)")

                logger.info("🤖 Starting AI analysis for relevant segments")
                relevant_parts = await get_most_relevant_parts_by_transcript(transcript)
                logger.info(f"✅ AI analysis complete - found {len(relevant_parts.most_relevant_segments)} segments")

                # Convert to JSON format for response
                logger.info("📊 Converting AI results to JSON format")
                relevant_segments_json = [
                    {
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "text": segment.text,
                        "relevance_score": segment.relevance_score,
                        "reasoning": segment.reasoning
                    }
                    for segment in relevant_parts.most_relevant_segments
                ]
                logger.info(f"✅ Created {len(relevant_segments_json)} segment records")

                # Create clips from relevant segments
                logger.info("🎬 Starting video clip generation")
                clips_output_dir = Path(config.temp_dir) / "clips"
                logger.info(f"📁 Output directory: {clips_output_dir}")
                clips_info = create_clips_from_segments(video_path, relevant_segments_json, clips_output_dir)
                logger.info(f"✅ Generated {len(clips_info)} video clips")

                # Save clips to database
                logger.info("💾 Saving clips to database")
                async with AsyncSessionLocal() as db:
                    clip_ids = []
                    for i, clip_info in enumerate(clips_info):
                        logger.info(f"💾 Saving clip {i+1}/{len(clips_info)}: {clip_info['filename']}")
                        clip_record = GeneratedClip(
                            task_id=task.id,
                            filename=clip_info["filename"],
                            file_path=clip_info["path"],
                            start_time=clip_info["start_time"],
                            end_time=clip_info["end_time"],
                            duration=clip_info["duration"],
                            text=clip_info["text"],
                            relevance_score=clip_info["relevance_score"],
                            reasoning=clip_info["reasoning"],
                            clip_order=i + 1
                        )
                        db.add(clip_record)
                        await db.flush()
                        clip_ids.append(clip_record.id)
                        logger.info(f"✅ Clip {i+1} saved with ID: {clip_record.id}")

                    # Update task with clip IDs
                    logger.info(f"🔗 Updating task with {len(clip_ids)} clip IDs")
                    task_update = await db.execute(
                        text("UPDATE tasks SET generated_clips_ids = :clip_ids WHERE id = :task_id"),
                        {"clip_ids": clip_ids, "task_id": task.id}
                    )
                    await db.commit()
                    logger.info("✅ Task updated with clip IDs")
            else:
                logger.error("❌ Failed to download video")
                raise HTTPException(status_code=500, detail="Failed to download video")

        logger.info(f"🎉 Task completed successfully! Task ID: {task.id}")
    logger.info(f"📊 Final results - Segments: {len(relevant_segments_json)}, Clips: {len(clips_info)}")

    return {
        "message": "Task started successfully",
        "task_id": task.id,
        "relevant_segments": relevant_segments_json,
        "clips": clips_info,
        "summary": relevant_parts.summary if relevant_parts else None,
        "key_topics": relevant_parts.key_topics if relevant_parts else None
    }

@app.get("/tasks/{task_id}/clips")
async def get_task_clips(task_id: str, db: AsyncSession = Depends(get_db)):
  """Get all clips for a specific task"""
  try:
    # Get task and verify it exists
    task_result = await db.execute(
      text("SELECT * FROM tasks WHERE id = :task_id"),
      {"task_id": task_id}
    )
    task = task_result.fetchone()
    if not task:
      raise HTTPException(status_code=404, detail="Task not found")

    # Get clips for this task
    clips_result = await db.execute(
      text("""
        SELECT id, filename, file_path, start_time, end_time, duration,
               text, relevance_score, reasoning, clip_order, created_at
        FROM generated_clips
        WHERE task_id = :task_id
        ORDER BY clip_order ASC
      """),
      {"task_id": task_id}
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
        "video_url": f"/clips/{clip.filename}"  # URL for frontend to access the clip
      }
      clips_data.append(clip_data)

    return {
      "task_id": task_id,
      "clips": clips_data,
      "total_clips": len(clips_data)
    }

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error retrieving clips: {str(e)}")

@app.get("/tasks/{task_id}")
async def get_task_details(task_id: str, db: AsyncSession = Depends(get_db)):
  """Get task details including clips"""
  try:
    # Get task details
    task_result = await db.execute(
      text("""
        SELECT t.*, s.title as source_title, s.type as source_type
        FROM tasks t
        LEFT JOIN sources s ON t.source_id = s.id
        WHERE t.id = :task_id
      """),
      {"task_id": task_id}
    )
    task = task_result.fetchone()
    if not task:
      raise HTTPException(status_code=404, detail="Task not found")

    # Get clips count
    clips_count_result = await db.execute(
      text("SELECT COUNT(*) as count FROM generated_clips WHERE task_id = :task_id"),
      {"task_id": task_id}
    )
    clips_count = clips_count_result.fetchone().count

    task_data = {
      "id": task.id,
      "user_id": task.user_id,
      "source_id": task.source_id,
      "source_title": task.source_title,
      "source_type": task.source_type,
      "generated_clips_ids": task.generated_clips_ids,
      "clips_count": clips_count,
      "created_at": task.created_at.isoformat(),
      "updated_at": task.updated_at.isoformat()
    }

    return task_data

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error retrieving task: {str(e)}")
