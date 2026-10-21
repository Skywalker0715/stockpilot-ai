# Vision Insights endpoints: image analysis beyond Generate's metadata draft.
#
# POST /api/v1/vision/analyze/{asset_id}  -> run Cohere vision analysis and persist
# GET  /api/v1/vision/insights/{asset_id}  -> return latest persisted record

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app import db
from app.models import VisionInsightsRecordOut, VisionInsightsRequest
from app.services import cohere_service, vision_service

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.post(
    "/analyze/{asset_id}",
    response_model=VisionInsightsRecordOut,
    status_code=status.HTTP_201_CREATED,
)
def analyze_asset(
    asset_id: Annotated[int, Path(gt=0)],
    payload: VisionInsightsRequest,
    conn: DbDep,
) -> VisionInsightsRecordOut:
    """Analyze an uploaded image with Cohere vision and persist the result.

    Requires explicit consent. The asset's editable metadata is NOT changed;
    keyword suggestions from the gap analysis must be applied separately via
    PATCH /api/v1/assets/{id}.
    """
    if payload.asset_id != asset_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="asset_id in body must match the URL path",
        )
    try:
        return vision_service.analyze_and_persist(
            conn, asset_id=asset_id, consent=payload.consent
        )
    except cohere_service.CohereServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/insights/{asset_id}",
    response_model=VisionInsightsRecordOut,
)
def get_insights(
    asset_id: Annotated[int, Path(gt=0)],
    conn: DbDep,
) -> VisionInsightsRecordOut:
    """Return the most recent persisted vision-insights record for an asset."""
    record = vision_service.get_latest_insights(conn, asset_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No vision insights found for this asset",
        )
    return record
