# Migrations must apply once, in order, and be idempotent (NFR-05).

from app import db

ALL_MIGRATIONS = [
    "001_initial.sql",
    "002_image_storage.sql",
    "003_vision_insights.sql",
]


def test_migrations_apply_once_and_are_idempotent(tmp_path):
    path = tmp_path / "mig.db"
    conn = db.connect(path)
    try:
        first = db.run_migrations(conn)
        assert first == ALL_MIGRATIONS

        second = db.run_migrations(conn)
        assert second == []  # already applied -> no-op

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"assets", "submissions", "schema_migrations", "vision_insights"} <= tables

        # 002 adds the image-storage columns additively.
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(assets)").fetchall()
        }
        assert {"stored_path", "original_filename", "width", "height", "file_size"} <= cols
    finally:
        conn.close()


def test_migration_preserves_existing_records(tmp_path):
    """A database populated before 002 keeps every record and gains the new
        columns as NULL and creates the additive insights table."""
    path = tmp_path / "legacy.db"
    conn = db.connect(path)
    try:
        # Simulate a pre-002 database: apply only 001, register it as
        # applied, and insert records.
        script = (db.MIGRATIONS_DIR / "001_initial.sql").read_text(encoding="utf-8")
        conn.executescript(script)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_migrations (name) VALUES ('001_initial.sql')"
        )
        conn.execute(
            """
            INSERT INTO assets (display_name, title, keywords, category)
            VALUES ('Legacy sunset', 'Sunset', '["sky"]', 'photo')
            """
        )
        conn.execute(
            """
            INSERT INTO submissions (asset_id, platform, status)
            VALUES (1, 'Adobe Stock', 'submitted')
            """
        )
        conn.commit()

        applied = db.run_migrations(conn)
        assert applied == ["002_image_storage.sql", "003_vision_insights.sql"]

        row = conn.execute("SELECT * FROM assets WHERE id = 1").fetchone()
        assert row["display_name"] == "Legacy sunset"
        assert row["title"] == "Sunset"
        assert row["stored_path"] is None  # no image yet
        sub = conn.execute("SELECT * FROM submissions WHERE id = 1").fetchone()
        assert sub["platform"] == "Adobe Stock"
    finally:
        conn.close()
