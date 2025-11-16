// start frontend/src/hooks/useClips.ts

import { useState, useEffect, useCallback } from "react";
import { useApiUrl } from "./useApiUrl";

/**
 * Clip data structure from API
 */
export interface Clip {
  id: string;
  filename: string;
  task_id: string;
  file_path: string;
  start_time: number;
  end_time: number;
  duration: number;
  text: string;
  relevance_score: number;
  reasoning: string;
  clip_order: number;
  created_at: string;
  video_url: string;
}

/**
 * Hook for fetching and managing clips for a specific task
 * Provides automatic loading, error handling, and refresh capability
 *
 * @param taskId - Task ID to fetch clips for
 * @returns Object containing clips array, loading state, error, and refresh function
 *
 * @example
 * ```tsx
 * const { clips, loading, error, refreshClips } = useClips(taskId);
 *
 * if (loading) return <div>Loading clips...</div>;
 * if (error) return <div>Error: {error}</div>;
 *
 * return (
 *   <div>
 *     {clips.map(clip => (
 *       <ClipCard key={clip.id} clip={clip} />
 *     ))}
 *     <button onClick={refreshClips}>Refresh</button>
 *   </div>
 * );
 * ```
 */
export function useClips(taskId: string | undefined) {
  const apiUrl = useApiUrl();
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchClips = useCallback(async () => {
    if (!taskId) {
      setClips([]);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/tasks/${taskId}/clips`);

      if (!response.ok) {
        throw new Error(`Failed to fetch clips: ${response.statusText}`);
      }

      const data = await response.json();
      setClips(data.clips || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setError(errorMessage);
      console.error("Error fetching clips:", err);
    } finally {
      setLoading(false);
    }
  }, [taskId, apiUrl]);

  // Fetch clips on mount and when taskId changes
  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  /**
   * Refresh clips data manually
   * Useful after operations that modify clips
   */
  const refreshClips = useCallback(async () => {
    await fetchClips();
  }, [fetchClips]);

  return {
    clips,
    loading,
    error,
    refreshClips,
  };
}

// end frontend/src/hooks/useClips.ts
