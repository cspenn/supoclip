import { useState, useEffect, useCallback } from "react";
import { useSession } from "@/lib/auth-client";
import { useApiUrl } from "./useApiUrl";

export interface Task {
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

/**
 * Custom hook for fetching and managing task list
 *
 * Automatically fetches tasks when user session is available.
 * Provides loading, error states and refresh functionality.
 *
 * @returns Object containing tasks array, loading state, error, and refresh function
 *
 * @example
 * const { tasks, isLoading, error, refreshTasks } = useTasks();
 */
export function useTasks() {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    if (!session?.user?.id) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

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
  }, [session?.user?.id, apiUrl]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const refreshTasks = useCallback(async () => {
    await fetchTasks();
  }, [fetchTasks]);

  return {
    tasks,
    isLoading,
    error,
    refreshTasks,
  };
}
