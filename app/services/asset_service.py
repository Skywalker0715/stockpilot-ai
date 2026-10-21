# Asset catalog persistence and search (FR-01, FR-02).

import json
import sqlite3

from app.models import AssetCreate, AssetOut, AssetUpdate


def _row_to_asset(row: sqlite3.Row) -> AssetOut:
    stored_path = row["stored_path"]
    return AssetOut(
        id=row["id"],
        display_name=row["display_name"],
        file_reference=row["file_reference"],
        media_type=row["media_type"],
        title=row["title"],
        description=row["description"],
        keywords=json.loads(row["keywords"]),
        category=row["category"],
        metadata_origin=row["metadata_origin"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        stored_path=stored_path,
        original_filename=row["original_filename"],
        width=row["width"],
        height=row["height"],
        file_size=row["file_size"],
        # Browser-safe URL, only when an uploaded image actually exists.
        image_url=f"/api/v1/images/{row['id']}" if stored_path else None,
    )


def create_asset(conn: sqlite3.Connection, data: AssetCreate) -> AssetOut:
    cur = conn.execute(
        """
        INSERT INTO assets (
            display_name, file_reference, media_type, title, description,
            keywords, category, metadata_origin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')
        RETURNING *
        """,
        (
            data.display_name,
            data.file_reference,
            data.media_type,
            data.title,
            data.description,
            json.dumps(data.keywords, ensure_ascii=False),
            data.category,
        ),
    )
    row = cur.fetchone()
    conn.commit()
    return _row_to_asset(row)


def get_asset(conn: sqlite3.Connection, asset_id: int) -> AssetOut | None:
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return _row_to_asset(row) if row else None


def create_uploaded_asset(
    conn: sqlite3.Connection,
    *,
    original_filename: str,
    stored_path: str,
    media_type: str,
    width: int,
    height: int,
    file_size: int,
) -> AssetOut:
    """Create the asset row for a validated, already-stored image upload.

    Metadata fields start empty; the AI draft never lands here until the
    user explicitly saves.
    """
    display_name = original_filename[:200]
    cur = conn.execute(
        """
        INSERT INTO assets (
            display_name, media_type, stored_path, original_filename,
            width, height, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        (display_name, media_type, stored_path, original_filename, width, height, file_size),
    )
    row = cur.fetchone()
    conn.commit()
    return _row_to_asset(row)


def list_assets(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    category: str | None = None,
    archived: bool = False,
    has_image: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AssetOut], int]:
    where = ["archived = ?"]
    params: list[object] = [1 if archived else 0]
    if has_image is not None:
        # Library view: only assets with (or without) an uploaded image.
        where.append("stored_path IS NOT NULL" if has_image else "stored_path IS NULL")
    if category:
        where.append("category = ?")
        params.append(category)
    if q:
        # Simple case-insensitive contains over name/title/keywords/category.
        like = f"%{q.lower()}%"
        where.append(
            "(lower(display_name) LIKE ? OR lower(COALESCE(title, '')) LIKE ?"
            " OR lower(keywords) LIKE ? OR lower(COALESCE(category, '')) LIKE ?)"
        )
        params.extend([like, like, like, like])
    where_sql = " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) AS n FROM assets WHERE {where_sql}", params
    ).fetchone()["n"]
    rows = conn.execute(
        f"""
        SELECT * FROM assets WHERE {where_sql}
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return [_row_to_asset(r) for r in rows], total


def update_asset(
    conn: sqlite3.Connection, asset_id: int, data: AssetUpdate
) -> AssetOut | None:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_asset(conn, asset_id)

    columns: list[str] = []
    params: list[object] = []
    for key, value in fields.items():
        if key == "keywords":
            columns.append("keywords = ?")
            params.append(json.dumps(value, ensure_ascii=False))
        elif key == "archived":
            columns.append("archived = ?")
            params.append(1 if value else 0)
        else:
            columns.append(f"{key} = ?")
            params.append(value)
    columns.append("updated_at = datetime('now')")
    params.append(asset_id)

    cur = conn.execute(
        f"UPDATE assets SET {', '.join(columns)} WHERE id = ? RETURNING *", params
    )
    row = cur.fetchone()
    conn.commit()
    return _row_to_asset(row) if row else None


def delete_asset(
    conn: sqlite3.Connection, asset_id: int
) -> tuple[AssetOut, int, str | None] | None:
    """Permanently delete an asset row; linked submissions cascade via the FK.

    Returns (asset, linked_submission_count, stored_path) after committing, so
    the caller can remove the app-managed image file outside the transaction
    (file deletion is not transactional). Returns None when the asset does not
    exist. The submission count is read before the delete.
    """
    asset = get_asset(conn, asset_id)
    if asset is None:
        return None
    submission_count = conn.execute(
        "SELECT COUNT(*) AS n FROM submissions WHERE asset_id = ?", (asset_id,)
    ).fetchone()["n"]
    # FK submissions.asset_id -> assets(id) ON DELETE CASCADE, and every
    # connection sets PRAGMA foreign_keys = ON: linked submissions are
    # removed with the asset row in this statement.
    conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    conn.commit()
    return asset, submission_count, asset.stored_path
