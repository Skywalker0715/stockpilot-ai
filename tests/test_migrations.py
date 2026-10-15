# Migrations must apply once, in order, and be idempotent (NFR-05).

from app import db


def test_migrations_apply_once_and_are_idempotent(tmp_path):
    path = tmp_path / "mig.db"
    conn = db.connect(path)
    try:
        first = db.run_migrations(conn)
        assert first == ["001_initial.sql"]

        second = db.run_migrations(conn)
        assert second == []  # already applied -> no-op

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"assets", "submissions", "schema_migrations"} <= tables
    finally:
        conn.close()
