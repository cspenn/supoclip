"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskCard } from "@/components/TaskCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/alerts/ErrorAlert";
import { AuthGuard, SimpleUnauthenticatedView } from "@/components/auth/AuthGuard";
import { useTasks } from "@/hooks/useTasks";
import { ArrowLeft, PlayCircle } from "lucide-react";
import Link from "next/link";

export default function ListPage() {
  const { tasks, isLoading, error } = useTasks();

  return (
    <AuthGuard fallback={<SimpleUnauthenticatedView />}>
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <div className="flex items-center gap-4 mb-4">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            </Link>
          </div>

          <div>
            <h1 className="text-2xl font-bold text-black mb-2">All Generations</h1>
            <p className="text-gray-600">
              View and manage all your video clip generations
            </p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        {isLoading ? (
          <div className="grid gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-5 w-64" />
                      <Skeleton className="h-4 w-48" />
                    </div>
                    <Skeleton className="h-8 w-24" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : error ? (
          <ErrorAlert message={error} />
        ) : tasks.length === 0 ? (
          <EmptyState
            icon={PlayCircle}
            title="No generations yet"
            description="Start by processing your first video to create clips."
            action={{
              label: "Create New Generation",
              href: "/",
              icon: PlayCircle,
            }}
          />
        ) : (
          <div className="space-y-4">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </div>
    </div>
    </AuthGuard>
  );
}
