#!/bin/bash

# SupoClip - Native macOS Quick Start Script
# This script starts SupoClip with local-first configuration
# No .env file or API keys required for offline operation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================"
echo "  SupoClip - AI Video Clipping Tool"
echo "============================================"
echo ""

# Check if we're in the right directory
if [ ! -f "start.sh" ] && [ ! -f "./start.sh" ]; then
    echo -e "${RED}Error: This script must be run from the SupoClip root directory${NC}"
    exit 1
fi

# Create .env from .env.example if missing (don't error)
if [ ! -f .env ]; then
    echo -e "${BLUE}Creating .env from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ .env created with local-first defaults${NC}"
        echo ""
    else
        echo -e "${YELLOW}Note: No .env file found. Using built-in defaults.${NC}"
        echo ""
    fi
else
    echo -e "${GREEN}✓ Using existing .env configuration${NC}"
    echo ""
fi

# Check Python prerequisites
echo "Checking Python prerequisites..."
if [ ! -d "backend/.venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Setting up...${NC}"
    cd backend
    if command -v uv &> /dev/null; then
        uv venv .venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    else
        echo -e "${YELLOW}uv not found. Trying python3 -m venv...${NC}"
        python3 -m venv .venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi
    cd ..
    echo ""
fi

# Check if dependencies are installed
if [ ! -d "backend/.venv/lib" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    cd backend
    source .venv/bin/activate
    if command -v uv &> /dev/null; then
        uv sync
    else
        pip install -r requirements.txt 2>/dev/null || pip install -e . 2>/dev/null
    fi
    cd ..
    echo -e "${GREEN}✓ Python dependencies installed${NC}"
    echo ""
fi

# Check Node prerequisites
echo "Checking Node.js prerequisites..."
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Node dependencies not found. Installing...${NC}"
    cd frontend
    npm install --legacy-peer-deps
    cd ..
    echo -e "${GREEN}✓ Node dependencies installed${NC}"
    echo ""
fi

# Function to find available port
find_available_port() {
    local start_port=$1
    local max_attempts=${2:-10}
    local port=$start_port

    for ((i = 0; i < max_attempts; i++)); do
        # Check if port is in use
        if ! lsof -i ":$port" >/dev/null 2>&1; then
            echo $port
            return 0
        fi
        port=$((port + 1))
    done

    # No available port found
    return 1
}

# Check for available ports (default to 8008 and 3003)
echo "Checking for available ports..."
BACKEND_PORT=$(find_available_port 8008)
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Could not find available port starting from 8008${NC}"
    exit 1
fi

FRONTEND_PORT=$(find_available_port 3003)
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Could not find available port starting from 3003${NC}"
    exit 1
fi

if [ "$BACKEND_PORT" != "8008" ]; then
    echo -e "${YELLOW}⚠ Port 8008 in use, using port $BACKEND_PORT instead${NC}"
fi

if [ "$FRONTEND_PORT" != "3003" ]; then
    echo -e "${YELLOW}⚠ Port 3003 in use, using port $FRONTEND_PORT instead${NC}"
fi

echo ""

# Optional: Check if KoboldCPP is running (warn if not, don't block)
echo "Checking for local LLM service..."
if nc -z localhost 6969 2>/dev/null; then
    echo -e "${GREEN}✓ KoboldCPP is running on localhost:6969${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠ KoboldCPP not detected on localhost:6969${NC}"
    echo "  For local AI processing, start KoboldCPP:"
    echo "    brew install koboldcpp"
    echo "    koboldcpp --port 6969 --model <path-to-model.gguf>"
    echo "  (Video processing will still work with cloud LLM fallback)"
    echo ""
fi

# Summary
echo "============================================"
echo -e "${GREEN}Ready to start SupoClip!${NC}"
echo "============================================"
echo ""
echo "Services will run at:"
echo "  Frontend:  http://localhost:$FRONTEND_PORT"
echo "  Backend:   http://localhost:$BACKEND_PORT"
echo "  API Docs:  http://localhost:$BACKEND_PORT/docs"
echo ""
echo "Updating frontend environment with actual port..."
# Update frontend .env.local with the actual backend port if different
sed -i '' "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://localhost:$BACKEND_PORT|" frontend/.env.local
sed -i '' "s|NEXT_PUBLIC_APP_URL=.*|NEXT_PUBLIC_APP_URL=http://localhost:$FRONTEND_PORT|" frontend/.env.local
echo ""
echo "Starting services..."
echo ""

# Seed database with default user if needed
echo -e "${BLUE}Initializing database...${NC}"
cd backend
source .venv/bin/activate
python3 seed.py
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠ Database seeding failed (may already be seeded)${NC}"
fi
cd ..
echo ""

# Start backend in background
echo -e "${BLUE}Starting backend on port $BACKEND_PORT...${NC}"
cd backend
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > /tmp/supoclip_backend.log 2>&1 &
BACKEND_PID=$!
cd ..
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}✗ Backend failed to start. Check logs:${NC}"
    cat /tmp/supoclip_backend.log
    exit 1
fi
echo -e "${GREEN}✓ Backend started on port $BACKEND_PORT (PID: $BACKEND_PID)${NC}"
echo ""

# Start frontend in background
echo -e "${BLUE}Starting frontend on port $FRONTEND_PORT...${NC}"
cd frontend
PORT=$FRONTEND_PORT npm run dev > /tmp/supoclip_frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
sleep 3

# Check if frontend started successfully
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}✗ Frontend failed to start. Check logs:${NC}"
    cat /tmp/supoclip_frontend.log
    kill $BACKEND_PID
    exit 1
fi
echo -e "${GREEN}✓ Frontend started on port $FRONTEND_PORT (PID: $FRONTEND_PID)${NC}"
echo ""

# Success message
echo "============================================"
echo -e "${GREEN}SupoClip is running!${NC}"
echo "============================================"
echo ""
echo "📱 Frontend:  http://localhost:$FRONTEND_PORT"
echo "🔧 API Docs:  http://localhost:$BACKEND_PORT/docs"
echo "⚙️  Backend:   http://localhost:$BACKEND_PORT"
echo ""
echo "Configuration:"
echo "  - Transcription: MLX Whisper (local)"
echo "  - LLM: KoboldCPP (localhost:6969) or Cloud Fallback"
echo "  - Database: SQLite (local)"
echo "  - Job Queue: Local AsyncIO"
echo ""
echo "Logs:"
echo "  Backend:  tail -f /tmp/supoclip_backend.log"
echo "  Frontend: tail -f /tmp/supoclip_frontend.log"
echo ""
echo "To stop services:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "============================================"

# Keep script running and forward signals to child processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
