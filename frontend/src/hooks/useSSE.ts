// start frontend/src/hooks/useSSE.ts

import { useState, useEffect, useCallback } from "react";
import { useApiUrl } from "./useApiUrl";

/**
 * Server-Sent Events (SSE) data structure
 */
export interface SSEData {
  status: string;
  progress?: number;
  message?: string;
  // Allow additional fields with unknown type
  [key: string]: unknown;
}

/**
 * Hook for subscribing to Server-Sent Events (SSE) for real-time updates
 * Automatically manages EventSource connection lifecycle
 *
 * @param taskId - Task ID to monitor (undefined to skip connection)
 * @param onData - Optional callback for each SSE message
 * @returns Object containing latest data, connection state, and error
 *
 * @example
 * ```tsx
 * const { data, connected, error } = useSSE(taskId, (newData) => {
 *   console.log("Progress update:", newData.progress);
 * });
 *
 * if (!connected) return <div>Connecting...</div>;
 * if (error) return <div>Connection error: {error}</div>;
 *
 * return (
 *   <div>
 *     Status: {data?.status}
 *     Progress: {data?.progress}%
 *   </div>
 * );
 * ```
 */
export function useSSE(
  taskId: string | undefined,
  onData?: (data: SSEData) => void
) {
  const apiUrl = useApiUrl();
  const [data, setData] = useState<SSEData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const handleData = useCallback(
    (newData: SSEData) => {
      setData(newData);
      if (onData) {
        onData(newData);
      }
    },
    [onData]
  );

  useEffect(() => {
    if (!taskId) {
      setConnected(false);
      setData(null);
      setError(null);
      return;
    }

    // Construct SSE endpoint URL
    const sseUrl = `${apiUrl}/tasks/${taskId}/progress`;

    // Create EventSource
    const eventSource = new EventSource(sseUrl);

    // Handle connection open
    eventSource.onopen = () => {
      console.log(`SSE connected for task ${taskId}`);
      setConnected(true);
      setError(null);
    };

    // Handle incoming messages
    eventSource.onmessage = (event) => {
      try {
        const parsedData = JSON.parse(event.data);
        handleData(parsedData);
      } catch (err) {
        console.error("Error parsing SSE data:", err);
        setError("Failed to parse server message");
      }
    };

    // Handle connection errors
    eventSource.onerror = (err) => {
      console.error("SSE error:", err);
      setError("Connection lost");
      setConnected(false);
      eventSource.close();
    };

    // Cleanup: close connection when component unmounts or taskId changes
    return () => {
      console.log(`SSE disconnecting for task ${taskId}`);
      eventSource.close();
      setConnected(false);
    };
  }, [taskId, apiUrl, handleData]);

  return {
    data,
    error,
    connected,
  };
}

// end frontend/src/hooks/useSSE.ts
