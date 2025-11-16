/**
 * SuccessAlert component for displaying success messages.
 * Used across the application for consistent success UI.
 */

import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle } from "lucide-react";

interface SuccessAlertProps {
  /**
   * Success message to display
   */
  message: string;

  /**
   * Optional CSS class name for additional styling
   */
  className?: string;
}

export function SuccessAlert({ message, className = "" }: SuccessAlertProps) {
  return (
    <Alert className={`border-green-200 bg-green-50 ${className}`}>
      <CheckCircle className="h-4 w-4 text-green-500" />
      <AlertDescription className="text-sm text-green-700">
        {message}
      </AlertDescription>
    </Alert>
  );
}
