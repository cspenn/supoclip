#!/bin/bash
# SupoClip Backend Start Script
# Starts the FastAPI backend server with local-first configuration

# Make sure pwd ends with backend
if [ "$(basename "$PWD")" != "backend" ]; then
  echo "Error: Please run this script from the backend directory"
  exit 1
fi

# Make sure .venv exists
if [ ! -d ".venv" ]; then
  echo "Error: .venv directory not found"
  echo "Please run: uv sync"
  exit 1
fi

# Activate the virtual environment
source .venv/bin/activate

echo "============================================"
echo "  SupoClip Backend Server"
echo "============================================"
echo ""
echo "Configuration:"
echo "  - Transcription: MLX Whisper (local)"
echo "  - LLM: Local-first (KoboldCPP) with cloud fallback"
echo "  - Database: SQLite"
echo "  - Job Queue: Local AsyncIO"
echo ""
echo "Starting server on http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo "============================================"
echo ""

# Start the application
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
