// start frontend/src/components/FontSizeSlider.tsx

"use client";

import React from "react";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

interface FontSizeSlizerProps {
  value: number;
  onChange: (size: number) => void;
  disabled?: boolean;
  min?: number;
  max?: number;
  label?: string;
}

/**
 * Reusable font size slider component
 * Allows selection of font size from 12px to 48px
 */
export function FontSizeSlider({
  value,
  onChange,
  disabled = false,
  min = 12,
  max = 48,
  label = "Font Size",
}: FontSizeSlizerProps) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <Label htmlFor="font-size">{label}</Label>
        <span className="text-sm font-semibold text-muted-foreground">
          {value}px
        </span>
      </div>
      <Slider
        id="font-size"
        min={min}
        max={max}
        step={1}
        value={[value]}
        onValueChange={(vals) => onChange(vals[0])}
        disabled={disabled}
        className="w-full"
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{min}px</span>
        <span>{max}px</span>
      </div>
    </div>
  );
}

// end frontend/src/components/FontSizeSlider.tsx
