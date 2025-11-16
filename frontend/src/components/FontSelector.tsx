// start frontend/src/components/FontSelector.tsx

"use client";

import React, { useState, useEffect } from "react";
import { Search, RefreshCw, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useFonts } from "@/hooks/useFonts";
import { Font } from "@/types/font";

interface FontSelectorProps {
  value?: string;
  onChange?: (fontName: string) => void;
  placeholder?: string;
}

export function FontSelector({
  value,
  onChange,
  placeholder = "Select a font...",
}: FontSelectorProps) {
  const { fonts, isLoading, error, refreshFonts } = useFonts();
  const [filteredFonts, setFilteredFonts] = useState<Font[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Filter fonts when search query or fonts list changes
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredFonts(fonts);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = fonts.filter(
        (f) =>
          f.name.toLowerCase().includes(query) ||
          f.family.toLowerCase().includes(query)
      );
      setFilteredFonts(filtered);
    }
  }, [searchQuery, fonts]);

  const handleRefresh = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setIsRefreshing(true);
      await refreshFonts();
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSelectFont = (fontName: string) => {
    onChange?.(fontName);
    setIsOpen(false);
    setSearchQuery("");
  };

  const selectedFont = fonts.find((f) => f.name === value);
  const bundledFonts = filteredFonts.filter((f) => f.source === "bundled");
  const systemFonts = filteredFonts.filter((f) => f.source === "system");

  return (
    <div className="relative w-full">
      {/* Dropdown trigger button */}
      <Button
        variant="outline"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full justify-between"
      >
        <span className="truncate">
          {selectedFont ? selectedFont.name : placeholder}
        </span>
        <ChevronDown className="ml-2 h-4 w-4 opacity-50" />
      </Button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg">
          {/* Search bar */}
          <div className="p-3 border-b border-gray-200">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search fonts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                  autoFocus
                />
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleRefresh}
                disabled={isRefreshing}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>

          {/* Font list */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center text-gray-500">Loading fonts...</div>
            ) : error ? (
              <div className="p-4 text-center text-red-500 text-sm">{error}</div>
            ) : filteredFonts.length === 0 ? (
              <div className="p-4 text-center text-gray-500">No fonts found</div>
            ) : (
              <>
                {/* Bundled fonts section */}
                {bundledFonts.length > 0 && (
                  <>
                    <div className="px-3 py-2 text-xs font-semibold text-gray-500 bg-gray-50">
                      Bundled Fonts
                    </div>
                    {bundledFonts.map((font) => (
                      <button
                        key={font.id}
                        onClick={() => handleSelectFont(font.name)}
                        className="w-full px-3 py-2 text-left hover:bg-blue-50 flex justify-between items-center"
                      >
                        <div>
                          <div className="font-medium">{font.name}</div>
                          <div className="text-xs text-gray-500">
                            {font.family} {font.style && `• ${font.style}`}{" "}
                            {font.weight && `• ${font.weight}`}
                          </div>
                        </div>
                        {value === font.name && (
                          <div className="text-blue-600">✓</div>
                        )}
                      </button>
                    ))}
                  </>
                )}

                {/* System fonts section */}
                {systemFonts.length > 0 && (
                  <>
                    <div className="px-3 py-2 text-xs font-semibold text-gray-500 bg-gray-50 border-t">
                      System Fonts ({systemFonts.length})
                    </div>
                    {systemFonts.map((font) => (
                      <button
                        key={font.id}
                        onClick={() => handleSelectFont(font.name)}
                        className="w-full px-3 py-2 text-left hover:bg-blue-50 flex justify-between items-center"
                      >
                        <div>
                          <div className="font-medium">{font.name}</div>
                          <div className="text-xs text-gray-500">
                            {font.family} {font.style && `• ${font.style}`}{" "}
                            {font.weight && `• ${font.weight}`}
                          </div>
                        </div>
                        {value === font.name && (
                          <div className="text-blue-600">✓</div>
                        )}
                      </button>
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Close dropdown when clicking outside */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}

// end frontend/src/components/FontSelector.tsx
