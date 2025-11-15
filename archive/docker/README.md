# Docker Archive

This directory contains Docker-based configurations that have been archived as the project migrates to native macOS support.

## Files

- **docker-compose.yml** - Original Docker Compose configuration (PostgreSQL, Redis, Backend, Frontend)
- **backend-Dockerfile** - Backend Docker image configuration
- **frontend-Dockerfile** - Frontend Docker image configuration
- **start.sh.docker.old** - Original start.sh script that required Docker

## Why These Are Archived

The project has migrated to **native macOS support** with:
- **Database:** SQLite (local) instead of PostgreSQL (containerized)
- **Job Queue:** Local asyncio instead of Redis (containerized)
- **Transcription:** MLX Whisper (local) instead of cloud services
- **LLM:** Local KoboldCPP instead of cloud APIs
- **Startup:** Single `./start.sh` command handles everything

## Using Docker (If Needed)

If you prefer to use Docker:
1. Copy files from this archive back to the project root
2. Use `docker-compose up` to start services
3. Note: This approach requires more resources and internet for container downloads

## Migration Notes

The native approach is now the default and recommended. If you were using the Docker version:

**Old Docker approach:**
```bash
docker-compose up -d  # Started PostgreSQL, Redis, containers
```

**New native approach:**
```bash
./start.sh  # Starts everything natively with local-first defaults
```

## Performance Comparison

| Aspect | Docker | Native |
|--------|--------|--------|
| Startup Time | 2-3 minutes | 30-60 seconds |
| Resource Usage | 2-4GB RAM | 500MB-1GB |
| Database | PostgreSQL container | SQLite local file |
| Transcription | Cloud or container | MLX Whisper (local) |
| LLM | Cloud or container | KoboldCPP (local) |

For more information, see the main project documentation in `QUICKSTART.md` and `CLAUDE.md`.
