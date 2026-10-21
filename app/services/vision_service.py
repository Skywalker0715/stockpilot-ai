# Vision Insights persistence and analysis (image analysis beyond Generate).
#
# Calls Cohere vision for a structured analysis of an uploaded image and
# persists the result to the vision_insights table (additive migration 003).
# The asset's editable metadata is NOT touched here: keyword suggestions from
# the gap analysis are applied only when the user explicitly confirms them via
# PATCH /api/v1/assets/{id}.

import json
import sqlite3

from app import config, db
from app.models import VisionInsightsOut, VisionInsightsRecordOut
from app.services import cohere_service


def _row_to_record(row: sqlite3.Row) -> VisionInsightsRecordOut:
    return VisionInsightsRecordOut(
        id=row["id"],
        asset_id=row["asset_id"],
        visual_attributes=json.loads(row["visual_attributes"]),
        commercial_use_ideas=json.loads(row["commercial_use_ideas"]),
        keyword_gap_analysis=json.loads(row["keyword_gap_analysis"]),
        metadata_quality_review=json.loads(row["metadata_quality_review"]),
        actionable_recommendations=json.loads(row["actionable_recommendations"]),
        model=row["model"],
        created_at=row["created_at"],
    )


def analyze_and_persist(
    conn: sqlite3.Connection,
    *,
    asset_id: int,
    consent: bool,
) -> VisionInsightsRecordOut:
    """Run vision analysis on an asset's uploaded image and persist it.

    Returns the persisted record. Raises CohereServiceError (mapped to an HTTP
    error by the route) on provider/config failures, and ValueError when the
    asset or its image is missing.
    """
    if not consent:
        raise ValueError("consent is required to send the image to Cohere")

    row = conn.execute(
        "SELECT id, stored_path, media_type, keywords FROM assets WHERE id = ?",
        (asset_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"asset {asset_id} does not exist")
    if not row["stored_path"]:
        raise ValueError("This asset has no uploaded image to analyze.")

    from app.services import storage_service

    try:
        image_path = storage_service.resolve_stored_path(row["stored_path"])
        data = image_path.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(
            "The stored image file is missing. Upload the image again."
        ) from exc

    existing_keywords = json.loads(row["keywords"] or "[]")

    try:
        analysis = cohere_service.analyze_vision_insights(
            data,
            row["media_type"] or "image/jpeg",
            existing_keywords=existing_keywords,
        )
    except cohere_service.CohereServiceError:
        # Re-raise so the route can map it to the appropriate HTTP status.
        raise

    cur = conn.execute(
        """
        INSERT INTO vision_insights (
            asset_id, visual_attributes, commercial_use_ideas,
            keyword_gap_analysis, metadata_quality_review,
            actionable_recommendations, model
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        (
            asset_id,
            json.dumps(analysis["visual_attributes"], ensure_ascii=False),
            json.dumps(analysis["commercial_use_ideas"], ensure_ascii=False),
            json.dumps(analysis["keyword_gap_analysis"], ensure_ascii=False),
            json.dumps(analysis["metadata_quality_review"], ensure_ascii=False),
            json.dumps(analysis["actionable_recommendations"], ensure_ascii=False),
            config.AI_MODEL,
        ),
    )
    record = _row_to_record(cur.fetchone())
    conn.commit()
    return record


def get_latest_insights(
    conn: sqlite3.Connection, asset_id: int
) -> VisionInsightsRecordOut | None:
    """Return the most recent persisted vision-insights record for an asset,
    or None when none exists."""
    row = conn.execute(
        """
        SELECT * FROM vision_insights
        WHERE asset_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (asset_id,),
    ).fetchone()
    return _row_to_record(row) if row else None
