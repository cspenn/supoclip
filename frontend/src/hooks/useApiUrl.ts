// start frontend/src/hooks/useApiUrl.ts

/**
 * Centralized hook for getting the API URL
 * Ensures consistent API endpoint across the application
 * @returns The API URL from environment variable or default
 */
export function useApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

// end frontend/src/hooks/useApiUrl.ts
