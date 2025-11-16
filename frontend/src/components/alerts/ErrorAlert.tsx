/**
 * ErrorAlert component for displaying error messages.
 * Used across the application for consistent error UI.
 */

import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

interface ErrorAlertProps {
  /**
   * Error message to display
   */
  message: string;

  /**
   * Optional CSS class name for additional styling
   */
  className?: string;
}

export function ErrorAlert({ message, className = "" }: ErrorAlertProps) {
  return (
    <Alert className={`border-red-200 bg-red-50 ${className}`}>
      <AlertCircle className="h-4 w-4 text-red-500" />
      <AlertDescription className="text-sm text-red-700">
        {message}
      </AlertDescription>
    </Alert>
  );
}
