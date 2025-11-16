---
title: "AuthContext Design Document"
date: 2025-11-16
status: "APPROVED"
author: "Design Review Team"
category: "Frontend Architecture"
---

# AuthContext Design Document: Unified Authentication State Management

**Purpose**: Design and implement AuthContext to provide both `session` data and `user_id` to all child components, enabling reliable authentication across the application.

**Status**: APPROVED - Ready for team review and implementation

---

## Problem Statement

### The Core Issue

In Phase 2 implementation, we're introducing AuthGuard to centralize authentication checks. However, **AuthGuard alone is insufficient** because:

1. **Missing user_id**: `useSession()` provides session object, but backend requires `user_id` header for all authenticated requests
2. **Prop Drilling**: Without context, every hook/component needs `user_id` passed as prop (anti-pattern)
3. **Decoupled from Session**: useTasks hooks fail because they don't receive user_id
4. **Cascading Failures**: If any page forgets to pass user_id, all authenticated API calls fail silently

### Manifestation in Code

Current code pattern (broken):

```typescript
// frontend/src/app/page.tsx
export default function HomePage() {
  const { data: session } = useSession();  // ✓ Get session

  // ❌ Problem: useTasks doesn't have access to session.user.id
  const { tasks } = useTasks();  // Fails silently - no user_id in header

  return (
    <>
      {/* Page code */}
    </>
  );
}

// frontend/src/hooks/useTasks.ts
export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const { data: session } = useSession();  // ✓ Get session here

  useEffect(() => {
    if (!session?.user?.id) return;  // ❌ Not guaranteed to have session

    const userId = session.user.id;

    fetch(`${apiUrl}/tasks/`, {
      headers: { 'user_id': userId },  // ✓ Header set
    });
  }, [session?.user?.id]);

  return { tasks, isLoading, error };
}
```

**Why this is fragile**:
- AuthGuard ensures `session` exists before rendering
- But useTasks calls `useSession()` again - redundant and risks race conditions
- If AuthGuard and useTasks timing differs, user_id might be undefined
- Hard to debug: API silently fails with 401 but no error message shown

### Why Context is Needed

React Context solves this by:
1. **Centralizing state**: One source of truth for session + user_id
2. **Avoiding race conditions**: All children read same data simultaneously
3. **Type safety**: TypeScript ensures user_id is non-null when available
4. **Eliminating prop drilling**: No need to pass user_id through 5 component levels
5. **Easy debugging**: Can inspect context value at any level

---

## Current Architecture Gap

### What Exists Now

```
Better Auth (server)
    |
    v
useSession() hook (client)
    |
    +-> { data: session, isPending, ... }
    |
    +-> session = { user: { id, email, name, ... }, expiresAt, ... }
```

**What's working**:
- Session fetching is solid
- user.id is available in session object

**What's missing**:
- No unified way to pass user_id to components that need it
- Each component calls useSession independently
- No guarantee that authenticated components have both session AND user_id

### Why Not Just Use useSession Everywhere?

You could, but it's problematic:
1. **Performance**: Every component calling useSession causes API lookups
2. **Race conditions**: Multiple calls might race, returning different states
3. **Not DRY**: Repeating session/user_id extraction in every hook
4. **Hard to optimize**: Cannot cache or memoize shared state

**AuthContext solves all these problems.**

---

## Proposed AuthContext Design

### Architecture Overview

```
RootLayout
    |
    v
<AuthProvider>  (uses useSession internally, caches result)
    |
    v
AuthContext (provides { session, user_id, isLoading })
    |
    +-> Page A: Has access to session + user_id
    |
    +-> Page B: Has access to session + user_id
    |
    +-> useTasks hook: Can read user_id from context (no prop needed)
    |
    +-> AppHeader: Can read user name from session (no prop needed)
```

### Context Definition

```typescript
// frontend/src/context/AuthContext.tsx

import { createContext, useContext, ReactNode } from "react";

/**
 * Session object from Better Auth.
 *
 * Properties:
 * - user: { id, email, name, image, ... }
 * - expiresAt: Number (timestamp)
 * - createdAt: String (ISO date)
 */
interface Session {
  user: {
    id: string;
    email: string;
    name: string;
    image?: string;
    emailVerified?: boolean;
  };
  expiresAt: number;
  createdAt: string;
}

/**
 * AuthContext value provided to all children.
 *
 * Provides both session data (from useSession) and derived user_id.
 * Guaranteed to have user_id when isAuthenticated is true.
 */
interface AuthContextType {
  session: Session | null;
  user_id: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

/**
 * Create context with undefined default (will be provided by AuthProvider).
 * Using undefined helps catch missing <AuthProvider> wrapper.
 */
export const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * useAuth hook to access auth context.
 *
 * Usage:
 *   const { session, user_id, isLoading } = useAuth();
 *
 * Throws error if used outside <AuthProvider>.
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }

  return context;
}
```

### AuthProvider Component

```typescript
// frontend/src/components/auth/AuthProvider.tsx

import { ReactNode } from "react";
import { useSession } from "@/lib/auth-client";
import { AuthContext } from "@/context/AuthContext";

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * AuthProvider wraps application and provides auth context to all children.
 *
 * Internally uses useSession() to fetch session data.
 * Caches and provides both session + user_id to entire app tree.
 *
 * Usage:
 *   <AuthProvider>
 *     <YourApp />
 *   </AuthProvider>
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const { data: session, isPending } = useSession();

  // Extract user_id from session (guaranteed non-null if session exists)
  const user_id = session?.user?.id || null;

  // Determine authentication status
  const isAuthenticated = !!session?.user;

  const contextValue = {
    session: session || null,
    user_id,
    isLoading: isPending,
    isAuthenticated,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}
```

### Integration in Root Layout

```typescript
// frontend/src/app/layout.tsx

import { AuthProvider } from "@/components/auth/AuthProvider";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {/* AuthProvider must be at root to provide auth to entire app */}
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
```

---

## Implementation Details

### Updated AuthGuard Component

AuthGuard uses useAuth instead of useSession:

```typescript
// frontend/src/components/auth/AuthGuard.tsx

import { ReactNode } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface AuthGuardProps {
  children: ReactNode;
  loadingFallback?: ReactNode;
  unauthenticatedFallback?: ReactNode;
  requireAuth?: boolean;
}

/**
 * AuthGuard wraps pages that require authentication.
 *
 * Uses AuthContext (not useSession directly) for consistency.
 * Shows loading state while session is fetching.
 * Shows unauthenticated fallback if user not logged in.
 *
 * Usage:
 *   export default function ProtectedPage() {
 *     return (
 *       <AuthGuard>
 *         <PageContent />
 *       </AuthGuard>
 *     );
 *   }
 */
export function AuthGuard({
  children,
  loadingFallback,
  unauthenticatedFallback,
  requireAuth = true,
}: AuthGuardProps) {
  const { session, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Redirect to login if not authenticated and requireAuth is true
    if (!isLoading && !isAuthenticated && requireAuth) {
      router.push("/sign-in");
    }
  }, [isLoading, isAuthenticated, requireAuth, router]);

  // Loading state
  if (isLoading) {
    return loadingFallback || <DefaultLoadingState />;
  }

  // Unauthenticated state
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

### Updated useTasks Hook

```typescript
// frontend/src/hooks/useTasks.ts

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
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

/**
 * Fetch all tasks for authenticated user.
 *
 * ✨ KEY CHANGE: Gets user_id from AuthContext, not useSession
 *
 * This means:
 * - Guaranteed to have user_id when called (AuthGuard ensures auth)
 * - No need to pass user_id as prop
 * - One place to manage authentication state
 *
 * Usage:
 *   export default function TasksPage() {
 *     return (
 *       <AuthGuard>
 *         <TasksContent />
 *       </AuthGuard>
 *     );
 *   }
 *
 *   function TasksContent() {
 *     const { tasks, isLoading, error } = useTasks();
 *     // user_id automatically obtained from context
 *     // No need to manage session here
 *   }
 */
export function useTasks(): UseTasksReturn {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ✨ Get both session AND user_id from context
  const { user_id } = useAuth();
  const apiUrl = useApiUrl();

  const fetchTasks = useCallback(async () => {
    // If no user_id, we're not authenticated
    // This shouldn't happen if AuthGuard is wrapping the page,
    // but we handle it gracefully
    if (!user_id) {
      setError("Not authenticated");
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // ✨ user_id is guaranteed from context
      const response = await fetch(`${apiUrl}/tasks/`, {
        headers: {
          "user_id": user_id,  // From context, not useSession
          "Content-Type": "application/json",
        },
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
  }, [user_id, apiUrl]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return { tasks, isLoading, error, refreshTasks: fetchTasks };
}
```

### Updated AppHeader Component

```typescript
// frontend/src/components/layout/AppHeader.tsx

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { PlayCircle, ArrowLeft, Settings } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

interface AppHeaderProps {
  variant?: "home" | "list" | "task" | "settings";
  showBackButton?: boolean;
  backButtonHref?: string;
  title?: string;
  subtitle?: string;
}

/**
 * Application header with optional navigation and user avatar.
 *
 * ✨ Gets user data from AuthContext instead of prop drilling.
 */
export function AppHeader({
  variant = "home",
  showBackButton = false,
  backButtonHref = "/",
  title,
  subtitle,
}: AppHeaderProps) {
  // ✨ Get session from context
  const { session } = useAuth();

  return (
    <div className="border-b bg-white">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex justify-between items-center">
          {/* Left: Logo or Back Button */}
          <div className="flex items-center gap-3">
            {showBackButton ? (
              <Link
                href={backButtonHref}
                className="flex items-center gap-2 hover:opacity-70"
              >
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

            {/* User Avatar - ✨ From context */}
            {session?.user && (
              <div className="flex items-center gap-2">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={session.user.image || ""} />
                  <AvatarFallback>
                    {session.user.name?.charAt(0) || "U"}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm text-gray-600">
                  {session.user.name || "User"}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## Testing Strategy

### Unit Tests

```typescript
// frontend/src/__tests__/context/AuthContext.test.tsx

import { render, screen } from "@testing-library/react";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { useAuth } from "@/context/AuthContext";
import { useSession } from "@/lib/auth-client";

// Mock useSession
jest.mock("@/lib/auth-client");

function TestComponent() {
  const { session, user_id, isLoading, isAuthenticated } = useAuth();

  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Not authenticated</div>;

  return (
    <div>
      <div data-testid="user-id">{user_id}</div>
      <div data-testid="user-name">{session?.user.name}</div>
    </div>
  );
}

describe("AuthContext", () => {
  it("provides session and user_id to children", () => {
    const mockSession = {
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
      },
      expiresAt: Date.now() + 3600000,
      createdAt: new Date().toISOString(),
    };

    (useSession as jest.Mock).mockReturnValue({
      data: mockSession,
      isPending: false,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId("user-id")).toHaveTextContent("user-123");
    expect(screen.getByTestId("user-name")).toHaveTextContent("Test User");
  });

  it("shows loading state while fetching session", () => {
    (useSession as jest.Mock).mockReturnValue({
      data: null,
      isPending: true,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows unauthenticated state when no session", () => {
    (useSession as jest.Mock).mockReturnValue({
      data: null,
      isPending: false,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByText("Not authenticated")).toBeInTheDocument();
  });

  it("throws error if useAuth called outside provider", () => {
    function BadComponent() {
      useAuth();  // Without AuthProvider!
      return <div>Should not render</div>;
    }

    // Suppress console.error for this test
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(<BadComponent />);
    }).toThrow("useAuth must be used within <AuthProvider>");

    spy.mockRestore();
  });
});
```

### Integration Tests

```typescript
// frontend/src/__tests__/hooks/useTasks.integration.test.tsx

import { render, screen, waitFor } from "@testing-library/react";
import { useTasks } from "@/hooks/useTasks";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { useSession } from "@/lib/auth-client";

jest.mock("@/lib/auth-client");

function TasksComponent() {
  const { tasks, isLoading, error } = useTasks();

  if (isLoading) return <div>Loading tasks...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      {tasks.length === 0 ? (
        <div>No tasks</div>
      ) : (
        <ul>
          {tasks.map((task) => (
            <li key={task.id}>{task.source_title}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

describe("useTasks with AuthContext", () => {
  beforeEach(() => {
    // Mock fetch
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("fetches tasks using user_id from context", async () => {
    const mockSession = {
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
      },
      expiresAt: Date.now() + 3600000,
      createdAt: new Date().toISOString(),
    };

    (useSession as jest.Mock).mockReturnValue({
      data: mockSession,
      isPending: false,
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tasks: [
          {
            id: "task-1",
            source_title: "Video 1",
            source_type: "youtube",
            status: "completed",
            clips_count: 3,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-01T00:00:00Z",
          },
        ],
      }),
    });

    render(
      <AuthProvider>
        <TasksComponent />
      </AuthProvider>
    );

    // Wait for tasks to load
    await waitFor(() => {
      expect(screen.getByText("Video 1")).toBeInTheDocument();
    });

    // Verify fetch was called with user_id header
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/tasks/"),
      expect.objectContaining({
        headers: expect.objectContaining({
          "user_id": "user-123",
        }),
      })
    );
  });

  it("handles fetch error gracefully", async () => {
    const mockSession = {
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
      },
      expiresAt: Date.now() + 3600000,
      createdAt: new Date().toISOString(),
    };

    (useSession as jest.Mock).mockReturnValue({
      data: mockSession,
      isPending: false,
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    render(
      <AuthProvider>
        <TasksComponent />
      </AuthProvider>
    );

    // Wait for error to display
    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument();
    });
  });
});
```

### End-to-End Tests

```typescript
// frontend/src/__tests__/e2e/auth-flow.e2e.test.tsx

/**
 * End-to-end test: User logs in, accesses protected page, fetches tasks.
 */

import { test, expect } from "@playwright/test";

test("user authentication flow with AuthContext", async ({ page }) => {
  // Navigate to home
  await page.goto("/");

  // Verify unauthenticated state (sign-in button visible)
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();

  // Sign in
  await page.goto("/sign-in");
  await page.fill('input[name="email"]', "test@example.com");
  await page.fill('input[name="password"]', "password123");
  await page.click('button[type="submit"]');

  // Wait for redirect to home (indicates auth success)
  await page.waitForURL("/");

  // Verify authenticated state
  await expect(page.getByText("Test User")).toBeVisible();

  // Navigate to tasks page
  await page.goto("/list");

  // Verify tasks load (indicates user_id passed correctly)
  await expect(page.getByText(/video 1/i)).toBeVisible();

  // Verify user info shown in header
  await expect(page.getByText("Test User")).toBeVisible();
});

test("redirects to sign-in if accessing protected page unauthenticated", async ({
  page,
}) => {
  // Try to access protected page
  await page.goto("/list");

  // Should redirect to sign-in
  await expect(page).toHaveURL(/sign-in/);
});
```

---

## Rollback Plan

If AuthContext causes issues during Phase 2 implementation:

1. **Remove AuthProvider** from root layout
2. **Revert AuthGuard** to use useSession directly
3. **Revert useTasks** to call useSession directly
4. **Prop drill user_id** through components (not ideal, but functional)

**Time to rollback**: 1-2 hours (simple revert)

**Data impact**: None (read-only changes)

---

## Timeline Impact

**AuthContext Implementation**: 4 hours (part of Phase 2)
- Design & type definitions: 1 hour
- Provider & context components: 1 hour
- Update AuthGuard & useTasks hooks: 1 hour
- Testing: 1 hour

**When to implement**: Days 1-2 of Phase 2, before updating page components

**Why before page updates**: Establish AuthContext first, then use it in all Phase 2 components

---

## References

- Phase 2 Plan: `codebase-deduplication-plan-2025-11-16.md` (Section "Phase 2: Layout & Structure")
- Phase 3 Guide: `phase3-parallel-endpoints-implementation-2025-11-16.md`
- Pre-Execution Checklist: `pre-execution-checklist-2025-11-16.md`
- React Context API: https://react.dev/reference/react/useContext
- Better Auth: https://www.better-auth.com

---

**Document Status**: APPROVED - Ready for implementation
**Created**: 2025-11-16
**Last Updated**: 2025-11-16
