"use client";

import { useSession } from "@/lib/auth-client";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import Link from "next/link";
import React from "react";

interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  loadingFallback?: React.ReactNode;
}

/**
 * Default loading skeleton shown during authentication check
 */
function DefaultLoadingSkeleton() {
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

/**
 * Default unauthenticated fallback view with marketing content
 */
function DefaultUnauthenticatedView() {
  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-4xl mx-auto px-4 py-24">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-black mb-4">
            SupoClip
          </h1>
          <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
            Professional video clipping platform powered by AI
          </p>

          <div className="flex gap-4 justify-center mb-16">
            <Link href="/sign-up">
              <Button size="lg" className="px-8 py-3">
                Get Started
              </Button>
            </Link>
            <Link href="/sign-in">
              <Button variant="outline" size="lg" className="px-8 py-3">
                Sign In
              </Button>
            </Link>
          </div>
        </div>

        <Separator className="my-16" />

        <div className="grid md:grid-cols-3 gap-8">
          <div className="text-center">
            <h3 className="text-lg font-semibold text-black mb-2">AI Analysis</h3>
            <p className="text-gray-600">
              Advanced content analysis for optimal clip extraction
            </p>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-semibold text-black mb-2">Fast Processing</h3>
            <p className="text-gray-600">
              Enterprise-grade infrastructure for rapid video processing
            </p>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-semibold text-black mb-2">Secure Platform</h3>
            <p className="text-gray-600">
              Enterprise security standards with private processing
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Simple unauthenticated fallback for pages that just need sign-in
 */
export function SimpleUnauthenticatedView() {
  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-4xl mx-auto px-4 py-24">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-black mb-4">
            Sign In Required
          </h1>
          <p className="text-gray-600 mb-8">
            You need to sign in to access this page
          </p>
          <Link href="/sign-in">
            <Button size="lg">Sign In</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

/**
 * AuthGuard wrapper component for pages requiring authentication
 *
 * Centralizes authentication checks and loading states across the application.
 * Provides default fallbacks for loading and unauthenticated states, with
 * option to override via props.
 *
 * @example
 * // Simple usage with defaults
 * <AuthGuard>
 *   <DashboardContent />
 * </AuthGuard>
 *
 * @example
 * // Custom fallback for unauthenticated users
 * <AuthGuard fallback={<SimpleUnauthenticatedView />}>
 *   <SettingsContent />
 * </AuthGuard>
 */
export function AuthGuard({
  children,
  fallback,
  loadingFallback
}: AuthGuardProps) {
  const { data: session, isPending } = useSession();

  // Show loading state while checking authentication
  if (isPending) {
    return <>{loadingFallback || <DefaultLoadingSkeleton />}</>;
  }

  // Show fallback if user is not authenticated
  if (!session?.user) {
    return <>{fallback || <DefaultUnauthenticatedView />}</>;
  }

  // User is authenticated, render children
  return <>{children}</>;
}
