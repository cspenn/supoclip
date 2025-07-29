from datetime import datetime
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, FastAPI, HTTPException, Request

from .models import User, Task, Source
from .database import init_db, close_db, get_db

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

@app.get("/")
def read_root():
  return {
      "message": "This is the SupoClip FastAPI-based API. Visit /docs for the API documentation."
  }

@app.get("/health/db")
async def check_database_health(db: AsyncSession = Depends(get_db)):
  """Check database connectivity"""
  try:
      await db.execute("SELECT 1")
      return {"status": "healthy", "database": "connected"}
  except Exception as e:
      return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@app.post("/start")
async def start_task(request: Request):
  """Placeholder for starting a new task"""
  data = await request.json()
  headers = request.headers

  raw_source = data.get("source")
  user_id = headers.get("user_id")

  if not raw_source["url"]:
    raise HTTPException(status_code=400, detail="Source URL is required")

  source = Source()
  source.type = source.decide_source_type(raw_source["url"])
  source.title = raw_source["title"]
  source.task_id = None

  async with get_db() as db:
    db.add(source)
    await db.commit()

  task = Task(
    user_id=user_id,
    source_id=source.id,
    generated_clips_ids=None,
    created_at=datetime.now(),
    updated_at=datetime.now(),
  )

  async with get_db() as db:
    db.add(task)
    await db.commit()

  return {"message": "Task started successfully"}
