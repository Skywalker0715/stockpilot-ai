# Asset CRUD, search, filter, and archive endpoints (FR-01, FR-02).

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app import db
from app.models import AssetCreate, AssetDeleteOut, AssetListOut, AssetOut, AssetUpdate
from app.services import asset_service, storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(payload: AssetCreate, conn: DbDep) -> AssetOut:
    return asset_service.create_asset(conn, payload)


@router.get("", response_model=AssetListOut)
def list_assets(
    conn: DbDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    archived: bool = False,
    has_image: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AssetListOut:
    items, total = asset_service.list_assets(
        conn,
        q=q,
        category=category,
        archived=archived,
        has_image=has_image,
        page=page,
        page_size=page_size,
    )
    return AssetListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, conn: DbDep) -> AssetOut:
    asset = asset_service.get_asset(conn, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, payload: AssetUpdate, conn: DbDep) -> AssetOut:
    asset = asset_service.update_asset(conn, asset_id, payload)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{asset_id}", response_model=AssetDeleteOut)
def delete_asset(asset_id: int, conn: DbDep) -> AssetDeleteOut:
    """Permanently delete an asset, its linked submissions (FK cascade), and
    its app-managed image file.

    The database deletion always commits first. If removing the stored file
    fails afterwards, the error is logged and image_removed is false — the
    response still reports success because the record deletion succeeded.
    """
    result = asset_service.delete_asset(conn, asset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset, submission_count, stored_path = result

    image_removed: bool | None = None
    if stored_path:
        image_removed = True
        try:
            # resolve_stored_path blocks anything outside UPLOAD_DIR.
            storage_service.resolve_stored_path(stored_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "Asset %s deleted, but stored image %s could not be removed: %s",
                asset_id,
                stored_path,
                exc,
            )
            image_removed = False

    return AssetDeleteOut(
        id=asset.id,
        display_name=asset.display_name,
        deleted_submissions=submission_count,
        image_removed=image_removed,
    )
