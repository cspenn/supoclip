# Post-Task Completion Checklist

## Before Committing Code

### Python Backend (backend/)

- [ ] **Code Quality**
  - [ ] Type hints on all functions: `def function(param: Type) -> ReturnType:`
  - [ ] Docstrings for public functions (Google-style)
  - [ ] No unused imports
  - [ ] No hardcoded values (use config.py)

- [ ] **Testing**
  - [ ] No test framework currently in use
  - [ ] Manually test via API: `curl http://localhost:8000/docs`
  - [ ] Check logs for emoji markers (✅ for success, ❌ for errors)

- [ ] **Linting** (if configured)
  - [ ] Would run: `python -m flake8 src/` (if installed)
  - [ ] Currently no automatic linting configured

- [ ] **Format** (if configured)
  - [ ] Would run: `python -m black src/` (if installed)
  - [ ] Currently no auto-formatter configured

- [ ] **Database**
  - [ ] Created new models? Check models.py is updated
  - [ ] Need schema changes? Update init.sql
  - [ ] New migrations? Alembic directory is in place

### TypeScript/React Frontend (frontend/)

- [ ] **Code Quality**
  - [ ] TypeScript types defined for all props
  - [ ] No `any` types unless absolutely necessary
  - [ ] Components properly exported
  - [ ] No unused imports
  - [ ] Proper error handling with try/catch

- [ ] **Linting**
  - [ ] Run: `npm run lint`
  - [ ] Fix any issues before committing
  - [ ] Check for React 19 compatibility warnings

- [ ] **Testing**
  - [ ] No test framework currently in use
  - [ ] Manual testing in browser http://localhost:3000

- [ ] **Build**
  - [ ] Test production build: `npm run build`
  - [ ] Verify no errors or warnings
  - [ ] `next/image` components properly optimized

- [ ] **API Integration**
  - [ ] Frontend calls correct backend endpoints
  - [ ] Error handling for API failures
  - [ ] Loading states implemented
  - [ ] Authentication tokens properly sent

### Environment & Configuration

- [ ] **Environment Variables**
  - [ ] No secrets hardcoded in code
  - [ ] New env vars added to .env.example
  - [ ] Backend .env properly set
  - [ ] Frontend NEXT_PUBLIC_* vars set

- [ ] **Dependencies**
  - [ ] Backend: Run `uv sync` and commit uv.lock if changed
  - [ ] Frontend: Run `npm install` if changed and commit package-lock.json

### Docker & Deployment

- [ ] **Docker**
  - [ ] Test with: `docker-compose up -d --build`
  - [ ] Check all services healthy: `docker-compose ps`
  - [ ] Test API: `curl http://localhost:8000/health`
  - [ ] Check logs: `docker-compose logs -f`

- [ ] **Database**
  - [ ] If schema changed, update init.sql
  - [ ] Migration tested: `docker-compose down -v && docker-compose up -d`
  - [ ] Data persists: `docker-compose restart postgres`

### Git & Commit

- [ ] **Code Review Self-Check**
  - [ ] Read through your diff
  - [ ] Remove debug code/comments
  - [ ] No console.log() or print() statements left
  - [ ] Follows project conventions

- [ ] **Commit Message**
  - [ ] Descriptive message in present tense
  - [ ] Example: "Add clip list endpoint" or "Fix face detection fallback"
  - [ ] No generic messages like "update" or "fix"

- [ ] **Testing Before Push**
  - [ ] Backend feature: Test via API docs
  - [ ] Frontend feature: Test in browser
  - [ ] Full integration: Test end-to-end
  - [ ] Check logs for errors

## Choosing Entry Point

### When to Use `main.py` (Old Monolithic)
- Bug fixes to existing endpoints
- Working on deprecated `/start` or `/start-with-progress`
- Local testing without Redis
- Simple features that don't need job queue

### When to Use `main_refactored.py` (New Layered)
- **RECOMMENDED for all new features**
- New endpoints (especially `/tasks` CRUD operations)
- Progress tracking with SSE
- Background job processing
- Job persistence across restarts
- Features requiring Redis

## Testing Checklist by Feature Type

### Video Processing Feature
- [ ] Backend accepts video upload/YouTube URL
- [ ] Transcription completes without errors
- [ ] AI analysis identifies clips correctly
- [ ] Video clips generated with proper dimensions (9:16)
- [ ] Clips saved to correct directory
- [ ] Metadata stored in database
- [ ] No memory leaks (check process memory)
- [ ] Clips playable in frontend

### API Endpoint Feature
- [ ] Endpoint accessible at documented path
- [ ] Correct HTTP method (GET/POST/PATCH)
- [ ] Parameters validated
- [ ] Error responses with appropriate status codes
- [ ] Documentation in code comments
- [ ] Swagger UI shows correct spec
- [ ] Authentication check (if user_id required)

### Frontend Feature
- [ ] Page renders without errors
- [ ] Responsive design works on mobile
- [ ] Dark mode (if using next-themes) works
- [ ] API calls succeed and display data
- [ ] Loading states show correctly
- [ ] Error messages display
- [ ] No console warnings/errors

### Authentication Feature
- [ ] Better Auth endpoints working
- [ ] Session persists correctly
- [ ] Protected routes redirect unauthenticated
- [ ] Logout clears session
- [ ] User preferences saved (if applicable)

## Debugging Tips Before Commit

### Backend Debugging
```bash
# Check logs with emoji markers
docker-compose logs backend | grep "❌"  # Find errors
docker-compose logs backend | grep "✅"  # Find successes

# Direct testing
curl http://localhost:8000/health/db
curl http://localhost:8000/docs  # Swagger UI

# Database check
docker-compose exec postgres psql -U supoclip -d supoclip
# SELECT * FROM tasks WHERE created_at > NOW() - INTERVAL '1 hour';
```

### Frontend Debugging
```bash
# Check browser console for errors
# Check Network tab in DevTools for API failures
# Check build output
npm run build 2>&1 | grep -i "error\|warning"
```

### Worker Debugging
```bash
# Check worker is running
docker-compose logs worker | tail -50

# Check Redis queue
docker-compose exec redis redis-cli
# > KEYS arq:*
# > LLEN arq:queue
```

## Final Verification Before Push

```bash
# 1. All services running
docker-compose ps

# 2. No build errors
docker-compose logs | grep -i "error"

# 3. Database healthy
curl http://localhost:8000/health/db

# 4. Tests passed (if applicable)
# npm run test  # (not configured)

# 5. Linting passed
npm run lint

# 6. Code looks good
git diff --staged  # Review changes

# 7. Ready to commit
git commit -m "descriptive message"
```

## Important Don'ts ❌

- ❌ Don't commit API keys or secrets
- ❌ Don't commit node_modules/ or .venv/
- ❌ Don't leave console.log() or print() statements
- ❌ Don't push to main branch directly (create PR instead)
- ❌ Don't change CLAUDE.md without updating the audit report
- ❌ Don't use blocking operations in async code
- ❌ Don't mix snake_case and camelCase in same table
- ❌ Don't hardcode URLs (use NEXT_PUBLIC_API_URL)
- ❌ Don't forget to commit lock files (uv.lock, package-lock.json)
- ❌ Don't modify init.sql without testing migrations
