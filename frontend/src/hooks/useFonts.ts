// start frontend/src/hooks/useFonts.ts

import { useState, useEffect, useCallback } from "react";
import { Font } from "@/types/font";
import { useApiUrl } from "./useApiUrl";

interface UseFontsReturn {
  fonts: Font[];
  isLoading: boolean;
  error: string | null;
  refreshFonts: () => Promise<void>;
}

/**
 * Hook for managing font loading and injection
 * Fetches available fonts from the backend and injects them into the document
 * @returns Object containing fonts array, loading state, error, and refresh function
 */
export function useFonts(): UseFontsReturn {
  const [fonts, setFonts] = useState<Font[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const apiUrl = useApiUrl();

  /**
   * Injects @font-face styles into the document for all fonts
   */
  const injectFonts = useCallback((fontList: Font[]) => {
    try {
      const fontFaceStyles = fontList
        .map((font) => {
          return `
            @font-face {
              font-family: '${font.name}';
              src: url('${apiUrl}/fonts/${font.name}') format('truetype');
              font-weight: ${font.weight || 'normal'};
              font-style: ${font.style || 'normal'};
            }
          `;
        })
        .join("\n");

      // Remove existing custom fonts style if present
      const existingStyle = document.getElementById("custom-fonts-style");
      if (existingStyle) {
        existingStyle.remove();
      }

      // Inject new font styles into the page
      const styleElement = document.createElement("style");
      styleElement.id = "custom-fonts-style";
      styleElement.innerHTML = fontFaceStyles;
      document.head.appendChild(styleElement);
    } catch (err) {
      console.error("Failed to inject fonts:", err);
    }
  }, [apiUrl]);

  /**
   * Fetches fonts from the backend API
   */
  const fetchFonts = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/fonts`);
      if (!response.ok) {
        throw new Error(`Failed to fetch fonts: ${response.statusText}`);
      }

      const data = await response.json();
      const fontList: Font[] = data.fonts || data;
      setFonts(fontList);
      injectFonts(fontList);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Font fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl, injectFonts]);

  /**
   * Refreshes the font list from the backend
   */
  const refreshFonts = useCallback(async () => {
    try {
      setError(null);

      const response = await fetch(`${apiUrl}/fonts/refresh`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Refresh failed: ${response.statusText}`);
      }

      // Refetch font list after refresh
      await fetchFonts();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Font refresh error:", err);
    }
  }, [apiUrl, fetchFonts]);

  // Load fonts on mount
  useEffect(() => {
    fetchFonts();
  }, [fetchFonts]);

  // Cleanup: remove injected styles on unmount
  useEffect(() => {
    return () => {
      const styleElement = document.getElementById("custom-fonts-style");
      if (styleElement) {
        styleElement.remove();
      }
    };
  }, []);

  return { fonts, isLoading, error, refreshFonts };
}

// end frontend/src/hooks/useFonts.ts
