# AI metadata generation: status disclosure + image analysis (draft only).

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app import config, db
from app.models import AiAnalyzeRequest, AiDraftOut, AiStatusOut
from app.services import cohere_service, storage_service

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.get("/status", response_model=AiStatusOut)
def ai_status() -> AiStatusOut:
    """Honest configuration disclosure: reflects whether COHERE_API_KEY is
    actually set right now, never a hardcoded claim either way."""
    if config.COHERE_API_KEY:
        return AiStatusOut(
            ai_configured=True,
            message=(
                f"AI metadata generation is enabled (model: "
                f"{config.AI_MODEL}). Images are sent to Cohere only "
                "when you click Generate."
            ),
            model=config.AI_MODEL,
        )
    return AiStatusOut(
        ai_configured=False,
        message=(
            "AI generation is not configured. Set COHERE_API_KEY in .env "
            "to enable it. All metadata fields can be entered and edited "
            "manually."
        ),
        model=None,
    )


@router.post("/analyze", response_model=AiDraftOut)
def analyze_image(payload: AiAnalyzeRequest, conn: DbDep) -> AiDraftOut:
    """Analyze the uploaded image with Cohere and return an unsaved draft.

    Persists NOTHING: the draft stays client-side until the user saves it
    through PATCH /api/v1/assets/{id}. Requires explicit consent.
    """
    row = conn.execute(
        "SELECT id, stored_path, media_type FROM assets WHERE id = ?",
        (payload.asset_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not row["stored_path"]:
        raise HTTPException(
            status_code=400,
            detail="This asset has no uploaded image to analyze.",
        )

    try:
        image_path = storage_service.resolve_stored_path(row["stored_path"])
        data = image_path.read_bytes()
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="The stored image file is missing. Upload the image again.",
        ) from None

    try:
        draft = cohere_service.analyze_image(
            data, row["media_type"] or "image/jpeg"
        )
    except cohere_service.CohereServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None

    return AiDraftOut(
        asset_id=payload.asset_id,
        title=draft["title"],
        description=draft["description"],
        category=draft["category"],
        keywords=draft["keywords"],
        model=config.AI_MODEL,
    )
