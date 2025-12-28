// start frontend/src/components/FontCustomization.tsx

"use client";

import React, { useState } from "react";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChevronDown } from "lucide-react";
import { FontSelector } from "@/components/FontSelector";
import { FontSizeSlider } from "@/components/FontSizeSlider";
import { FontColorPicker } from "@/components/FontColorPicker";
import { FontPreview } from "@/components/FontPreview";
import { FontOptions } from "@/types/font";

interface FontCustomizationProps {
  value: FontOptions;
  onChange: (options: FontOptions) => void;
  disabled?: boolean;
  showPreview?: boolean;
  collapsible?: boolean;
}

/**
 * Composite component for complete font customization
 * Combines FontSelector, FontSizeSlider, FontColorPicker, and FontPreview
 * Provides a unified interface for font selection and customization
 */
export function FontCustomization({
  value,
  onChange,
  disabled = false,
  showPreview = true,
  collapsible = false,
}: FontCustomizationProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleFamilyChange = (family: string) => {
    onChange({ ...value, family });
  };

  const handleSizeChange = (size: number) => {
    onChange({ ...value, size });
  };

  const handleColorChange = (color: string) => {
    onChange({ ...value, color });
  };

  if (collapsible && isCollapsed) {
    return (
      <Card className="border-0 bg-muted/30">
        <button
          onClick={() => setIsCollapsed(false)}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
          disabled={disabled}
        >
          <span className="font-semibold text-lg">Font & Style Options</span>
          <ChevronDown className="w-5 h-5 transform transition-transform" />
        </button>
      </Card>
    );
  }

  return (
    <Card className="border-0 bg-muted/30">
      {collapsible && (
        <CardHeader className="pb-3 cursor-pointer" onClick={() => setIsCollapsed(true)}>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Font & Style Options</CardTitle>
            <ChevronDown className="w-5 h-5 transform transition-transform rotate-180" />
          </div>
        </CardHeader>
      )}
      {!collapsible && (
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <span>Font & Style Options</span>
          </CardTitle>
        </CardHeader>
      )}
      <Separator className="mx-6" />
      <CardContent className="pt-6 space-y-8">
        {/* === Typography Section === */}
        <div className="space-y-6">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Typography
          </h3>

          <FontSelector
            value={value.family}
            onChange={handleFamilyChange}
            placeholder="Select a font..."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <FontSizeSlider
              value={value.size}
              onChange={handleSizeChange}
              disabled={disabled}
              min={12}
              max={64}
              label="Font Size"
            />
            <FontColorPicker
              value={value.color}
              onChange={handleColorChange}
              disabled={disabled}
              label="Text Color"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
              Text Transform
            </label>
            <div className="flex gap-2">
              {(["none", "uppercase", "lowercase"] as const).map((transform) => (
                <button
                  key={transform}
                  onClick={() => onChange({ ...value, textTransform: transform })}
                  className={`px-3 py-1.5 text-sm rounded-md border transition-all ${(value.textTransform || "none") === transform
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-transparent hover:bg-muted border-input"
                    }`}
                >
                  {transform.charAt(0).toUpperCase() + transform.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        <Separator />

        {/* === Styling Section === */}
        <div className="space-y-6">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Styling Effects
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            {/* Stroke */}
            <div className="space-y-4">
              <FontColorPicker
                value={value.strokeColor || "#000000"}
                onChange={(c) => onChange({ ...value, strokeColor: c })}
                disabled={disabled}
                label="Stroke Color"
              />
              <FontSizeSlider
                value={value.strokeWidth ?? 0}
                onChange={(v) => onChange({ ...value, strokeWidth: v })}
                disabled={disabled}
                min={0}
                max={10}
                label="Stroke Width"
              />
            </div>

            {/* Shadow */}
            <div className="space-y-4">
              <FontColorPicker
                value={value.shadowColor || "#000000"}
                onChange={(c) => onChange({ ...value, shadowColor: c })}
                disabled={disabled}
                label="Shadow Color"
              />
              <FontSizeSlider
                value={value.shadowOffset ?? 0}
                onChange={(v) => onChange({ ...value, shadowOffset: v })}
                disabled={disabled}
                min={0}
                max={10}
                label="Shadow Offset"
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* === Positioning Section === */}
        <div className="space-y-6">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Positioning
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Vertical Y */}
            <div className="space-y-3">
              <div className="flex justify-between">
                <label className="text-sm font-medium">Vertical Position (Y)</label>
                <span className="text-xs text-muted-foreground">
                  {Math.round((value.positionY ?? 0.65) * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={Math.round((value.positionY ?? 0.65) * 100)}
                onChange={(e) => onChange({ ...value, positionY: parseInt(e.target.value) / 100 })}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
                disabled={disabled}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Top (0%)</span>
                <span>Bottom (100%)</span>
              </div>
            </div>

            {/* Horizontal X */}
            <div className="space-y-3">
              <div className="flex justify-between">
                <label className="text-sm font-medium">Horizontal Position (X)</label>
                <span className="text-xs text-muted-foreground">
                  {Math.round((value.positionX ?? 0.50) * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={Math.round((value.positionX ?? 0.50) * 100)}
                onChange={(e) => onChange({ ...value, positionX: parseInt(e.target.value) / 100 })}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
                disabled={disabled}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Left (0%)</span>
                <span>Right (100%)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Preview */}
        {showPreview && (
          <div className="pt-4 border-t">
            <p className="text-sm font-medium text-muted-foreground mb-3">
              Live Preview
            </p>
            <FontPreview
              fontFamily={value.family}
              fontSize={value.size}
              fontColor={value.color}
              strokeColor={value.strokeColor}
              strokeWidth={value.strokeWidth}
              shadowColor={value.shadowColor}
              shadowOffset={value.shadowOffset}
              textTransform={value.textTransform}
              previewText="Your styled captions will look like this"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// end frontend/src/components/FontCustomization.tsx
