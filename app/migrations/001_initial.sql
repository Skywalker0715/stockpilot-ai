-- 001_initial.sql: asset catalog and submission/review history.

CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    file_reference TEXT,
    media_type TEXT,
    title TEXT,
    description TEXT,
    -- JSON array of keyword strings, normalized on write by the service layer.
    keywords TEXT NOT NULL DEFAULT '[]',
    category TEXT,
    -- Origin of the current metadata content.
    metadata_origin TEXT NOT NULL DEFAULT 'manual'
        CHECK (metadata_origin IN ('manual', 'imported', 'ai_suggested')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_assets_category ON assets(category);
CREATE INDEX idx_assets_archived ON assets(archived);

CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    -- Submission/review lifecycle state.
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'accepted', 'rejected', 'withdrawn', 'unknown')),
    submitted_at TEXT,
    reviewed_at TEXT,
    rejection_note TEXT,
    rejection_category TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_submissions_asset ON submissions(asset_id);
CREATE INDEX idx_submissions_status ON submissions(status);
