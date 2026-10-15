# Aggregates over user-recorded data only (PRD "Personal insights").
# No predictions, no causal claims: counts, sample size, and time range.

import sqlite3

from app.models import InsightsSummaryOut


def _count_map(conn: sqlite3.Connection, sql: str) -> dict[str, int]:
    return {row["k"]: row["n"] for row in conn.execute(sql).fetchall()}


def summary(conn: sqlite3.Connection) -> InsightsSummaryOut:
    totals = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM assets) AS total_assets,
            (SELECT COUNT(*) FROM assets WHERE archived = 1) AS archived_assets,
            (SELECT COUNT(*) FROM submissions) AS total_submissions
        """
    ).fetchone()

    by_status = _count_map(
        conn,
        "SELECT status AS k, COUNT(*) AS n FROM submissions GROUP BY status",
    )
    by_platform = _count_map(
        conn,
        "SELECT platform AS k, COUNT(*) AS n FROM submissions GROUP BY platform",
    )
    rejections_by_category = _count_map(
        conn,
        """
        SELECT COALESCE(rejection_category, 'uncategorized') AS k, COUNT(*) AS n
        FROM submissions WHERE status = 'rejected' GROUP BY rejection_category
        """,
    )
    period = conn.execute(
        "SELECT MIN(created_at) AS start, MAX(created_at) AS end FROM submissions"
    ).fetchone()

    # Sample size = submissions with an explicit submitted date (PRD: show sample size).
    sample = conn.execute(
        "SELECT COUNT(*) AS n FROM submissions WHERE submitted_at IS NOT NULL"
    ).fetchone()

    return InsightsSummaryOut(
        total_assets=totals["total_assets"],
        archived_assets=totals["archived_assets"],
        total_submissions=totals["total_submissions"],
        submissions_by_status=by_status,
        submissions_by_platform=by_platform,
        rejections_by_category=rejections_by_category,
        sample_size=sample["n"],
        period_start=period["start"],
        period_end=period["end"],
    )
