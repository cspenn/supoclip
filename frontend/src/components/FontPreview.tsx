// start frontend/src/components/FontPreview.tsx

"use client";

import React from "react";

interface FontPreviewProps {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  text?: string;
  previewText?: string;
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
}: FontPreviewProps) {
  return (
    <div
      className="w-full p-6 rounded-lg bg-black text-center"
      style={{
        fontFamily: `'${fontFamily}'`,
      }}
    >
      <div
        style={{
          fontSize: `${fontSize}px`,
          color: fontColor,
          fontWeight: 500,
          lineHeight: 1.4,
        }}
      >
        {text || previewText}
      </div>
    </div>
  );
}

// end frontend/src/components/FontPreview.tsx
