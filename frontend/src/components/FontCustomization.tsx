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
      <CardContent className="pt-6 space-y-6">
        {/* Font Family Selection */}
        <div>
          <FontSelector
            value={value.family}
            onChange={handleFamilyChange}
            placeholder="Select a font..."
          />
        </div>

        {/* Font Size Slider */}
        <div>
          <FontSizeSlider
            value={value.size}
            onChange={handleSizeChange}
            disabled={disabled}
            min={12}
            max={48}
            label="Font Size"
          />
        </div>

        {/* Font Color Picker */}
        <div>
          <FontColorPicker
            value={value.color}
            onChange={handleColorChange}
            disabled={disabled}
            label="Font Color"
          />
        </div>

        {/* Preview */}
        {showPreview && (
          <div className="pt-4 border-t">
            <p className="text-sm font-medium text-muted-foreground mb-3">
              Preview
            </p>
            <FontPreview
              fontFamily={value.family}
              fontSize={value.size}
              fontColor={value.color}
              previewText="Your subtitle will look like this"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// end frontend/src/components/FontCustomization.tsx
