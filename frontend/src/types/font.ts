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
  // Extended Styling
  strokeColor?: string;
  strokeWidth?: number;
  shadowColor?: string;
  shadowOffset?: number;
  textTransform?: "none" | "uppercase" | "lowercase";
  // Positioning
  positionX?: number; // 0.0 to 1.0
  positionY?: number; // 0.0 to 1.0
  alignment?: "left" | "center" | "right";
}

// end frontend/src/types/font.ts
