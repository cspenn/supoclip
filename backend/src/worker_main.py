"""
Worker process entry point.
Run this to start background job workers.

Usage:
    arq src.workers.tasks.WorkerSettings
"""
import logging
from arq import run_worker
from .workers.tasks import WorkerSettings
from .config import Config
from .logging_config import setup_logging

# Configure configuration and logging
config = Config()
setup_logging(config.get_log_level(), config.log_dir, "worker")

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting SupoClip worker...")
    logger.info(f"Redis: {Config().redis_host}:{Config().redis_port}")
    run_worker(WorkerSettings)
