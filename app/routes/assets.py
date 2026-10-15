# Asset CRUD, search, filter, and archive endpoints (FR-01, FR-02).

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app import db
from app.models import AssetCreate, AssetListOut, AssetOut, AssetUpdate
from app.services import asset_service

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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AssetListOut:
    items, total = asset_service.list_assets(
        conn, q=q, category=category, archived=archived, page=page, page_size=page_size
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
