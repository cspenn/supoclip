# Pre-Execution Checklist for Deduplication Plan
**Date**: 2025-11-16
**Timeline**: 7 hours of work before starting implementation
**Assigned To**: [Team to determine]

---

## Overview

This checklist ensures the plan is ready for execution. Completing these items prevents 4-8 hour production incidents later.

**Total Effort**: 7 hours
**Timeline**: 2-3 days before Phase 1 begins
**Cost**: 7 hours now vs. 20-40 hours of incident response later

---

## Section 1: Plan Verification (1 hour)

### 1.1 Re-verify Line Numbers in Plan

**Why**: Original plan may reference outdated line numbers. Starting with wrong references causes rework.

**Task**:
- [ ] Open original plan: `docs/progress/fixes/codebase-deduplication-plan-2025-11-16.md`
- [ ] Open each file mentioned and verify line numbers:
  - [ ] `frontend/src/app/page.tsx` (status badge logic around line 357-369)
  - [ ] `frontend/src/app/list/page.tsx` (getStatusBadge function around line 62-95)
  - [ ] `frontend/src/app/tasks/[id]/page.tsx` (status rendering)
  - [ ] `frontend/src/app/settings/page.tsx`
  - [ ] `backend/src/main.py` (legacy endpoint)
  - [ ] `backend/src/workers/tasks.py` (async processing)

**Deliverable**: Updated plan with correct line numbers, or document where numbers differ

**Assigned To**: [Frontend dev + Backend dev]
**Time**: 1 hour
**Status**: Not started

---

### 1.2 Document Current Code Patterns

**Why**: Need to understand how duplication currently manifests before extracting.

**Task**:
- [ ] Copy problematic code blocks into analysis document
- [ ] Highlight the duplicated sections
- [ ] Note any variations between duplications
- [ ] Document how each piece is currently used

**Example**:
```typescript
// frontend/src/app/page.tsx (lines 357-369)
function getStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge>Completed</Badge>
    // ...
  }
}

// frontend/src/app/list/page.tsx (lines 62-95)
function getStatusBadge(status: string) {  // SAME FUNCTION
  switch (status) {
    case "completed":
      return <Badge>Completed</Badge>
    // ...
  }
}
```

**Deliverable**: Document: `Current Code Patterns Analysis`

**Assigned To**: [Frontend dev]
**Time**: 30 minutes
**Status**: Not started

---

## Section 2: Testing Infrastructure Setup (2 hours)

### 2.1 Create Frontend Testing Template

**Why**: Need consistent test structure for all new components.

**Task**:
- [ ] Review existing test patterns (if any exist)
- [ ] Create template file: `frontend/src/components/__tests__/TEMPLATE.test.tsx`
- [ ] Include examples for:
  - Component rendering
  - Props validation
  - User interactions
  - Error states
  - Loading states

**Template Structure**:
```typescript
import { render, screen } from '@testing-library/react';
import { ComponentName } from '../ComponentName';

describe('ComponentName', () => {
  describe('Rendering', () => {
    it('should render component with required props', () => {
      render(<ComponentName prop1="value" />);
      expect(screen.getByText('expected')).toBeInTheDocument();
    });
  });

  describe('Props', () => {
    it('should handle optional className prop', () => {
      const { container } = render(
        <ComponentName className="custom" />
      );
      expect(container.firstChild).toHaveClass('custom');
    });
  });

  describe('Error Handling', () => {
    it('should display error message when provided', () => {
      render(<ComponentName error="Error occurred" />);
      expect(screen.getByText('Error occurred')).toBeInTheDocument();
    });
  });
});
```

**Deliverable**: Template file + README with instructions

**Assigned To**: [Frontend test lead]
**Time**: 45 minutes
**Status**: Not started

---

### 2.2 Create Backend Testing Template

**Why**: Need consistent test structure for backend services/dependencies.

**Task**:
- [ ] Review existing test patterns
- [ ] Create template file: `backend/tests/test_template.py`
- [ ] Include examples for:
  - Sync function tests
  - Async function tests
  - Dependency injection
  - Error handling
  - Database interaction

**Template Structure**:
```python
import pytest
from backend.src.services.service_name import ServiceName

@pytest.fixture
def mock_db():
    """Mock database session"""
    return MagicMock()

@pytest.fixture
def service(mock_db):
    """Create service with mocked dependencies"""
    return ServiceName(db_session=mock_db, config=Config())

class TestServiceName:
    @pytest.mark.asyncio
    async def test_method_success(self, service):
        """Test happy path"""
        result = await service.method(arg1="value")
        assert result is not None
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_method_error_handling(self, service, mock_db):
        """Test error scenarios"""
        mock_db.query.side_effect = Exception("DB Error")
        with pytest.raises(ServiceError):
            await service.method(arg1="value")
```

**Deliverable**: Template file + README with instructions

**Assigned To**: [Backend test lead]
**Time**: 45 minutes
**Status**: Not started

---

## Section 3: Architecture Design (2 hours)

### 3.1 Document Current Auth Flow

**Why**: Phase 2 and Phase 3 both touch auth. Need clear understanding before implementation.

**Task**:
- [ ] Diagram: Frontend session flow
  - How useSession() gets session
  - Where session comes from
  - How user_id is stored in session

- [ ] Diagram: Backend auth flow
  - How user_id header gets validated
  - Current dependency injection approach
  - Where decisions are made about user_id

- [ ] Document the mismatch
  - Frontend has session context
  - Backend expects header
  - How do they communicate?

- [ ] Create comparison table
  - Frontend auth approach
  - Backend auth approach
  - Proposed unified approach (AuthContext)

**Deliverable**: `Auth Flow Architecture Document` with diagrams

**Assigned To**: [Senior dev or architect]
**Time**: 60 minutes
**Status**: Not started

---

### 3.2 Design AuthContext for Phase 2

**Why**: Critical to avoid auth failures in Phase 2 pages.

**Task**:
- [ ] Review proposal in deep analysis document
- [ ] Design final AuthContext interface:
  ```typescript
  interface AuthContextValue {
    session: Session | null
    userId: string | null
    isLoading: boolean
  }
  ```

- [ ] Decide: Provider location (root layout vs wrapper)
- [ ] Decide: Default values for unauthenticated
- [ ] Decide: Error handling (what if session expires)
- [ ] Get team approval before coding starts

**Deliverable**: `AuthContext Design Document` with:
- Final interface definition
- Provider location decision
- Integration points
- Error scenarios

**Assigned To**: [Architect or senior frontend dev]
**Time**: 45 minutes
**Status**: Not started

---

## Section 4: Pre-Phase-1 Verifications (1.5 hours)

### 4.1 Verify Build Pipeline

**Why**: Ensure testing/building works before making changes.

**Task**:
- [ ] Run frontend build: `npm run build`
  - Record output, baseline build time
  - Verify zero TypeScript errors
  - Document any warnings

- [ ] Run frontend lint: `npm run lint`
  - Verify passes
  - Document any pre-existing issues

- [ ] Run frontend tests: `npm test`
  - Verify tests run
  - Document baseline test count and pass rate

- [ ] Run backend checks: `./checkpython.sh`
  - Verify passes with 100% passing tests
  - Document baseline metrics

**Deliverable**: `Baseline Metrics Document`
```
Frontend:
- Build time: X seconds
- TypeScript errors: 0
- Lint warnings: N
- Jest tests: N tests, M passing

Backend:
- checkpython.sh: PASS
- Test count: N passing
- Type errors: 0
```

**Assigned To**: [Devops or build lead]
**Time**: 45 minutes
**Status**: Not started

---

### 4.2 Verify Git Workflow

**Why**: Need to establish VUW commit practice before starting.

**Task**:
- [ ] Create git template for VUW commits
  ```bash
  VUW-QW-001: Create StatusBadge component

  - Extract status badge rendering logic
  - Supports: pending, processing, completed, failed, error
  - Used in: page.tsx, list/page.tsx, tasks/[id]/page.tsx
  - Tests: 3 variants tested
  - Related to: codebase-deduplication-plan
  ```

- [ ] Document rollback procedure:
  - `git log --oneline -20` to find commit
  - `git revert [commit-hash]` to rollback individual VUW
  - Keep commit history for audit trail

- [ ] Create pre-commit checklist:
  - [ ] Tests pass locally
  - [ ] Build succeeds
  - [ ] Linting passes
  - [ ] No console errors
  - [ ] VUW-specific tests added

**Deliverable**: `Git Workflow Document`

**Assigned To**: [Tech lead]
**Time**: 30 minutes
**Status**: Not started

---

## Section 5: Risk Mitigation Planning (1.5 hours)

### 5.1 Create Rollback Runbook

**Why**: If something breaks, need clear recovery procedure.

**Task**:
- [ ] Document rollback for Phase 1 (component extraction)
  - Time to rollback: 5-10 minutes per component
  - Procedure: `git revert [commit]`
  - Data impact: None (frontend only)

- [ ] Document rollback for Phase 2 (auth/hooks)
  - Time to rollback: 30-60 minutes
  - Procedure: `git revert [commits] --no-edit`
  - Restore inline auth code from backup
  - Data impact: None (frontend only)

- [ ] Document rollback for Phase 3 (backend)
  - Time to rollback: 15-30 minutes (with gradual rollout)
  - Procedure: Set `ASYNC_ROLLOUT_PERCENTAGE=0` in config
  - Investigate while in fallback mode
  - Data impact: Check consistency

**Deliverable**: `Rollback Runbook` with step-by-step procedures

**Assigned To**: [Release manager or tech lead]
**Time**: 45 minutes
**Status**: Not started

---

### 5.2 Setup Monitoring for Phase 3

**Why**: Gradual rollout requires real-time metrics.

**Task**:
- [ ] Identify metrics to track:
  - Request count by service (sync vs async)
  - Error count by service
  - Error rate % by service
  - Response time by service
  - Task completion time

- [ ] Choose monitoring approach:
  - Datadog / NewRelic / CloudWatch? (or custom)
  - Dashboard setup
  - Alerting rules

- [ ] Define halt conditions:
  - Error rate >5% → halt rollout
  - Response time +50% → halt rollout
  - Data inconsistency detected → halt rollout

**Deliverable**: `Phase 3 Monitoring Plan`

**Assigned To**: [Devops or platform engineer]
**Time**: 45 minutes
**Status**: Not started

---

## Section 6: Stakeholder Communication (0.5 hours)

### 6.1 Schedule Team Discussions

**Task**:
- [ ] Schedule design review for Phase 3 approach
  - Attendees: [list]
  - Time: 30 minutes
  - Goal: Approve parallel endpoint approach

- [ ] Schedule Phase 1 kickoff
  - Attendees: [frontend team]
  - Time: 30 minutes
  - Goal: Review plan, assign VUWs, establish cadence

- [ ] Schedule Phase 2 kickoff
  - Attendees: [frontend team]
  - Time: 30 minutes
  - Goal: Review auth architecture, discuss integration

- [ ] Schedule Phase 3 kickoff (if approved)
  - Attendees: [backend team]
  - Time: 60 minutes
  - Goal: Deep dive into Phase 3 guide, monitoring setup

**Deliverable**: Calendar invites sent

**Assigned To**: [Project manager]
**Time**: 30 minutes
**Status**: Not started

---

## Completion Checklist

### Before Phase 1 Can Start

All of the following must be marked DONE:

**Plan Verification**:
- [ ] Line numbers verified/updated in plan
- [ ] Current code patterns documented
- [ ] Original plan updated if needed

**Testing Infrastructure**:
- [ ] Frontend test template created
- [ ] Backend test template created
- [ ] Team trained on test patterns

**Architecture Design**:
- [ ] Auth flow documented
- [ ] AuthContext design approved
- [ ] Team has questions answered

**Build Verification**:
- [ ] Frontend build baseline recorded
- [ ] Frontend lint baseline recorded
- [ ] Frontend tests baseline recorded
- [ ] Backend checks baseline recorded

**Git Workflow**:
- [ ] VUW commit template established
- [ ] Rollback procedure documented
- [ ] Pre-commit checklist created

**Risk Mitigation**:
- [ ] Rollback runbook created
- [ ] Phase 3 monitoring plan defined
- [ ] Halt conditions documented

**Stakeholder Alignment**:
- [ ] Phase 3 approach approved by team
- [ ] Team meetings scheduled
- [ ] Timeline communicated

---

## Estimated Time Breakdown

| Task | Assigned To | Effort | Status |
|------|---|--------|--------|
| 1.1 Line verification | Frontend + Backend dev | 1h | Not started |
| 1.2 Code patterns | Frontend dev | 0.5h | Not started |
| 2.1 Frontend testing template | Frontend lead | 0.75h | Not started |
| 2.2 Backend testing template | Backend lead | 0.75h | Not started |
| 3.1 Auth flow documentation | Architect | 1h | Not started |
| 3.2 AuthContext design | Senior dev | 0.75h | Not started |
| 4.1 Build baseline | Devops | 0.75h | Not started |
| 4.2 Git workflow | Tech lead | 0.5h | Not started |
| 5.1 Rollback runbook | Release manager | 0.75h | Not started |
| 5.2 Phase 3 monitoring | Devops | 0.75h | Not started |
| 6.1 Stakeholder comms | PM | 0.5h | Not started |
| **TOTAL** | **Multiple** | **~7h** | **Not started** |

---

## Sign-Off

**Pre-Execution Setup Complete**: [  ] Yes [  ] No

**Date Completed**: _______________

**Completed By**: _______________

**Approved By**: _______________

---

## Notes

- Mark each task [  ] as completed
- If task blocked, document why in notes
- Don't start Phase 1 until all tasks marked done
- Update this document as work progresses
- Archive completed version before beginning Phase 1

---

## Questions During Pre-Execution

**Document all questions and decisions**:

1. Question: _______________
   Decision: _______________
   Owner: _______________

2. Question: _______________
   Decision: _______________
   Owner: _______________

[Continue as needed]

---

**This checklist ensures execution begins from a position of strength, not guesswork.**
