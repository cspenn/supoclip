// start frontend/src/components/ProcessingStatus.tsx

"use client";

import React from "react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Task processing status types
 */
export type TaskStatus = "queued" | "processing" | "completed" | "error";

/**
 * Props for ProcessingStatus component
 */
export interface ProcessingStatusProps {
  /** Current status of the task */
  status: TaskStatus;
  /** Progress percentage (0-100) */
  progress: number;
  /** Optional status message to display */
  message?: string;
  /** Optional error message if status is "error" */
  error?: string;
}

/**
 * Component for displaying task processing status with progress bar
 *
 * Shows a card with progress bar and status information.
 * Adapts styling based on task status (queued, processing, completed, error).
 *
 * @example
 * ```tsx
 * <ProcessingStatus
 *   status="processing"
 *   progress={45}
 *   message="Analyzing transcript..."
 * />
 *
 * <ProcessingStatus
 *   status="error"
 *   progress={0}
 *   error="Failed to download video"
 * />
 *
 * <ProcessingStatus
 *   status="completed"
 *   progress={100}
 *   message="All clips generated successfully"
 * />
 * ```
 */
export function ProcessingStatus({
  status,
  progress,
  message,
  error,
}: ProcessingStatusProps) {
  // Determine status label and color
  const getStatusDisplay = () => {
    switch (status) {
      case "queued":
        return { label: "Queued", color: "text-yellow-600" };
      case "processing":
        return { label: "Processing", color: "text-blue-600" };
      case "completed":
        return { label: "Completed", color: "text-green-600" };
      case "error":
        return { label: "Error", color: "text-red-600" };
      default:
        return { label: "Unknown", color: "text-gray-600" };
    }
  };

  const { label, color } = getStatusDisplay();

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="space-y-4">
          {/* Status header */}
          <div className="flex justify-between items-center">
            <span className={`text-sm font-medium ${color}`}>{label}</span>
            <span className="text-sm text-gray-500">{progress}%</span>
          </div>

          {/* Progress bar */}
          <Progress
            value={progress}
            className="w-full"
            // Note: If your Progress component supports className for the indicator,
            // you can pass it here. Otherwise, this is handled by the component itself.
          />

          {/* Status message */}
          {message && (
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {message}
            </p>
          )}

          {/* Error message (if present) */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 font-medium">
              {error}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// end frontend/src/components/ProcessingStatus.tsx
