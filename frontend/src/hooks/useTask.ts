import { useState, useEffect, useCallback } from "react";
import { useSession } from "@/lib/auth-client";
import { useApiUrl } from "./useApiUrl";

export interface TaskDetail {
  id: string;
  user_id: string;
  source_id: string;
  source_title: string;
  source_type: string;
  source_url?: string;
  status: string;
  clips_count: number;
  processing_error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  // Progress tracking fields
  progress?: number;
  progress_message?: string;
  // Font customization fields
  font_family?: string;
  font_size?: number;
  font_color?: string;
}

export interface Clip {
  id: string;
  filename: string;
  title?: string;
  duration: number;
  start_time: number | string;
  end_time: number | string;
  task_id: string;
  created_at: string;
  // Additional fields used by task detail page
  file_path?: string;
  text?: string;
  relevance_score?: number;
  reasoning?: string;
  clip_order?: number;
  video_url?: string;
}

/**
 * Custom hook for fetching and managing a single task with its clips
 *
 * Automatically fetches task details when task ID is provided.
 * Includes retry logic for tasks that might not be persisted yet.
 * Fetches clips if task status is 'completed'.
 *
 * @param taskId - The ID of the task to fetch
 * @param options - Optional configuration
 * @param options.maxRetries - Maximum number of retries for 404 responses (default: 5)
 * @returns Object containing task, clips, loading state, error, and refresh function
 *
 * @example
 * const { task, clips, isLoading, error, refresh } = useTask(taskId);
 */
export function useTask(
  taskId: string | null | undefined,
  options: { maxRetries?: number } = {}
) {
  const { maxRetries = 5 } = options;
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTaskStatus = useCallback(async (retryCount = 0): Promise<boolean> => {
    if (!taskId) return false;

    try {
      setError(null);

      const taskHeaders: HeadersInit = {};
      if (session?.user?.id) {
        taskHeaders["user_id"] = session.user.id;
      }

      const taskResponse = await fetch(`${apiUrl}/tasks/${taskId}`, {
        headers: taskHeaders,
      });

      // Handle 404 with retry logic (task might not be persisted yet)
      if (taskResponse.status === 404 && retryCount < maxRetries) {
        console.log(`Task not found yet, retrying in ${(retryCount + 1) * 500}ms... (${retryCount + 1}/${maxRetries})`);
        await new Promise((resolve) => setTimeout(resolve, (retryCount + 1) * 500));
        return fetchTaskStatus(retryCount + 1);
      }

      if (!taskResponse.ok) {
        throw new Error(`Failed to fetch task: ${taskResponse.status}`);
      }

      const taskData = await taskResponse.json();
      setTask(taskData);

      // Only fetch clips if task is completed
      if (taskData.status === "completed") {
        const clipsHeaders: HeadersInit = {};
        if (session?.user?.id) {
          clipsHeaders["user_id"] = session.user.id;
        }

        const clipsResponse = await fetch(`${apiUrl}/tasks/${taskId}/clips`, {
          headers: clipsHeaders,
        });

        if (!clipsResponse.ok) {
          throw new Error(`Failed to fetch clips: ${clipsResponse.status}`);
        }

        const clipsData = await clipsResponse.json();
        setClips(clipsData.clips || []);
      }

      return true;
    } catch (err) {
      console.error("Error fetching task data:", err);
      setError(err instanceof Error ? err.message : "Failed to load task");
      return false;
    }
  }, [taskId, session?.user?.id, apiUrl, maxRetries]);

  useEffect(() => {
    if (!taskId) {
      setIsLoading(false);
      return;
    }

    const fetchTaskData = async () => {
      try {
        setIsLoading(true);
        await fetchTaskStatus();
      } finally {
        setIsLoading(false);
      }
    };

    fetchTaskData();
  }, [taskId, fetchTaskStatus]);

  const refresh = useCallback(async () => {
    if (!taskId) return;
    setIsLoading(true);
    try {
      await fetchTaskStatus();
    } finally {
      setIsLoading(false);
    }
  }, [taskId, fetchTaskStatus]);

  return {
    task,
    clips,
    isLoading,
    error,
    refresh,
    fetchTaskStatus, // Exposed for SSE polling use case
  };
}
