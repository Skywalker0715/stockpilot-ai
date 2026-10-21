-- 003_vision_insights.sql: persisted vision-insights analysis results (additive only).
-- Existing tables are untouched; existing records are preserved.
-- Each row stores one AI vision-insights analysis for one asset. An asset may
-- have multiple analyses over time (the most recent is served to the UI).
--
-- All analysis content is AI-generated and is labeled as such in the UI: it is
-- never presented as measured market demand, sales volume, or ranking data.

CREATE TABLE vision_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    -- JSON object: visual attributes observed in the image (objects, scene,
    -- colors, lighting, mood, composition, orientation, copy space).
    visual_attributes TEXT NOT NULL DEFAULT '{}',
    -- JSON array: commercial use ideas (AI suggestions, not guarantees).
    commercial_use_ideas TEXT NOT NULL DEFAULT '[]',
    -- JSON object: keyword gap analysis vs. existing metadata keywords.
    keyword_gap_analysis TEXT NOT NULL DEFAULT '{}',
    -- JSON object: metadata quality review (vague titles, repetitive keywords,
    -- unsupported terms, description accuracy).
    metadata_quality_review TEXT NOT NULL DEFAULT '{}',
    -- JSON array: actionable, image-specific recommendations.
    actionable_recommendations TEXT NOT NULL DEFAULT '[]',
    -- Model that produced this analysis (honesty: never guess).
    model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_vision_insights_asset ON vision_insights(asset_id);
CREATE INDEX idx_vision_insights_created_at ON vision_insights(created_at);
