from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    """Configuration for SupoClip backend (native macOS version).

    Uses:
    - SQLite for database (not PostgreSQL)
    - MLX Whisper for transcription (not AssemblyAI)
    - Local asyncio queue for jobs (not Redis/arq)
    """

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        # MLX Whisper transcription model
        # Options: tiny, base, small, medium, large
        self.mlx_whisper_model = os.getenv("MLX_WHISPER_MODEL", "medium")

        # LLM configuration for transcript analysis
        self.llm = os.getenv(
            "LLM_MODEL",
            "google:gemini-2.5-flash-lite"
        )
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

        # Video processing settings
        self.max_video_duration = int(os.getenv("MAX_VIDEO_DURATION", "3600"))
        self.output_dir = os.getenv("OUTPUT_DIR", "outputs")

        # Clip generation settings
        self.max_clips = int(os.getenv("MAX_CLIPS", "10"))
        self.clip_duration = int(os.getenv("CLIP_DURATION", "30"))  # seconds

        # Temporary directory for video processing
        self.temp_dir = os.getenv("TEMP_DIR", "temp")

        # Database URL (SQLite)
        self.database_url = os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./supoclip.db"
        )

        # Local job queue settings
        self.max_workers = int(os.getenv("MAX_WORKERS", "2"))
        self.worker_timeout = int(os.getenv("WORKER_TIMEOUT", "3600"))
