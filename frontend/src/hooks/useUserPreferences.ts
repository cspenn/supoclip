// start frontend/src/hooks/useUserPreferences.ts

import { useState, useEffect, useCallback } from "react";
import { UserPreferences } from "@/types/preferences";

interface UseUserPreferencesReturn {
  preferences: UserPreferences | null;
  isLoading: boolean;
  error: string | null;
  updatePreferences: (prefs: Partial<UserPreferences>) => Promise<void>;
}

/**
 * Default user preferences
 */
const DEFAULT_PREFERENCES: UserPreferences = {
  fontFamily: "TikTokSans-Regular",
  fontSize: 24,
  fontColor: "#FFFFFF",
  clipMinLength: 10,
  clipTargetLength: 30,
  clipMaxLength: 45,
  customAiPrompt: null,
};

/**
 * Hook for managing user preferences
 * Loads preferences from the API and provides a function to update them
 * @returns Object containing preferences, loading state, error, and update function
 */
export function useUserPreferences(): UseUserPreferencesReturn {
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetches user preferences from the backend API
   */
  const fetchPreferences = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch("/api/preferences");
      if (response.ok) {
        const data: UserPreferences = await response.json();
        setPreferences(data);
      } else if (response.status === 401) {
        // Not authenticated, use defaults
        setPreferences(DEFAULT_PREFERENCES);
      } else {
        throw new Error(`Failed to fetch preferences: ${response.statusText}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Failed to load preferences:", err);
      // Set defaults on error
      setPreferences(DEFAULT_PREFERENCES);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Updates user preferences on the backend
   * @param prefs Partial preferences object to update
   */
  const updatePreferences = useCallback(
    async (prefs: Partial<UserPreferences>) => {
      try {
        setError(null);

        const response = await fetch("/api/preferences", {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(prefs),
        });

        if (!response.ok) {
          throw new Error(`Failed to update preferences: ${response.statusText}`);
        }

        const updatedData: UserPreferences = await response.json();
        setPreferences(updatedData);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        console.error("Failed to update preferences:", err);
        throw err;
      }
    },
    []
  );

  // Load preferences on mount
  useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  return { preferences, isLoading, error, updatePreferences };
}

// end frontend/src/hooks/useUserPreferences.ts
