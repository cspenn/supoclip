# SupoClip Project Overview

## Purpose
SupoClip is an open-source alternative to OpusClip - an AI-powered video clipping tool that transforms long-form content (YouTube videos or uploaded files) into viral short clips (9:16 vertical format).

**Core Value Proposition:**
- Completely free (no subscription fees)
- No watermarks on generated clips
- Fully open source
- Self-hosted option available
- Unlimited usage

## Key Features
1. **Video Upload/YouTube Integration** - Download from YouTube or upload local videos
2. **AI Transcription** - Word-level timestamps via parakeet-mlx (offline, on-device)
3. **Intelligent Clip Selection** - Pydantic AI analyzes transcripts for viral segments (10-45s clips)
4. **Video Generation** - MoviePy creates clips with:
   - Smart face-centered cropping (MediaPipe + OpenCV + Haar cascade fallbacks)
   - parakeet-mlx-powered subtitles (word-level synchronization)
   - Custom fonts (TTF files in backend/fonts/)
   - Optional transition effects (MP4 files in backend/transitions/)
5. **Real-time Progress** - Server-Sent Events (SSE) for live processing updates
6. **Local Job Queue** - asyncio-based local queue for background processing

## Monorepo Structure
```
supoclip/
├── backend/       # Python FastAPI backend (port 8000)
├── frontend/      # Next.js 15 main app (port 3000)
├── waitlist/      # Next.js 15 landing page
└── CLAUDE.md      # Developer guidance
```

## System Information
- **OS**: macOS (Darwin)
- **Git Status**: Clean main branch
- **Package Managers**:
  - Backend: uv (Python)
  - Frontend: npm (Node.js)
