# Insights summary: honest aggregates over recorded data only.
# (AI status disclosure lives in routes/ai.py alongside generation.)

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app import db
from app.models import InsightsSummaryOut
from app.services import insights_service

router = APIRouter(prefix="/api/v1", tags=["insights"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.get("/insights/summary", response_model=InsightsSummaryOut)
def insights_summary(conn: DbDep) -> InsightsSummaryOut:
    return insights_service.summary(conn)

