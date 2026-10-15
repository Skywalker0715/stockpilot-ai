# Submission/review history endpoints (FR-04, FR-05).

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app import db
from app.models import (
    SubmissionCreate,
    SubmissionListOut,
    SubmissionOut,
    SubmissionUpdate,
)
from app.services import submission_service

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.post("", response_model=SubmissionOut, status_code=201)
def create_submission(payload: SubmissionCreate, conn: DbDep) -> SubmissionOut:
    try:
        return submission_service.create_submission(conn, payload)
    except submission_service.AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc


@router.get("", response_model=SubmissionListOut)
def list_submissions(
    conn: DbDep,
    asset_id: Annotated[int | None, Query(gt=0)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SubmissionListOut:
    if status is not None and status not in (
        "draft",
        "submitted",
        "accepted",
        "rejected",
        "withdrawn",
        "unknown",
    ):
        raise HTTPException(status_code=422, detail="Invalid submission status")
    items, total = submission_service.list_submissions(
        conn, asset_id=asset_id, status=status, page=page, page_size=page_size
    )
    return SubmissionListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, conn: DbDep) -> SubmissionOut:
    submission = submission_service.get_submission(conn, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


@router.patch("/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: int, payload: SubmissionUpdate, conn: DbDep
) -> SubmissionOut:
    submission = submission_service.update_submission(
        conn, submission_id, payload
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission
