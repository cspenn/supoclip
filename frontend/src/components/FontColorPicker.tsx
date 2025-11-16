// start frontend/src/components/FontColorPicker.tsx

"use client";

import React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

interface FontColorPickerProps {
  value: string;
  onChange: (color: string) => void;
  disabled?: boolean;
  label?: string;
  presets?: string[];
}

const DEFAULT_PRESETS = ["#FFFFFF", "#000000", "#FFD700", "#FF6B6B", "#4ECDC4", "#45B7D1"];

/**
 * Reusable font color picker component
 * Allows selection of font color via hex input or preset swatches
 */
export function FontColorPicker({
  value,
  onChange,
  disabled = false,
  label = "Font Color",
  presets = DEFAULT_PRESETS,
}: FontColorPickerProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor="font-color">{label}</Label>
      <div className="flex gap-2 items-center">
        <Input
          id="font-color"
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="w-16 h-10 cursor-pointer"
        />
        <Input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="#FFFFFF"
          className="flex-1"
        />
      </div>
      <div className="flex gap-2 flex-wrap">
        {presets.map((preset) => (
          <button
            key={preset}
            onClick={() => onChange(preset)}
            disabled={disabled}
            className={`w-8 h-8 rounded border-2 transition-all hover:scale-110 ${
              value === preset ? "border-gray-800 dark:border-gray-200" : "border-gray-300 dark:border-gray-600"
            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            style={{ backgroundColor: preset }}
            title={preset}
          />
        ))}
      </div>
    </div>
  );
}

// end frontend/src/components/FontColorPicker.tsx
