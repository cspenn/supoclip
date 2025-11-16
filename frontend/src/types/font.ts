// start frontend/src/types/font.ts

/**
 * Represents a single font available in the system
 */
export interface Font {
  id: string;
  name: string;
  family: string;
  style?: string;
  weight?: number;
  source: "bundled" | "system";
}

/**
 * Font customization options for video clip generation
 */
export interface FontOptions {
  family: string;
  size: number;
  color: string;
}

// end frontend/src/types/font.ts
