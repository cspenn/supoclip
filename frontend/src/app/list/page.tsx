"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskCard } from "@/components/TaskCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/alerts/ErrorAlert";
import { AuthGuard, SimpleUnauthenticatedView } from "@/components/auth/AuthGuard";
import { useSession } from "@/lib/auth-client";
import { ArrowLeft, PlayCircle } from "lucide-react";
import Link from "next/link";

interface Task {
  id: string;
  user_id: string;
  source_id: string;
  source_title: string;
  source_type: string;
  status: string;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

export default function ListPage() {
  const { data: session } = useSession();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    const fetchTasks = async () => {
      if (!session?.user?.id) return;

      try {
        setIsLoading(true);
        const response = await fetch(`${apiUrl}/tasks/`, {
          headers: {
            'user_id': session.user.id,
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch tasks: ${response.status}`);
        }

        const data = await response.json();
        setTasks(data.tasks || []);
      } catch (err) {
        console.error("Error fetching tasks:", err);
        setError(err instanceof Error ? err.message : "Failed to load tasks");
      } finally {
        setIsLoading(false);
      }
    };

    fetchTasks();
  }, [session?.user?.id, apiUrl]);

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
