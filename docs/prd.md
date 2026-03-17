# Product Requirements Document: SupoClip

## Vision

SupoClip is an open-source, self-hosted alternative to OpusClip. It transforms long-form video content into viral short-form clips using AI-powered analysis, with zero subscription fees, no watermarks, and unlimited usage.

## Problem Statement

Content creators need to repurpose long-form videos (podcasts, interviews, tutorials) into short-form clips for platforms like TikTok, Instagram Reels, and YouTube Shorts. Existing tools (OpusClip, Vidyo.ai) charge monthly subscriptions, add watermarks, and require uploading to third-party servers.

## Target Users

- Independent content creators with long-form video content
- Podcasters looking to create video highlights
- Marketing teams repurposing webinars and interviews
- Privacy-conscious creators who want local processing

## Core Features

### 1. Video Input
- **YouTube download**: Paste a URL; yt-dlp downloads the video
- **File upload**: Upload local video files via the web UI

### 2. AI Transcription
- **Engine**: parakeet-mlx (offline, on-device, word-level timestamps)
- **Output**: Full transcript with per-word timing data
- **Privacy**: All transcription runs locally; no data leaves the machine

### 3. Intelligent Clip Selection
- **Engine**: Pydantic AI with configurable LLM backend (local or cloud)
- **Selection criteria**: Strong hooks, valuable content, emotional moments, complete standalone thoughts
- **Output**: 3-7 segments per video, each 10-45 seconds
- **Validation**: start_time != end_time, minimum 5-10s duration

### 4. Video Generation
- **Format**: 9:16 vertical (short-form standard)
- **Smart cropping**: Face-centered using MediaPipe (primary), OpenCV DNN (fallback), Haar cascade (last resort)
- **Subtitles**: Word-level synchronized via pysubs2 + ffmpeg ASS filter; customizable font/size/color/stroke/shadow/position
- **Transitions**: Optional intro/outro effects from MP4 templates
- **Encoding**: H.264 via ffmpeg, even dimensions enforced

### 5. Real-Time Progress
- Live progress display during transcription, analysis, and clip generation
- Task-based tracking with persistent task history

### 6. Font and Style Customization
- Custom TTF fonts (including Google Fonts) placed in `fonts/`
- Configurable font family, size, color, stroke, shadow, and subtitle position per request
- System font discovery

### 7. Settings Persistence
- User preferences (fonts, clip lengths, AI prompt, logo, resolution) persisted across sessions

### 8. Task History and Clip Management
- View past processing jobs and their generated clips
- Download or delete individual clips

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Deployment | Self-hosted, single machine |
| Processes | Single Python process |
| Database | SQLite (no external DB server) |
| Job queue | Local asyncio (no Redis/external queue) |
| Package manager | uv only |
| Python version | 3.12 |
| Frontend | NiceGUI 3.0+ (Python, built on FastAPI) |
| Authentication | None (single-user local app) |
| Start command | `python -m src.main` |
| System dependency | ffmpeg |

## Architecture

SupoClip is a single all-Python application. NiceGUI provides the web interface as part of the same process as the backend, eliminating the need for a separate Node.js server.

```
supoclip/
├── src/           Python application (NiceGUI UI + FastAPI API + video processing)
├── fonts/         Custom TTF font files
└── transitions/   Transition effect MP4 templates
```

## Architecture Migration

SupoClip was originally built as a two-process split application: a Python/FastAPI backend and a React/Next.js frontend. While functional, this architecture required two package managers (uv and npm), two servers, and significant coordination overhead for a fundamentally single-user local tool.

The approved redesign consolidates everything into a single Python process using NiceGUI, which is built on top of FastAPI and provides a reactive web UI authored entirely in Python. Subtitle rendering migrates from Playwright-based browser rendering to pysubs2 + ffmpeg ASS filter (faster, no browser dependency), and video processing moves from MoviePy to direct ffmpeg calls. Authentication is removed entirely, as it was only bypassed locally anyway. The waitlist (hosted/SaaS landing page) is deleted from scope as the project focuses exclusively on the self-hosted use case.

## Out of Scope

- Multi-user SaaS deployment
- Cloud-based video processing
- Mobile native apps
- Real-time collaborative editing
- Billing and payment integration
- Hosted/waitlist version
