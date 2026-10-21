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
    # Date range and sample size describe the SAME set: only submissions
    # with an explicit submitted_at (NULL submitted_at rows are excluded
    # from both). No recorded dates -> count 0 and NULL bounds, reported
    # honestly rather than falling back to record-creation timestamps.
    dated = conn.execute(
        """
        SELECT COUNT(*) AS n,
               MIN(submitted_at) AS start,
               MAX(submitted_at) AS end
        FROM submissions
        WHERE submitted_at IS NOT NULL
        """
    ).fetchone()

    return InsightsSummaryOut(
        total_assets=totals["total_assets"],
        archived_assets=totals["archived_assets"],
        total_submissions=totals["total_submissions"],
        submissions_by_status=by_status,
        submissions_by_platform=by_platform,
        rejections_by_category=rejections_by_category,
        sample_size=dated["n"],
        period_start=dated["start"],
        period_end=dated["end"],
    )
