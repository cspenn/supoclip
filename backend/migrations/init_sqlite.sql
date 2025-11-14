-- SupoClip SQLite Schema
-- Converted from PostgreSQL (init.sql)
-- Key differences from PostgreSQL:
-- - TEXT for UUIDs instead of UUID type
-- - INTEGER (0/1) for booleans instead of BOOLEAN
-- - DATETIME for timestamps instead of TIMESTAMP
-- - No UUID extension required

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    emailVerified INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
    image TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    first_name TEXT,
    last_name TEXT,
    password_hash TEXT,
    default_font_family TEXT DEFAULT 'TikTokSans-Regular',
    default_font_size INTEGER DEFAULT 24,
    default_font_color TEXT DEFAULT '#FFFFFF'
);

-- Sources table
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    type TEXT CHECK (type IN ('youtube', 'video_url')) NOT NULL,
    title TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL,
    source_id TEXT,
    generated_clips_ids TEXT,  -- JSON array stored as TEXT
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    progress_message TEXT,
    font_family TEXT DEFAULT 'TikTokSans-Regular',
    font_size INTEGER DEFAULT 24,
    font_color TEXT DEFAULT '#FFFFFF',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

-- Generated clips table
CREATE TABLE IF NOT EXISTS generated_clips (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    task_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration REAL NOT NULL,
    text TEXT,
    relevance_score REAL NOT NULL,
    reasoning TEXT,
    clip_order INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Better Auth tables
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    expiresAt DATETIME NOT NULL,
    token TEXT UNIQUE NOT NULL,
    createdAt DATETIME NOT NULL,
    updatedAt DATETIME NOT NULL,
    ipAddress TEXT,
    userAgent TEXT,
    userId TEXT NOT NULL,
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS account (
    id TEXT PRIMARY KEY,
    accountId TEXT NOT NULL,
    providerId TEXT NOT NULL,
    userId TEXT NOT NULL,
    accessToken TEXT,
    refreshToken TEXT,
    idToken TEXT,
    accessTokenExpiresAt DATETIME,
    refreshTokenExpiresAt DATETIME,
    scope TEXT,
    password TEXT,
    createdAt DATETIME NOT NULL,
    updatedAt DATETIME NOT NULL,
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS verification (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL,
    value TEXT NOT NULL,
    expiresAt DATETIME NOT NULL,
    createdAt DATETIME,
    updatedAt DATETIME
);

-- Indexes (same as PostgreSQL)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_source_id ON tasks(source_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources(created_at);
CREATE INDEX IF NOT EXISTS idx_generated_clips_task_id ON generated_clips(task_id);
CREATE INDEX IF NOT EXISTS idx_generated_clips_clip_order ON generated_clips(clip_order);
CREATE INDEX IF NOT EXISTS idx_generated_clips_created_at ON generated_clips(created_at);
CREATE INDEX IF NOT EXISTS idx_session_token ON session(token);
CREATE INDEX IF NOT EXISTS idx_session_userId ON session(userId);
CREATE INDEX IF NOT EXISTS idx_account_userId ON account(userId);
CREATE INDEX IF NOT EXISTS idx_verification_identifier ON verification(identifier);

-- Triggers for auto-updating timestamps
-- SQLite doesn't have the same trigger syntax as PostgreSQL
CREATE TRIGGER IF NOT EXISTS update_users_updatedAt
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_sources_updated_at
AFTER UPDATE ON sources
FOR EACH ROW
BEGIN
    UPDATE sources SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_generated_clips_updated_at
AFTER UPDATE ON generated_clips
FOR EACH ROW
BEGIN
    UPDATE generated_clips SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_session_updatedAt
AFTER UPDATE ON session
FOR EACH ROW
BEGIN
    UPDATE session SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_account_updatedAt
AFTER UPDATE ON account
FOR EACH ROW
BEGIN
    UPDATE account SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_verification_updatedAt
AFTER UPDATE ON verification
FOR EACH ROW
BEGIN
    UPDATE verification SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
