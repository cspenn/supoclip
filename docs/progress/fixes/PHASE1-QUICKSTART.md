# Phase 1: System Fonts Detection - Quick Start Guide

**Status:** Ready for Implementation
**Total Effort:** 8-10 hours across 12 VUWs
**Target Completion:** 1-2 developer days
**Branch:** `feature/system-fonts-detection`

---

## 30-Second Overview

Phase 1 adds system font detection to SupoClip, allowing users to:
- Use fonts already installed on their system
- Search fonts by name
- Refresh font detection on demand
- See fonts organized by type (bundled vs system)

**What gets built:**
- Backend FontService (detect, validate, cache fonts)
- 4 new API endpoints (/fonts, /fonts/search, /fonts/refresh, /fonts/{name})
- Enhanced FontSelector component with search
- SQLite caching of detected fonts

---

## VUW Execution Order

Run these VUWs sequentially. Each must pass `./checkpython.sh` with 100% tests passing.

| VUW | Name | Time | Status |
|-----|------|------|--------|
| 1 | Add Dependencies & FontService Skeleton | 30 min | [ ] |
| 2 | System Font Detection | 45 min | [ ] |
| 3 | Font Validation for MoviePy | 40 min | [ ] |
| 4 | Font Metadata Extraction | 45 min | [ ] |
| 5 | Database Model & Schema | 40 min | [ ] |
| 6 | Font API Routes | 50 min | [ ] |
| 7 | Database Caching | 45 min | [ ] |
| 8 | Font Refresh Functionality | 35 min | [ ] |
| 9 | Frontend FontSelector | 50 min | [ ] |
| 10 | Integration Testing | 60 min | [ ] |
| 11 | Documentation & Comments | 40 min | [ ] |
| 12 | Final Performance Verification | 50 min | [ ] |
| | **TOTAL** | **~8-10 hours** | |

---

## Before Starting

### Prerequisites Checklist

- [ ] Python 3.11+ installed: `python --version`
- [ ] Node.js 18+ installed: `node --version`
- [ ] Git available: `git status` (clean working tree)
- [ ] Backend repo accessible: `cd /Users/cspenn/Documents/github/supoclip/backend`
- [ ] Frontend repo accessible: `cd /Users/cspenn/Documents/github/supoclip/frontend`
- [ ] Read CLAUDE.md in project root
- [ ] Read full implementation plan: `docs/progress/fixes/phase1-system-fonts-implementation.md`

### Initial Git Checkpoint

```bash
cd /Users/cspenn/Documents/github/supoclip

# Create feature branch
git checkout -b feature/system-fonts-detection

# Create initial checkpoint
git add -A
git commit -m "CHECKPOINT: Phase 1 - Before system fonts detection implementation"
```

---

## VUW Summary Template

Each VUW follows this pattern:

```
1. Read step-by-step instructions in main document
2. Follow code examples provided
3. Make git checkpoint: git add -A && git commit -m "VUW N: Description"
4. Run verification: ./checkpython.sh
5. Confirm all checks pass (zero errors, 100% tests)
6. Move to next VUW
```

---

## Key Files to Modify/Create

### Backend Files
```
backend/
├── pyproject.toml                    # Add matplotlib, fonttools
├── src/
│   ├── models.py                     # Add SystemFont model
│   ├── main.py                       # Initialize FontService
│   ├── services/
│   │   └── font_service.py          # NEW - Core font logic
│   └── api/routes/
│       └── fonts.py                 # NEW - 4 API endpoints
└── fonts/                           # Existing bundled fonts
    ├── TikTokSans-Regular.ttf
    └── THEBOLDFONT-FREEVERSION.ttf
```

### Frontend Files
```
frontend/
├── src/
│   ├── components/
│   │   └── FontSelector.tsx         # NEW - Font dropdown component
│   ├── app/
│   │   └── settings/page.tsx        # Integrate FontSelector
│   └── lib/
└── prisma/
    └── schema.prisma                # Add SystemFont model
```

### Database Files
```
├── init.sql                          # Add system_fonts table
└── docs/
    ├── fonts.md                      # NEW - Feature documentation
    └── progress/fixes/
        └── phase1-system-fonts-implementation.md  # THIS PLAN
```

---

## Testing Each VUW

After each VUW, run:

```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Run quality checks (MUST PASS)
./checkpython.sh

# Expected output:
# ✓ ruff: zero errors
# ✓ mypy: zero errors
# ✓ bandit: zero errors
# ✓ pytest: 100% passing

# Then commit
git add -A
git commit -m "VUW N: [Description]"
```

---

## Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| `matplotlib` not installed | `cd backend && uv sync` |
| `fonttools` import error | `cd backend && uv sync` |
| Tests fail | Read error output, check docstrings match signatures |
| Database error | Delete `supoclip.db`, restart backend |
| Font not detected | Run refresh, check logs for matplotlib issues |
| Frontend errors | Clear `.next` cache, rebuild with `npm run build` |

---

## Success Indicators

By the end of Phase 1, you should be able to:

1. **Backend:**
   - `curl http://localhost:8000/fonts` returns JSON with fonts
   - `curl "http://localhost:8000/fonts/search?q=arial"` returns matches
   - `curl -X POST http://localhost:8000/fonts/refresh` detects fonts
   - Font files can be downloaded: `curl http://localhost:8000/fonts/TikTokSans-Regular -o /tmp/test.ttf`

2. **Frontend:**
   - FontSelector component renders in settings page
   - Can search fonts by typing
   - Refresh button works
   - Fonts separated into "Bundled" and "System" groups

3. **Code Quality:**
   - `./checkpython.sh` reports zero errors
   - All tests pass (100%)
   - No console errors

---

## Git Commands Quick Ref

```bash
# Check current branch
git branch

# Create feature branch
git checkout -b feature/system-fonts-detection

# Check status
git status

# Make checkpoint after each VUW
git add -A
git commit -m "VUW N: [Description]"

# View recent commits
git log --oneline -5

# Revert if needed
git reset --hard <commit_hash>
```

---

## Useful Commands

```bash
# Backend setup
cd /Users/cspenn/Documents/github/supoclip/backend
uv venv .venv
source .venv/bin/activate
uv sync

# Run backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v

# Run quality checks
./checkpython.sh

# Frontend setup
cd /Users/cspenn/Documents/github/supoclip/frontend
npm install
npm run dev

# Test API
curl http://localhost:8000/fonts | python -m json.tool
```

---

## Progress Tracking

Keep this checklist updated as you complete each VUW:

```markdown
# Phase 1 Progress

- [ ] VUW 1: Dependencies & Skeleton (30 min)
- [ ] VUW 2: System Font Detection (45 min)
- [ ] VUW 3: Font Validation (40 min)
- [ ] VUW 4: Metadata Extraction (45 min)
- [ ] VUW 5: Database Model (40 min)
- [ ] VUW 6: API Routes (50 min)
- [ ] VUW 7: Database Caching (45 min)
- [ ] VUW 8: Refresh Functionality (35 min)
- [ ] VUW 9: Frontend Component (50 min)
- [ ] VUW 10: Integration Testing (60 min)
- [ ] VUW 11: Documentation (40 min)
- [ ] VUW 12: Performance Verification (50 min)

**Total Time:** 530 minutes = 8.8 hours
**Status:** IN PROGRESS / COMPLETE
**Started:** [DATE]
**Completed:** [DATE]
```

---

## Where to Get Help

If you get stuck:

1. **Read the full plan:** `/Users/cspenn/Documents/github/supoclip/docs/progress/fixes/phase1-system-fonts-implementation.md`
2. **Check logs:** `docker-compose logs backend | tail -100`
3. **Review CLAUDE.md:** `/Users/cspenn/Documents/github/supoclip/CLAUDE.md`
4. **Check error messages:** Look at `checkpython.sh` output carefully
5. **Test endpoints manually:** Use curl commands above

---

## Next Phase

After Phase 1 is complete:
- Phase 2: Font previews and categorization
- Phase 3: Font uploading for premium users
- Phase 4: Advanced search filters

---

**Document Version:** 1.0
**Last Updated:** November 15, 2025
**Maintainer:** SupoClip Development Team
