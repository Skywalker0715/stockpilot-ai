# Insights summary: honest aggregates over recorded data only.

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app import db
from app.models import AiStatusOut, InsightsSummaryOut
from app.services import insights_service

router = APIRouter(prefix="/api/v1", tags=["insights"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.get("/insights/summary", response_model=InsightsSummaryOut)
def insights_summary(conn: DbDep) -> InsightsSummaryOut:
    return insights_service.summary(conn)


@router.get("/ai/status", response_model=AiStatusOut)
def ai_status() -> AiStatusOut:
    # The MVP ships without an AI provider (approved scope Q6).
    # This endpoint exists so the UI can state that honestly
    # instead of implying suggestions are available.
    return AiStatusOut(
        ai_configured=False,
        message=(
            "AI suggestions are not configured in this build. "
            "All metadata fields can be entered and edited manually."
        ),
    )
