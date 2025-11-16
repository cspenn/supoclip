-- Migration: Add system_fonts table for font caching
-- Date: 2025-11-15
-- Status: For SQLite backend

-- Create system_fonts table with SQLite-compatible syntax
CREATE TABLE IF NOT EXISTS system_fonts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL,
    style TEXT,
    weight INTEGER,
    file_path TEXT,
    file_hash TEXT,
    is_valid INTEGER DEFAULT 1,
    detection_timestamp TEXT,
    metadata_json TEXT,
    source TEXT NOT NULL CHECK(source IN ('bundled', 'system')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_system_fonts_family ON system_fonts(family);
CREATE INDEX IF NOT EXISTS idx_system_fonts_source ON system_fonts(source);
CREATE INDEX IF NOT EXISTS idx_system_fonts_is_valid ON system_fonts(is_valid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_fonts_name_file ON system_fonts(name, file_path);

-- Create trigger for auto-updating updated_at
CREATE TRIGGER IF NOT EXISTS update_system_fonts_updated_at
AFTER UPDATE ON system_fonts
FOR EACH ROW
BEGIN
    UPDATE system_fonts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
