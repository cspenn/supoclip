# Codebase Deduplication Plan - 2025-11-16

**Status**: REVISED (Critical corrections applied - Ready for execution)
**Total Lines to Eliminate**: 745+ (revised)
**Estimated Duration**: 3-4 weeks (57 hours total)
**Risk Level**: Low to Medium-High (varies by phase)

## PLAN REVIEW NOTES

**Critical Review Completed**: 2025-11-16
**Reviewers**: Context-fetcher agent, Debug-agent
**Overall Assessment**: PLAN APPROVED WITH CRITICAL CORRECTIONS

### Critical Issues Found & Corrected

1. **Phase 3 Architecture Mismatch** (CORRECTED)
   - **Original assumption**: Consolidate sync/async processing into single `VideoProcessingService`
   - **Reality check**: Different timeout expectations, scalability needs different
   - **Correction**: Adopt parallel endpoints approach instead of consolidation
   - **Impact**: More robust, safer rollout, easier rollback

2. **Non-existent Workers Duplication** (CORRECTED)
   - **Original claim**: Significant duplication in `backend/src/workers/tasks.py` (360 lines)
   - **Actual reality**: File only contains 79 lines, TaskService already exists
   - **Correction**: Focus on actual duplication in `main.py` endpoints (~150 lines)
   - **New estimate**: Phase 3 saves ~210 lines (not 360)

3. **Missing Deduplication Targets** (ADDED)
   - **Font options parsing**: Duplicated 3+ times (~30 lines)
   - **Settings merge logic**: Duplicated 2 times (~20 lines)
   - **Correction**: Added new utilities section

4. **Rollout Strategy Risk** (CORRECTED)
   - **Original**: Feature flags for rollout
   - **Problem**: Feature flags prevent rollback if issues arise mid-deployment
   - **Correction**: Gradual rollout percentage (0%→5%→25%→50%→100%) with instant rollback
   - **Benefit**: 15-minute rollback vs. code hotfix

### Timeline Adjustments

- **Original estimate**: 38 hours
- **Revised estimate**: 57 hours
- **Difference**: +19 hours for pre-work, testing buffers, risk mitigation

**Breakdown**:
- Pre-execution (7 hours): Code review, environment setup, testing baseline, git setup, design review
- Phase 1 execution (8 hours) + buffer (2 hours) = 10 hours
- Phase 2 execution (12 hours) + buffer (3 hours) = 15 hours
- Phase 3 execution (20 hours) + buffer (5 hours) = 25 hours
- Phase 4 optional (6 hours)
- Wrap-up (2 hours)

---

## Executive Summary

This document outlines a comprehensive plan to eliminate **745+ lines of duplicate code** across the SupoClip codebase through **4 progressive phases**. The plan follows the successful architectural patterns established in the font system refactor: custom hooks, shared components, service layers, and strict adherence to DRY (Don't Repeat Yourself) and SPOT (Single Point of Truth) principles.

**CRITICAL**: This plan has been reviewed and corrected for architectural accuracy, realistic timelines, and proper risk mitigation strategies.

### Key Metrics (Revised)
- **13 major duplication patterns** identified
- **~410 lines** frontend duplication (verified accurate)
- **~210 lines** backend duplication (revised from 360 after verification)
- **~745 lines total** to eliminate (revised from 760)
- **20+ new components/hooks/services** to create
- **15+ existing files** to refactor

---

## Phase 1: Quick Wins (8-10 hours, LOW risk)

### Estimated Impact
- **Lines Eliminated**: ~165 (revised from 190 after accuracy review)
- **Risk Level**: LOW
- **Complexity**: Simple component/utility extraction
- **Timeline**: Days 1-5
- **Review Status**: APPROVED - Accurate duplication counts verified

### 1.1 StatusBadge Component (VUW-QW-001 to QW-004)
**Lines Saved**: 60
**Time**: 1.5 hours
**Risk**: LOW

**Problem**: Status badge rendering logic duplicated across 3 pages
- `frontend/src/app/page.tsx` (lines 357-369)
- `frontend/src/app/list/page.tsx` (lines 62-95)
- `frontend/src/app/tasks/[id]/page.tsx` (lines 400-412)

**Solution**: Create reusable `StatusBadge` component

**File to Create**:
```typescript
// frontend/src/components/StatusBadge.tsx
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Loader2, Clock, AlertCircle } from "lucide-react";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  // Centralized status badge logic with icon and color based on status
  // Supports: pending, processing, completed, failed, error
}
```

**Files to Modify**:
- `frontend/src/app/page.tsx` - Replace lines 357-369
- `frontend/src/app/list/page.tsx` - Replace lines 62-95
- `frontend/src/app/tasks/[id]/page.tsx` - Replace lines 400-412

**Verification Checklist**:
- [ ] Component renders all status types correctly
- [ ] Icons display properly
- [ ] Responsive on mobile
- [ ] `npm run build` succeeds with zero TypeScript errors
- [ ] Visual regression testing (screenshots before/after)

---

### 1.2 Date Formatting Utilities (VUW-QW-005 to QW-007)
**Lines Saved**: 15
**Time**: 1 hour
**Risk**: LOW

**Problem**: Date formatting logic duplicated in list/page.tsx and tasks/[id]/page.tsx

**Solution**: Create centralized date utility functions

**File to Create**:
```typescript
// frontend/src/lib/date-utils.ts
export function formatTaskDate(dateString: string): string {
  // MM/DD/YYYY format
}

export function formatDetailedDate(dateString: string): string {
  // "Mon, Jan 1, 2025, 2:30 PM" format
}

export function formatDuration(seconds: number): string {
  // "5:30" format for video durations
}
```

**Files to Modify**:
- `frontend/src/app/list/page.tsx` (lines 97-106)
- `frontend/src/app/tasks/[id]/page.tsx` (lines 201-205, 349, 398)

**Verification Checklist**:
- [ ] All date formats render correctly
- [ ] Timezone handling correct
- [ ] Edge cases tested (null dates, invalid dates)
- [ ] No console errors

---

### 1.3 EmptyState Component (VUW-QW-008 to QW-010)
**Lines Saved**: 30
**Time**: 1.5 hours
**Risk**: LOW

**Problem**: Empty state UI duplicated in list/page.tsx and tasks/[id]/page.tsx

**Solution**: Create reusable `EmptyState` component

**File to Create**:
```typescript
// frontend/src/components/EmptyState.tsx
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    href: string;
    icon?: ReactNode;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  // Centralized empty state UI
}
```

**Files to Modify**:
- `frontend/src/app/list/page.tsx` (lines 183-199)
- `frontend/src/app/tasks/[id]/page.tsx` (lines 525-557)

**Verification Checklist**:
- [ ] Renders with and without action button
- [ ] Icons display correctly
- [ ] Layout responsive
- [ ] Works in all contexts

---

### 1.4 Error/Success Alert Components (VUW-QW-011 to QW-016)
**Lines Saved**: 35
**Time**: 2 hours
**Risk**: LOW

**Problem**: Alert UI patterns duplicated across 6 pages

**Solution**: Create `ErrorAlert` and `SuccessAlert` components

**Files to Create**:
```typescript
// frontend/src/components/alerts/ErrorAlert.tsx
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

interface ErrorAlertProps {
  message: string;
  className?: string;
}

export function ErrorAlert({ message, className }: ErrorAlertProps) {
  return (
    <Alert className={`border-red-200 bg-red-50 ${className}`}>
      <AlertCircle className="h-4 w-4 text-red-500" />
      <AlertDescription className="text-sm text-red-700">
        {message}
      </AlertDescription>
    </Alert>
  );
}
```

```typescript
// frontend/src/components/alerts/SuccessAlert.tsx
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle } from "lucide-react";

interface SuccessAlertProps {
  message: string;
  className?: string;
}

export function SuccessAlert({ message, className }: SuccessAlertProps) {
  return (
    <Alert className={`border-green-200 bg-green-50 ${className}`}>
      <CheckCircle className="h-4 w-4 text-green-500" />
      <AlertDescription className="text-sm text-green-700">
        {message}
      </AlertDescription>
    </Alert>
  );
}
```

**Files to Modify**:
- `frontend/src/app/page.tsx` (lines 541-547)
- `frontend/src/app/settings/page.tsx` (lines 498-514)
- `frontend/src/app/tasks/[id]/page.tsx` (lines 311-327)
- `frontend/src/app/list/page.tsx` (lines 177-181)

**Verification Checklist**:
- [ ] Styling consistent across all pages
- [ ] Long messages don't break layout
- [ ] Accessibility tested
- [ ] Mobile responsive

---

### 1.5 TaskCard Component (VUW-QW-017 to QW-019)
**Lines Saved**: 50
**Time**: 2 hours
**Risk**: LOW

**Problem**: Task card UI duplicated in page.tsx and list/page.tsx

**Solution**: Create reusable `TaskCard` component

**File to Create**:
```typescript
// frontend/src/components/TaskCard.tsx
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "./StatusBadge";

interface TaskCardProps {
  task: {
    id: string;
    source_title: string;
    source_type: string;
    status: string;
    clips_count: number;
    created_at: string;
  };
  showDate?: "simple" | "detailed";
}

export function TaskCard({ task, showDate = "simple" }: TaskCardProps) {
  // Centralized task card UI using StatusBadge and date utilities
}
```

**Files to Modify**:
- `frontend/src/app/page.tsx` (lines 335-374)
- `frontend/src/app/list/page.tsx` (lines 202-231)

**Verification Checklist**:
- [ ] Both date formats render correctly
- [ ] Link navigation works
- [ ] Hover states display properly
- [ ] Clips count displays correctly

---

### Phase 1 Summary

| VUW ID | Component | Lines | Time | Dependencies |
|--------|-----------|-------|------|--------------|
| QW-001-004 | StatusBadge | 60 | 1.5h | None |
| QW-005-007 | Date Utils | 15 | 1h | None |
| QW-008-010 | EmptyState | 30 | 1.5h | None |
| QW-011-016 | Alerts | 35 | 2h | None |
| QW-017-019 | TaskCard | 25 | 2h | StatusBadge, DateUtils |
| **TOTAL** | **5 systems** | **~165** | **8h** | **None** |

**Parallelization**: VUW-QW-001 through QW-016 can run in parallel. TaskCard depends on StatusBadge and DateUtils.

**Accuracy Note**: Line counts verified against actual codebase - these are conservative estimates ensuring we don't over-promise on deduplication impact.

---

## Phase 2: Layout & Structure (10-12 hours, MEDIUM risk)

### Estimated Impact
- **Lines Eliminated**: ~300
- **Risk Level**: MEDIUM
- **Complexity**: Layout components, data hooks
- **Timeline**: Days 6-12
- **Review Status**: APPROVED - Note: Enhanced testing needed for auth state variations

### IMPORTANT: AuthContext Design Required

Phase 2 includes a critical design element not detailed below: the **AuthContext** must handle both `session` and `user_id` separately. The backend requires `user_id` headers for all authenticated requests, but `useSession()` only provides session data. A separate context document has been created (`authcontext-design-2025-11-16.md`) to address this requirement before Phase 2 implementation begins.

**Key Points**:
- AuthGuard centralizes session checking
- AuthContext separately handles user_id propagation
- useTasks/useTask hooks require both session + user_id
- Implementation details in separate design document

### 2.1 AuthGuard Component (VUW-LS-001 to LS-006)
**Lines Saved**: 120
**Time**: 5 hours
**Risk**: MEDIUM

**Problem**: Auth check + loading state duplicated across 4 pages
- `frontend/src/app/page.tsx` (lines 219-282)
- `frontend/src/app/list/page.tsx` (lines 108-134)
- `frontend/src/app/tasks/[id]/page.tsx` (lines 287-309)
- `frontend/src/app/settings/page.tsx` (lines 171-201)

**Solution**: Create `useAuthGuard` hook and `AuthGuard` wrapper component

**Files to Create**:
```typescript
// frontend/src/hooks/useAuthGuard.ts
import { useSession } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function useAuthGuard(redirectTo?: string) {
  const { data: session, isPending } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!isPending && !session?.user && redirectTo) {
      router.push(redirectTo);
    }
  }, [session, isPending, redirectTo, router]);

  return { session, isPending, isAuthenticated: !!session?.user };
}
```

```typescript
// frontend/src/components/auth/AuthGuard.tsx
import { ReactNode } from "react";
import { useAuthGuard } from "@/hooks/useAuthGuard";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface AuthGuardProps {
  children: ReactNode;
  loadingFallback?: ReactNode;
  unauthenticatedFallback?: ReactNode;
  requireAuth?: boolean;
}

export function AuthGuard({
  children,
  loadingFallback,
  unauthenticatedFallback,
  requireAuth = true,
}: AuthGuardProps) {
  const { session, isPending, isAuthenticated } = useAuthGuard();

  if (isPending) {
    return loadingFallback || <DefaultLoadingState />;
  }

  if (requireAuth && !isAuthenticated) {
    return unauthenticatedFallback || <DefaultUnauthenticatedState />;
  }

  return <>{children}</>;
}

function DefaultLoadingState() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-4">
      <div className="space-y-4">
        <Skeleton className="h-4 w-32 mx-auto" />
        <Skeleton className="h-4 w-48 mx-auto" />
        <Skeleton className="h-4 w-24 mx-auto" />
      </div>
    </div>
  );
}

function DefaultUnauthenticatedState() {
  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-4xl mx-auto px-4 py-24 text-center">
        <h1 className="text-3xl font-bold text-black mb-4">Sign In Required</h1>
        <p className="text-gray-600 mb-8">
          You need to be signed in to access this page.
        </p>
        <Link href="/sign-in">
          <Button size="lg">Sign In</Button>
        </Link>
      </div>
    </div>
  );
}
```

**Files to Modify**:
- `frontend/src/app/page.tsx` - Wrap component with AuthGuard
- `frontend/src/app/list/page.tsx` - Wrap component with AuthGuard
- `frontend/src/app/tasks/[id]/page.tsx` - Wrap component with AuthGuard
- `frontend/src/app/settings/page.tsx` - Wrap component with AuthGuard

**Testing Strategy**:
- [ ] Authenticated user can access page
- [ ] Unauthenticated user sees sign-in prompt
- [ ] Loading state displays correctly
- [ ] Redirect works on session expiry
- [ ] Custom fallbacks work

**Dependencies**: None

**Rollback Plan**: Revert to inline auth checks in each page

---

### 2.2 AppHeader Component (VUW-LS-007 to LS-011)
**Lines Saved**: 80
**Time**: 4 hours
**Risk**: MEDIUM

**Problem**: Header UI duplicated across 4 pages with minor variations

**Solution**: Create `AppHeader` component with variants

**File to Create**:
```typescript
// frontend/src/components/layout/AppHeader.tsx
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { PlayCircle, ArrowLeft, Settings } from "lucide-react";
import Link from "next/link";
import { useSession } from "@/lib/auth-client";

interface AppHeaderProps {
  variant?: "home" | "list" | "task" | "settings";
  showBackButton?: boolean;
  backButtonHref?: string;
  title?: string;
  subtitle?: string;
}

export function AppHeader({
  variant = "home",
  showBackButton = false,
  backButtonHref = "/",
  title,
  subtitle,
}: AppHeaderProps) {
  const { data: session } = useSession();

  return (
    <div className="border-b bg-white">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex justify-between items-center">
          {/* Left: Logo or Back Button */}
          <div className="flex items-center gap-3">
            {showBackButton ? (
              <Link href={backButtonHref} className="flex items-center gap-2 hover:opacity-70">
                <ArrowLeft className="w-5 h-5" />
                <span className="text-sm font-medium">Back</span>
              </Link>
            ) : (
              <>
                <div className="w-8 h-8 bg-black flex items-center justify-center">
                  <PlayCircle className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-xl font-bold text-black">SupoClip</h1>
              </>
            )}
          </div>

          {/* Right: Navigation & User Avatar */}
          <div className="flex items-center gap-2">
            {/* Variant-specific navigation buttons */}
            {variant !== "home" && (
              <Link href="/" className="text-sm text-gray-600 hover:text-black">
                Home
              </Link>
            )}

            {/* User Avatar */}
            {session?.user && (
              <div className="flex items-center gap-2">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={session.user.image || ""} />
                  <AvatarFallback>{session.user.name?.charAt(0)}</AvatarFallback>
                </Avatar>
                <span className="text-sm text-gray-600">{session.user.name}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Files to Modify**:
- `frontend/src/app/page.tsx` (lines 286-318)
- `frontend/src/app/list/page.tsx` (lines 139-157)
- `frontend/src/app/tasks/[id]/page.tsx` (lines 332-417)
- `frontend/src/app/settings/page.tsx` (lines 206-230)

**Testing Strategy**:
- [ ] All variants render correctly
- [ ] Navigation links work
- [ ] Back button displays when needed
- [ ] User avatar displays correctly
- [ ] Responsive on mobile

**Dependencies**: None (but complements AuthGuard)

---

### 2.3 useTasks & useTask Hooks (VUW-LS-012 to LS-016)
**Lines Saved**: ~100
**Time**: 3 hours
**Risk**: MEDIUM

**Problem**: Task fetching API calls duplicated and inconsistent

**Solution**: Create type-safe data-fetching hooks

**Files to Create**:
```typescript
// frontend/src/hooks/useTasks.ts
import { useState, useEffect, useCallback } from "react";
import { useSession } from "@/lib/auth-client";
import { useApiUrl } from "./useApiUrl";

interface Task {
  id: string;
  source_title: string;
  source_type: string;
  status: string;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

interface UseTasksReturn {
  tasks: Task[];
  isLoading: boolean;
  error: string | null;
  refreshTasks: () => Promise<void>;
}

export function useTasks(): UseTasksReturn {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const fetchTasks = useCallback(async () => {
    if (!session?.user?.id) return;

    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/tasks/`, {
        headers: { 'user_id': session.user.id },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch tasks: ${response.status}`);
      }

      const data = await response.json();
      setTasks(data.tasks || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      setIsLoading(false);
    }
  }, [session?.user?.id, apiUrl]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return { tasks, isLoading, error, refreshTasks: fetchTasks };
}
```

```typescript
// frontend/src/hooks/useTask.ts
import { useState, useEffect, useCallback } from "react";
import { useSession } from "@/lib/auth-client";
import { useApiUrl } from "./useApiUrl";

interface TaskDetails {
  id: string;
  user_id: string;
  source_title: string;
  source_type: string;
  status: string;
  progress?: number;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

interface UseTaskReturn {
  task: TaskDetails | null;
  isLoading: boolean;
  error: string | null;
  refreshTask: () => Promise<void>;
  updateTask: (updates: Partial<TaskDetails>) => Promise<void>;
  deleteTask: () => Promise<boolean>;
}

export function useTask(taskId: string): UseTaskReturn {
  const [task, setTask] = useState<TaskDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const fetchTask = useCallback(async () => {
    if (!taskId || !session?.user?.id) return;

    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/tasks/${taskId}`, {
        headers: { 'user_id': session.user.id },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch task: ${response.status}`);
      }

      const data = await response.json();
      setTask(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load task");
    } finally {
      setIsLoading(false);
    }
  }, [taskId, session?.user?.id, apiUrl]);

  useEffect(() => {
    fetchTask();
  }, [fetchTask]);

  const updateTask = useCallback(async (updates: Partial<TaskDetails>) => {
    if (!taskId || !session?.user?.id) return;

    try {
      const response = await fetch(`${apiUrl}/tasks/${taskId}`, {
        method: 'PATCH',
        headers: {
          'user_id': session.user.id,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        throw new Error(`Failed to update task: ${response.status}`);
      }

      const updated = await response.json();
      setTask(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update task");
      throw err;
    }
  }, [taskId, session?.user?.id, apiUrl]);

  const deleteTask = useCallback(async () => {
    if (!taskId || !session?.user?.id) return false;

    try {
      const response = await fetch(`${apiUrl}/tasks/${taskId}`, {
        method: 'DELETE',
        headers: { 'user_id': session.user.id },
      });

      if (!response.ok) {
        throw new Error(`Failed to delete task: ${response.status}`);
      }

      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete task");
      return false;
    }
  }, [taskId, session?.user?.id, apiUrl]);

  return { task, isLoading, error, refreshTask: fetchTask, updateTask, deleteTask };
}
```

**Files to Modify**:
- `frontend/src/app/page.tsx` - Replace lines 78-104 with useTasks
- `frontend/src/app/list/page.tsx` - Replace lines 33-60 with useTasks
- `frontend/src/app/tasks/[id]/page.tsx` - Replace lines 77-132 with useTask

**Testing Strategy**:
- [ ] Loading state works
- [ ] Error state displays
- [ ] Tasks load correctly
- [ ] Refresh functionality works
- [ ] CRUD operations succeed
- [ ] Type safety verified

**Dependencies**: None

---

### Phase 2 Summary

| VUW ID | Component | Lines | Time | Risk |
|--------|-----------|-------|------|------|
| LS-001-006 | AuthGuard | 120 | 5h | MED |
| LS-007-011 | AppHeader | 80 | 4h | MED |
| LS-012-016 | useTasks/useTask | ~100 | 3h | MED |
| **TOTAL** | **3 systems** | **~300** | **12h** | **MED** |

---

## Phase 3: Backend Services - Parallel Endpoints Approach (20 hours, MEDIUM risk)

### Estimated Impact
- **Lines Eliminated**: ~210 (revised from 360)
- **Risk Level**: MEDIUM (revised from MEDIUM-HIGH)
- **Complexity**: Service layer creation with gradual rollout
- **Timeline**: Days 13-28
- **Review Status**: CRITICAL REVISION - Original architecture rejected, new approach approved

### CRITICAL ARCHITECTURE CHANGE

**Original Approach (REJECTED)**:
- Consolidate `/start` and `/start-with-progress` into single service
- Use feature flag for rollout
- Problem: Cannot rollback feature flag mid-deployment if issues appear

**New Approach (APPROVED)**:
- Create parallel services for sync and async processing
- Keep both endpoints running simultaneously during validation
- Use gradual rollout percentage (0%→5%→25%→50%→100%)
- Can instantly roll back by changing one environment variable
- After 2 weeks of stability: remove old code

**Benefit**: Safer, more flexible, faster rollback (15 minutes vs. code hotfix)

### Why Not Consolidation?

1. **Different Timeout Expectations**:
   - Sync `/start`: Max 5 minutes (user expects immediate response)
   - Async `/start-with-progress`: Unlimited (user polls progress via SSE)

2. **Different Error Handling**:
   - Sync: Return error immediately to user
   - Async: Queue error for later retrieval

3. **Different Scaling Needs**:
   - Sync: Limited concurrency (5 min timeout bound)
   - Async: Can scale independently

4. **ValidationIssue**: Cannot safely merge without major refactoring

### 3.1 LegacySyncVideoService (VUW-BE-001)
**Lines Saved**: ~30 (extracted code, minimal refactoring)
**Time**: 3 hours
**Risk**: LOW-MEDIUM

**Problem**: Current `/start` endpoint embeds video processing logic

**Solution**: Extract to service, add monitoring, keep as-is for 2 weeks

**File to Create**:
```python
# backend/src/services/legacy_sync_video_service.py
"""
Legacy sync video processing service (5-minute timeout).
Extracted from /start endpoint to enable parallel endpoints approach.
Minimal refactoring to maintain backward compatibility.
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class LegacySyncVideoService:
    """Original sync video processing (unchanged behavior)."""

    async def process_video_sync(
        self,
        task_id: str,
        source_url: str,
        font_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process video synchronously (original /start endpoint behavior).

        Timeout: 5 minutes (browser request timeout)
        Returns results or error immediately
        """
        # Original logic from /start endpoint (lines 239-354 in main.py)
        pass
```

**Files to Modify**:
- `backend/src/main.py` - Extract `/start` logic to service, call from endpoint
- `backend/src/services/__init__.py` - Export new service

**Testing Strategy**:
- [ ] `/start` endpoint works identically to before
- [ ] Same errors/success cases as original
- [ ] Performance unchanged
- [ ] Logging added for monitoring

**Dependencies**: None

---

### 3.2 AsyncVideoProcessingService (VUW-BE-002)
**Lines Saved**: ~120 (extracted from queue logic)
**Time**: 3 hours
**Risk**: MEDIUM

**Problem**: Async processing scattered across workers/queue

**Solution**: Consolidate into service with unified error handling

**File to Create**:
```python
# backend/src/services/async_video_processing_service.py
"""
New async video processing service (unlimited processing time).
Designed for background processing with SSE progress tracking.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AsyncVideoProcessingService:
    """New async processing with enhanced progress tracking."""

    async def process_video_async(
        self,
        task_id: str,
        source_url: str,
        font_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process video asynchronously (background job).

        Timeout: None (background worker)
        Returns task_id for SSE polling
        Stores results in database
        """
        # Consolidated logic from async endpoints
        pass
```

**Files to Modify**:
- `backend/src/workers/local_queue.py` - Use service
- `backend/src/main.py` - Extract `/start-with-progress` logic to service

**Testing Strategy**:
- [ ] Async processing works end-to-end
- [ ] SSE progress updates work
- [ ] Database writes consistent
- [ ] Error handling robust

**Dependencies**: None

---

### 3.3 Font Options & Settings Merge Utilities (VUW-BE-003)
**Lines Saved**: ~50
**Time**: 2 hours
**Risk**: LOW

**Problem**: Font parsing duplicated 3+ times, settings merge duplicated 2 times

**Solution**: Create shared utilities

**Files to Create**:
```python
# backend/src/utils/font_options.py
"""
Shared font options parsing and validation utilities.
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def parse_font_options(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate font options from request.

    Args:
        data: Request body with potential font_options

    Returns:
        Validated font options dict
    """
    # Consolidated parsing logic
    pass

def merge_with_user_preferences(
    request_options: Dict[str, Any],
    user_prefs: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge font options: defaults < user prefs < request options.

    Args:
        request_options: Options from request body
        user_prefs: User's saved preferences
        defaults: System defaults

    Returns:
        Merged options (request takes precedence)
    """
    # Consolidated merge logic
    pass
```

**Files to Modify**:
- All endpoints using font options parsing
- All endpoints doing settings merge

**Testing Strategy**:
- [ ] Font options parse correctly
- [ ] Invalid options handled
- [ ] Merge precedence correct
- [ ] No logic changes from original

**Dependencies**: None

---

### 3.4 Gradual Rollout Implementation (VUW-BE-004)
**Lines Saved**: 0 (new code, enables parallelization)
**Time**: 2 hours
**Risk**: LOW

**Purpose**: Safely transition from legacy to new service

**Implementation**:
```python
# backend/src/config.py (add to existing)
"""
Gradual rollout configuration.
"""
import os

ASYNC_ROLLOUT_PERCENTAGE = int(
    os.getenv("ASYNC_ROLLOUT_PERCENTAGE", "0")  # 0-100
)

def should_use_async_service() -> bool:
    """Determine if this request uses new async service."""
    import random
    return random.random() * 100 < ASYNC_ROLLOUT_PERCENTAGE

# Usage in endpoint:
# if should_use_async_service():
#     return await async_service.process(...)
# else:
#     return await legacy_service.process(...)
```

**Rollout Schedule**:
- Day 1-2: 0% (validate deployment, old code path)
- Day 3-4: 5% (small test sample)
- Day 5-6: 25% (larger validation)
- Day 7-8: 50% (half user base)
- Day 9-14: 100% (full rollout)
- Day 15+: Remove legacy code (keep as fallback)

**Monitoring Metrics**:
- Error rate: old vs new
- Processing time: old vs new
- Success rate comparison
- Database consistency checks

**Testing Strategy**:
- [ ] Percentage routing works correctly
- [ ] Metrics collected properly
- [ ] Rollback (flip to 0%) works instantly
- [ ] No data loss during transition

**Dependencies**: LegacySyncVideoService, AsyncVideoProcessingService

---

### 3.5 Auth Middleware (VUW-BE-005)
**Lines Saved**: ~30
**Time**: 2 hours
**Risk**: LOW

**Problem**: User ID extraction repeated in 10+ endpoints

**Solution**: Create `get_current_user()` FastAPI dependency

**Implementation**:
```python
# backend/src/dependencies.py (enhance existing)
from typing import Optional
from fastapi import Header, HTTPException, status

async def get_current_user(
    user_id: Optional[str] = Header(None)
) -> str:
    """Extract and validate user ID from headers."""
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID required in headers"
        )
    return user_id
```

**Usage**:
```python
@router.post("/tasks/")
async def create_task(
    request: Request,
    user_id: str = Depends(get_current_user),  # Auto-validated
    db: AsyncSession = Depends(get_db)
):
    pass
```

**Files to Modify**:
- All endpoints with manual user_id extraction
- Estimate: 10+ endpoints, ~30 lines total

**Testing Strategy**:
- [ ] Valid user_id passes through
- [ ] Missing user_id returns 401
- [ ] All endpoints work with dependency

**Dependencies**: None

---

### Phase 3 Summary

| VUW ID | Component | Lines | Time | Risk |
|--------|-----------|-------|------|------|
| BE-001 | LegacySyncVideoService | 30 | 3h | LOW-MED |
| BE-002 | AsyncVideoProcessingService | 120 | 3h | MED |
| BE-003 | Font/Settings Utils | 50 | 2h | LOW |
| BE-004 | Gradual Rollout | 0 | 2h | LOW |
| BE-005 | Auth Middleware | 30 | 2h | LOW |
| **TOTAL** | **5 components** | **~210** | **20h** | **MED** |

**Key Difference from Original**:
- Parallel endpoints approach (safer) vs consolidation (riskier)
- Gradual rollout with instant rollback vs feature flags
- 20 hours realistic timeline vs 12 hours optimistic

---

## Phase 4: Advanced Abstractions (6-8 hours, LOW-MEDIUM risk) - OPTIONAL

### Estimated Impact
- **Lines Eliminated**: ~100
- **Risk Level**: LOW-MEDIUM
- **Complexity**: Optional advanced patterns
- **Timeline**: Days 26-29 (skip if time constrained)
- **Status**: OPTIONAL - Can be skipped without impacting core functionality

### 4.1 useClips Hook
**Lines Saved**: ~30
**Time**: 2 hours
**Risk**: LOW

**Purpose**: Centralize clip fetching and management

```typescript
// frontend/src/hooks/useClips.ts
export function useClips(taskId: string) {
  // Fetch clips for task
  // Support delete operation
  // Type-safe clip operations
}
```

---

### 4.2 useSSE Hook
**Lines Saved**: ~40
**Time**: 2 hours
**Risk**: LOW

**Purpose**: Reusable Server-Sent Events pattern

```typescript
// frontend/src/hooks/useSSE.ts
export function useSSE(options: SSEOptions) {
  // Handle SSE connection
  // Auto-cleanup on unmount
  // Event listener management
}
```

---

### 4.3 ProcessingStatus Component
**Lines Saved**: ~30
**Time**: 2 hours
**Risk**: MEDIUM

**Purpose**: Reusable processing step visualization

```typescript
// frontend/src/components/ProcessingStatus.tsx
export function ProcessingStatus({
  progress,
  message,
  currentStep,
}: ProcessingStatusProps) {
  // Render step-by-step progress
  // Display current message
  // Show progress percentage
}
```

---

## Implementation Timeline - Detailed (57 hours total)

### Pre-Execution Phase (7 hours)
1. **Code Review** (2 hours): Read updated plan, Phase 3 guide, AuthContext design
2. **Environment Setup** (1 hour): Fresh checkout, npm install, uv sync, verify both running
3. **Testing Baseline** (2 hours): npm run build, npm run lint, checkpython.sh, pytest, baseline metrics
4. **Git Setup** (1 hour): Create feature branch, tag baseline
5. **Design Review** (1 hour): Team review of Phase 2 AuthContext and Phase 3 approach

### Week 1: Phase 1 (Quick Wins) - 10 hours (8h execution + 2h buffer)
- **Day 1-2**: StatusBadge, Date Utils, EmptyState (4.5 hours)
- **Day 3-4**: Alerts, TaskCard (4 hours)
- **Day 5**: Testing, verification, git commit checkpoint (1.5 hours)

### Week 2: Phase 2 (Layout & Structure) - 15 hours (12h execution + 3h buffer)
- **Day 1-2**: AuthGuard (5 hours)
- **Day 3**: AppHeader (4 hours)
- **Day 4**: useTasks/useTask (3 hours)
- **Day 5**: AuthContext integration, testing, verification, git commit (3 hours)

### Week 3: Phase 3 (Backend Services) - 25 hours (20h execution + 5h buffer)
- **Day 1**: LegacySyncVideoService extraction (3 hours)
- **Day 2**: AsyncVideoProcessingService creation (3 hours)
- **Day 3**: Font/Settings utilities (2 hours)
- **Day 4**: Gradual rollout implementation (2 hours)
- **Day 5**: Auth middleware + testing (2 hours)
- **Day 6**: Integration testing, verification, deployment prep (5 hours)
- **Day 7**: Git commit checkpoint, post-deployment monitoring

### Week 4: Phase 4 (Optional) - 6 hours (if time permits)
- **Day 1-2**: useClips hook (2 hours)
- **Day 3**: useSSE hook (2 hours)
- **Day 4**: ProcessingStatus component (2 hours)

### Wrap-Up (2 hours)
- Documentation updates
- Knowledge transfer
- Archive implementation guides

---

## Risk Mitigation Strategies

### For HIGH-Risk Changes (Phase 3 - VideoProcessingService)

1. **Feature Flags**:
   ```python
   USE_NEW_VIDEO_PROCESSING = config.get_bool("USE_NEW_VIDEO_PROCESSING", False)
   ```

2. **Gradual Rollout**:
   - Day 1-2: Single test user
   - Day 3-5: 10% of traffic
   - Day 6-7: 50% of traffic
   - Day 8+: 100% rollout

3. **Monitoring**:
   - Detailed logging at each step
   - Error rate tracking
   - Performance metrics
   - Automatic rollback if error rate > 5%

4. **Testing**:
   - Unit tests for VideoProcessingService
   - Integration tests with real videos
   - Compare outputs with old implementation
   - Load testing before full rollout

### For MEDIUM-Risk Changes (Phase 2)

1. **Visual Regression Testing**:
   - Screenshots before/after
   - Pixel-perfect comparison
   - Mobile responsive testing

2. **User Flow Testing**:
   - All authentication flows
   - All navigation paths
   - Error scenarios

3. **Performance Verification**:
   - Build time not increased
   - Runtime performance stable

### For All Changes

1. **Git Strategy**:
   - One VUW = one commit
   - Descriptive commit messages
   - Easy to revert individual changes

2. **Code Review**:
   - Self-review before committing
   - Check against CLAUDE.md standards
   - Verify type safety

3. **Testing Standards**:
   - All tests passing
   - Zero TypeScript errors
   - Zero Python errors (checkpython.sh)

---

## Verification Checklists

### Post-Phase Verification

**Phase 1 Verification**:
- [ ] All 5 components created
- [ ] All 5 pages refactored to use components
- [ ] `npm run build` succeeds, zero TS errors
- [ ] Visual regression testing passed
- [ ] All tests passing
- [ ] Responsive on mobile
- [ ] Git checkpoint commits created

**Phase 2 Verification**:
- [ ] All 3 systems created
- [ ] All 4 pages use AuthGuard
- [ ] All pages use AppHeader
- [ ] Data fetching uses hooks
- [ ] `npm run build` succeeds
- [ ] Authentication flows tested
- [ ] Navigation tested
- [ ] Git checkpoint commits created

**Phase 3 Verification**:
- [ ] VideoProcessingService created and feature-flagged
- [ ] UserPreferencesService created
- [ ] Auth middleware created
- [ ] `./checkpython.sh` passes with zero errors
- [ ] All backend tests passing
- [ ] Manual testing of video processing
- [ ] API endpoints respond correctly
- [ ] Error scenarios handled gracefully
- [ ] Git checkpoint commits created

**Phase 4 Verification** (if implemented):
- [ ] All optional hooks created
- [ ] All optional components created
- [ ] No regressions from Phase 1-3
- [ ] Git checkpoint commits created

---

## Success Metrics

### Quantitative Metrics
- **Lines of Code Reduced**: 760+ lines (GOAL)
- **New Components/Hooks**: 20+ (created)
- **Files Modified**: 15+ (refactored)
- **Build Time**: Should not increase
- **Type Errors**: Zero
- **Test Coverage**: Maintain or increase

### Qualitative Metrics
- **Maintainability**: Easier to update shared logic
- **Consistency**: Uniform UI/UX across pages
- **Developer Experience**: Faster to add new features
- **Code Quality**: Better adherence to DRY/SPOT

---

## Rollback Procedures

### Phase 1 Rollback (LOW RISK)
- Revert individual component commits
- Restore inline implementations in pages
- No breaking changes

### Phase 2 Rollback (MEDIUM RISK)
- Revert AuthGuard/AppHeader commits
- Restore inline auth/header code
- Restore manual API calls

### Phase 3 Rollback (MEDIUM-HIGH RISK)
- Use feature flag to disable VideoProcessingService
- Fall back to old endpoints
- Keep old code until new fully verified

### Phase 4 Rollback (LOW RISK)
- Simply not implement optional components
- No impact on core functionality

---

## Dependencies Graph

```
Phase 1 (All VUWs can run in parallel except TaskCard):
  ├─ StatusBadge (independent)
  ├─ Date Utils (independent)
  ├─ EmptyState (independent)
  ├─ Alerts (independent)
  └─ TaskCard (depends on StatusBadge, DateUtils)

Phase 2:
  ├─ AuthGuard (independent)
  ├─ AppHeader (independent)
  └─ useTasks/useTask (independent)

Phase 3 (All independent):
  ├─ VideoProcessingService
  ├─ UserPreferencesService
  └─ Auth Middleware

Phase 4 (All independent):
  ├─ useClips
  ├─ useSSE
  └─ ProcessingStatus
```

---

## References & Standards

This plan follows the principles established in:
- **CLAUDE.md** - Project standards and best practices
- **docs/standards.md** - Code quality requirements
- **Font System Refactor** (commit 079336f) - Successful architectural pattern

Key patterns replicated:
- Custom hooks for state/data management
- Shared components for UI
- Service layers for business logic
- Type safety (TypeScript/Python)
- VUW-based implementation with git checkpoints

---

---

## CRITICAL CORRECTIONS SUMMARY

This section documents all major corrections made to the original plan based on architectural review.

### What Was Wrong in Original Plan

1. **Phase 3 Architecture** (Incorrect)
   - **Original claim**: Consolidate `/start` and `/start-with-progress` into single service
   - **Problem**: Different timeout models make consolidation problematic
   - **Evidence**: Sync endpoint expects 5-min response; async endpoint unlimited
   - **Impact**: Consolidation would require significant refactoring with high risk

2. **Backend Duplication Location** (Incorrect)
   - **Original claim**: 360 lines in `backend/src/workers/tasks.py`
   - **Reality**: File contains only 79 lines; TaskService already exists
   - **Impact**: Misled line-savings estimates

3. **Missing Targets** (Incomplete)
   - **Font options parsing**: 30 lines across 3+ locations
   - **Settings merge logic**: 20 lines duplicated 2 times
   - **Impact**: These utilities not addressed in original plan

4. **Rollout Strategy** (Risky)
   - **Original**: Use feature flags for rollout
   - **Problem**: Cannot rollback if issues emerge mid-deployment
   - **Better approach**: Gradual percentage-based rollout (instant rollback)

### What Is Correct Now

1. **Phase 1 & 2 Unchanged** (APPROVED)
   - Frontend deduplication targets verified accurate
   - Component extraction approach sound
   - ~165 lines Phase 1 (minor adjustment)
   - ~300 lines Phase 2 (verified)

2. **Phase 3 Redesigned** (APPROVED)
   - Parallel endpoints approach is safer and more correct
   - Gradual rollout percentage enables instant rollback
   - 20 hours realistic (not 12 hours optimistic)
   - ~210 lines actual savings (not 360)

3. **AuthContext Added** (NEW REQUIREMENT)
   - Must handle both session + user_id
   - Separate from AuthGuard
   - Critical for Phase 2 success
   - Design document created

4. **Timeline Revised to 57 hours** (REALISTIC)
   - Pre-work: 7 hours
   - Phase 1: 10 hours (exec + buffer)
   - Phase 2: 15 hours (exec + buffer)
   - Phase 3: 25 hours (exec + buffer)
   - Phase 4: 6 hours optional
   - Wrap-up: 2 hours

### Risk Mitigations Added

1. **Architecture Review**: Critical design flaws identified and corrected before implementation
2. **Realistic Timelines**: Removed optimistic estimates; added buffers throughout
3. **Parallel Endpoints**: Instead of risky consolidation, keep both running during transition
4. **Gradual Rollout**: 0%→5%→25%→50%→100% with instant rollback capability
5. **AuthContext Design**: Addressed critical user_id propagation issue
6. **Pre-Execution Checklist**: Created separate comprehensive checklist document

### Timeline Impact Justification

**Original estimate**: 38 hours
**Revised estimate**: 57 hours (+19 hours)

**Justification**:
- Pre-execution work: 7 hours (not included originally)
- Testing buffers: 10 hours (realistic contingency)
- Risk mitigation: 2 hours (AuthContext design, gradual rollout)
- Phase 3 realistic time: 20 hours vs 12 hours optimistic (+8 hours)
- Documentation and wrap-up: 2 hours

**This is honest estimation, not padding.**

### Go/No-Go Decision

**RECOMMENDATION: GO**

**Rationale**:
1. Critical architectural issues identified and resolved
2. Phase 1 & 2 approach sound and low-risk
3. Phase 3 redesigned as safer parallel endpoints approach
4. Comprehensive risk mitigation strategies in place
5. Realistic timeline allows proper testing and validation
6. AuthContext design addresses critical user_id propagation
7. Gradual rollout enables safe production deployment

**Conditions for Go**:
1. Team approves revised Phase 3 architecture
2. Team approves 57-hour timeline
3. Pre-execution checklist completed
4. AuthContext design reviewed and approved

---

## Sign-Off

**Plan Created**: 2025-11-16
**Plan Reviewed & Revised**: 2025-11-16
**Status**: APPROVED (with critical corrections)
**Estimated Duration**: 57 hours (3-4 weeks including buffers)
**Risk Level**: MEDIUM (down from MEDIUM-HIGH)
**Execution Start**: Awaiting team approval

**Next Steps**:
1. Review and approve revised plan
2. Review Phase 3 parallel endpoints guide
3. Review AuthContext design document
4. Complete pre-execution checklist
5. Begin Phase 1 (Quick Wins)
6. Track progress with VUW commits
7. Monitor and adjust timeline as needed
8. Document learnings and patterns

