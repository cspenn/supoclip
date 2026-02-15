# Development Work Plan: SupoClip

## Current Phase: Quality Assurance and Stabilization

The core video pipeline is functional. Current focus is on code quality, type safety, and documentation.

## Completed Milestones

### Phase 1: Core Pipeline
- [x] YouTube video download via yt-dlp
- [x] Video file upload
- [x] Transcription via parakeet-mlx (word-level timestamps)
- [x] AI-powered clip selection via Pydantic AI
- [x] 9:16 vertical clip generation with MoviePy
- [x] Smart face-centered cropping (MediaPipe + OpenCV fallbacks)
- [x] Word-level subtitle overlay
- [x] Custom font support (TTF)
- [x] Transition effects
- [x] SSE progress streaming
- [x] SQLite persistence for tasks, sources, clips

### Phase 2: Frontend
- [x] Next.js 15 web interface with App Router
- [x] Better Auth integration with Prisma adapter
- [x] Task submission and progress tracking UI
- [x] Clip preview and download
- [x] ShadCN UI components + TailwindCSS v4

## Active Work

### QA Campaign 1: Application Stability
- [ ] Add task completion postcondition checks
- [ ] Convert Config to Pydantic BaseSettings
- [ ] Migrate legacy typing imports to Python 3.11+ builtins
- [ ] Remove os.getenv() calls outside Config class

### QA Campaign 2: Code Quality
- [ ] Remove duplicate API endpoints
- [ ] Replace raw SQL with repository pattern
- [ ] Add file path markers to backend source files
- [ ] Remove dead code (unused wrappers, functions, parameters)
- [ ] Fix .gitignore and untrack artifacts
- [ ] Remove archive debugging scripts
- [ ] Fix bare except clauses
- [ ] Replace raw sqlite3 usage in video_utils.py

### QA Campaign 3: Bug Fixes
- [ ] Fix duration policy to respect user clip_min_length
- [ ] Fix parse_timestamp_to_seconds to raise on failure
- [ ] Update stale .serena memory files
- [ ] Clean up stale AssemblyAI references
- [ ] Update stale test files

### QA Campaign 4: Documentation
- [ ] Create missing docs (prd.md, workplan.md, polish.md, standards.md)
- [ ] Create .pre-commit-config.yaml

## Future Milestones

### Phase 3: Polish
- [ ] Error handling improvements
- [ ] Performance optimization (profiling, caching)
- [ ] Accessibility audit on frontend
- [ ] End-to-end testing with Playwright

### Phase 4: Release Preparation
- [ ] README with setup instructions
- [ ] Docker/container support for easy deployment
- [ ] CI/CD pipeline configuration
- [ ] License and contribution guidelines
