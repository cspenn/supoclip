// start frontend/src/types/preferences.ts

/**
 * User preferences for video processing and clip generation
 */
export interface UserPreferences {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  clipMinLength: number;
  clipTargetLength: number;
  clipMaxLength: number;
  customAiPrompt: string | null;
  outputResolution: "480p" | "720p" | "1080p";
}

// end frontend/src/types/preferences.ts
