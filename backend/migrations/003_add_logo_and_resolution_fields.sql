-- Migration: Add logo and resolution fields to users table
-- Date: 2025-11-19
-- Status: For SQLite backend
-- Purpose: Adds logo_file_path, logo_corner_position, and output_resolution columns

-- Add logo_file_path column if it doesn't exist
ALTER TABLE users ADD COLUMN logo_file_path VARCHAR(500);

-- Add logo_corner_position column with default and check constraint
ALTER TABLE users ADD COLUMN logo_corner_position VARCHAR(20) DEFAULT 'top-right'
    CHECK (logo_corner_position IN ('top-left', 'top-right', 'bottom-left', 'bottom-right'));

-- Add output_resolution column with default and check constraint
ALTER TABLE users ADD COLUMN output_resolution VARCHAR(10) DEFAULT '720p'
    CHECK (output_resolution IN ('480p', '720p', '1080p'));

-- Note: SQLite doesn't support adding multiple columns in a single ALTER TABLE statement
-- Each ALTER TABLE statement adds one column at a time
