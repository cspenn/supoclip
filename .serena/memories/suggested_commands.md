# SupoClip Development Commands

## Backend Setup & Running

### Initial Setup
```bash
cd backend
uv venv .venv                    # Create virtual environment
source .venv/bin/activate        # Activate (macOS/Linux)
# .venv\Scripts\activate         # Activate (Windows)
uv sync                          # Install dependencies
```

### Development Server (Main - Current)
```bash
cd backend
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Development Server (Refactored - Recommended)
```bash
cd backend
source .venv/bin/activate
uvicorn src.main_refactored:app --reload --host 0.0.0.0 --port 8000
```

### Worker Process (Refactored Only)
```bash
cd backend
source .venv/bin/activate
arq src.workers.tasks.WorkerSettings
```

### API Documentation
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## Frontend Setup & Running

### Development Server
```bash
cd frontend
npm install                      # Install dependencies
npm run dev                      # Start Turbopack dev server (port 3000)
```

### Production Build
```bash
cd frontend
npm run build                    # Build for production
npm start                        # Run production server
```

### Linting
```bash
cd frontend
npm run lint                     # Run ESLint
```

## Docker Commands

### Start All Services
```bash
docker-compose up -d             # Start in background
docker-compose up -d --build     # Rebuild images first
```

### Stop All Services
```bash
docker-compose down              # Stop and remove containers
docker-compose down -v           # WARNING: Also remove volumes (deletes data!)
```

### View Logs
```bash
docker-compose logs -f           # Follow all logs
docker-compose logs -f backend   # Follow backend logs only
docker-compose logs -f worker    # Follow worker logs only
docker-compose logs -f frontend  # Follow frontend logs only
docker-compose logs -f postgres  # Follow database logs
docker-compose logs -f redis     # Follow Redis logs
```

### Check Service Status
```bash
docker-compose ps                # List all services and status
docker-compose exec postgres psql -U supoclip -d supoclip  # Connect to DB
docker-compose exec redis redis-cli               # Connect to Redis
```

## Database Commands

### Connect to PostgreSQL
```bash
docker-compose exec postgres psql -U supoclip -d supoclip
# Or if local:
psql postgresql://supoclip:supoclip_password@localhost:5432/supoclip
```

### Redis Commands
```bash
docker-compose exec redis redis-cli
# Check job queue:
> KEYS arq:*
> LLEN arq:queue
> GET arq:job:{job_id}
```

### Reset Database (WARNING: Deletes all data!)
```bash
docker-compose down -v
docker-compose up -d
# Database will reinitialize from init.sql
```

## Git Commands

### Branch Management
```bash
git checkout -b feature/description      # Create feature branch
git checkout main                        # Switch to main
git pull origin main                     # Pull latest
```

### Committing Changes
```bash
git status                               # Check status
git add .                               # Stage all changes
git commit -m "message"                 # Commit (follow conventions)
git push origin branch-name              # Push to remote
```

## Quick Health Checks

### Backend Health
```bash
curl http://localhost:8000/health       # Basic health
curl http://localhost:8000/health/db    # Database connection
curl http://localhost:8000/health/redis # Redis connection (refactored only)
```

### Frontend Health
```bash
curl http://localhost:3000              # Check if running
```

### Environment Check
```bash
echo $DATABASE_URL                       # Check env var
echo $ASSEMBLY_AI_API_KEY               # Check API key loaded
env | grep -E "OPENAI|ANTHROPIC|GOOGLE" # Check AI provider keys
```

## Helpful Utility Commands

### macOS Specific
```bash
# Install system dependencies
brew install ffmpeg                      # Required for video processing
brew install uv                         # Python package manager
brew install redis                      # Optional: local Redis
brew install postgresql                 # Optional: local PostgreSQL

# Check if services are running
ps aux | grep uvicorn                   # Check backend process
ps aux | grep arq                       # Check worker process
ps aux | grep postgres                  # Check database
```

### File/Directory Navigation
```bash
find backend/src -name "*.py" -type f   # List all Python files
find frontend/src -name "*.tsx" -type f # List all TypeScript React files
ls -la backend/fonts/                   # List available fonts
ls -la backend/transitions/              # List available transitions
```

### Searching Code
```bash
grep -r "function_name" backend/src/    # Search backend
grep -r "ComponentName" frontend/src/   # Search frontend
grep -n "TODO\|FIXME" backend/src/**/*.py  # Find TODOs
```

## Environment Configuration

### Create .env file
```bash
cp .env.example .env
# Edit .env and add your API keys:
# - ASSEMBLY_AI_API_KEY
# - OPENAI_API_KEY (or GOOGLE_API_KEY or ANTHROPIC_API_KEY)
# - LLM=openai:gpt-4
# - BETTER_AUTH_SECRET (change from default in production)
```

### Verify Configuration
```bash
# Check .env is properly formatted
cat .env | grep -v "^#" | grep -v "^$"
# Run quick test
docker-compose up -d --build
docker-compose exec backend curl http://localhost:8000/health/db
```

## Common Development Workflows

### Testing a New Feature
1. Create branch: `git checkout -b feature/my-feature`
2. Run backend: `uvicorn src.main_refactored:app --reload`
3. Run frontend: `npm run dev`
4. Check logs: `docker-compose logs -f` (if using Docker)
5. Test API: `curl http://localhost:8000/docs`
6. Commit: `git commit -m "Add my feature"`

### Debugging Video Processing
```bash
# 1. Check backend logs
docker-compose logs -f backend
# 2. Check worker logs (refactored)
docker-compose logs -f worker
# 3. Check transcription caching
ls -la /app/uploads/.transcript_cache.json
# 4. Check generated clips
ls -la /app/clips/
```

### Working with Fonts
```bash
# Add new font
cp /path/to/font.ttf backend/fonts/
# Verify it's available
curl http://localhost:8000/fonts
```

### Working with Transitions
```bash
# Add new transition effect
cp /path/to/transition.mp4 backend/transitions/
# Verify it's available
curl http://localhost:8000/transitions
```
