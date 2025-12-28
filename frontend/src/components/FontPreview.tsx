// start frontend/src/components/FontPreview.tsx

"use client";

import React from "react";

interface FontPreviewProps {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  text?: string;
  previewText?: string;
  // Extended styling
  strokeColor?: string;
  strokeWidth?: number;
  shadowColor?: string;
  shadowOffset?: number;
  textTransform?: "none" | "uppercase" | "lowercase";
}

/**
 * Reusable font preview component
 * Displays a preview of how text will look with selected font options
 */
export function FontPreview({
  fontFamily,
  fontSize,
  fontColor,
  text,
  previewText = "Preview: Your subtitle will look like this",
  strokeColor = "transparent",
  strokeWidth = 0,
  shadowColor = "transparent",
  shadowOffset = 0,
  textTransform = "none",
}: FontPreviewProps) {

  // Construct shadow string
  const textShadow = shadowColor && shadowColor !== "transparent" && shadowOffset > 0
    ? `${shadowOffset}px ${shadowOffset}px 0px ${shadowColor}`
    : "none";

  // Construct stroke style (using webkit prefix for compatibility)
  const textStroke = strokeWidth > 0 && strokeColor !== "transparent"
    ? `${strokeWidth}px ${strokeColor}`
    : "none";

  return (
    <div
      className="w-full p-6 rounded-lg bg-black text-center overflow-hidden"
      style={{
        fontFamily: `'${fontFamily}'`,
      }}
    >
      <div
        style={{
          fontSize: `${fontSize}px`,
          color: fontColor,
          fontWeight: 700, // Default to bold for subtitles
          lineHeight: 1.4,
          textTransform: textTransform,
          textShadow: textShadow,
          WebkitTextStroke: textStroke,
        }}
        className="transition-all duration-200"
      >
        {text || previewText}
      </div>
    </div>
  );
}

// end frontend/src/components/FontPreview.tsx
