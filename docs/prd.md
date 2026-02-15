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
- **Subtitles**: Word-level synchronized, customizable font/size/color
- **Transitions**: Optional intro/outro effects from MP4 templates
- **Encoding**: H.264, even dimensions enforced

### 5. Real-Time Progress
- Server-Sent Events (SSE) for live progress updates during processing
- Task-based tracking with unique task IDs

### 6. Font and Style Customization
- Custom TTF fonts placed in `backend/fonts/`
- Configurable font family, size, and color per request
- System font discovery

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Deployment | Self-hosted, single machine |
| Database | SQLite (no external DB server) |
| Job queue | Local asyncio (no Redis/external queue) |
| Package manager | uv (backend), npm (frontend) |
| Python version | 3.11+ |
| System dependency | ffmpeg |

## Architecture

```
supoclip/
├── backend/       Python FastAPI API + video processing
├── frontend/      Next.js 15 web interface
└── waitlist/      Next.js 15 landing page (hosted version)
```

## Out of Scope (Current Phase)

- Multi-user SaaS deployment
- Cloud-based video processing
- Mobile native apps
- Real-time collaborative editing
- Billing and payment integration
