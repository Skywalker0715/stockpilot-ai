# Submission/review history persistence (FR-04, FR-05).

import sqlite3

from app.models import SubmissionCreate, SubmissionOut, SubmissionUpdate


def _row_to_submission(row: sqlite3.Row) -> SubmissionOut:
    return SubmissionOut(
        id=row["id"],
        asset_id=row["asset_id"],
        platform=row["platform"],
        status=row["status"],
        submitted_at=row["submitted_at"],
        reviewed_at=row["reviewed_at"],
        rejection_note=row["rejection_note"],
        rejection_category=row["rejection_category"],
        created_at=row["created_at"],
    )


class AssetNotFoundError(ValueError):
    """Raised when a submission references a missing asset."""


def create_submission(
    conn: sqlite3.Connection, data: SubmissionCreate
) -> SubmissionOut:
    asset = conn.execute(
        "SELECT id FROM assets WHERE id = ?", (data.asset_id,)
    ).fetchone()
    if asset is None:
        raise AssetNotFoundError(f"asset {data.asset_id} does not exist")
    cur = conn.execute(
        """
        INSERT INTO submissions (
            asset_id, platform, status, submitted_at, rejection_note, rejection_category
        ) VALUES (?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        (
            data.asset_id,
            data.platform,
            data.status.value,
            data.submitted_at,
            data.rejection_note,
            data.rejection_category,
        ),
    )
    row = cur.fetchone()
    conn.commit()
    return _row_to_submission(row)


def get_submission(conn: sqlite3.Connection, submission_id: int) -> SubmissionOut | None:
    row = conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    return _row_to_submission(row) if row else None


def list_submissions(
    conn: sqlite3.Connection,
    *,
    asset_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[SubmissionOut], int]:
    where: list[str] = []
    params: list[object] = []
    if asset_id is not None:
        where.append("asset_id = ?")
        params.append(asset_id)
    if status:
        where.append("status = ?")
        params.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) AS n FROM submissions {where_sql}", params
    ).fetchone()["n"]
    rows = conn.execute(
        f"""
        SELECT * FROM submissions {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return [_row_to_submission(r) for r in rows], total


def update_submission(
    conn: sqlite3.Connection, submission_id: int, data: SubmissionUpdate
) -> SubmissionOut | None:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_submission(conn, submission_id)

    columns: list[str] = []
    params: list[object] = []
    for key, value in fields.items():
        if key == "status" and value is not None:
            columns.append("status = ?")
            params.append(value.value if hasattr(value, "value") else value)
        else:
            columns.append(f"{key} = ?")
            params.append(value)
    params.append(submission_id)

    cur = conn.execute(
        f"UPDATE submissions SET {', '.join(columns)} WHERE id = ? RETURNING *",
        params,
    )
    row = cur.fetchone()
    conn.commit()
    return _row_to_submission(row) if row else None


def delete_submission(
    conn: sqlite3.Connection, submission_id: int
) -> SubmissionOut | None:
    """Permanently delete one submission record.

    Only this row is removed: the referenced asset, its image and metadata,
    and sibling submissions are untouched (submissions have no child rows).
    Returns None when the record does not exist.
    """
    submission = get_submission(conn, submission_id)
    if submission is None:
        return None
    conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
    conn.commit()
    return submission
