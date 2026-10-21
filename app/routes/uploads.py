# Image upload (multipart) and safe browser-facing image serving.

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import config, db
from app.models import AssetOut, ImageUploadOut
from app.services import asset_service, storage_service

router = APIRouter(prefix="/api/v1", tags=["uploads"])

DbDep = Annotated[sqlite3.Connection, Depends(db.get_connection)]


@router.post("/uploads", response_model=ImageUploadOut, status_code=201)
async def upload_image(file: Annotated[UploadFile, File(...)], conn: DbDep) -> ImageUploadOut:
    """Store a validated image and create its asset record.

    Validation: extension allow-list, magic bytes, size limit, and a full
    Pillow decode. Storage filenames are server-generated; the client's
    filename is kept only as display metadata.
    """
    # Enforce the size limit while streaming; never buffer an oversized file.
    limit = config.MAX_UPLOAD_BYTES
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            limit_mb = limit / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File is too large (limit {limit_mb:.1f} MB).",
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    try:
        validated = storage_service.validate_image(file.filename, data)
    except storage_service.UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    stored_name = storage_service.save_image(data, validated.extension)
    try:
        asset = asset_service.create_uploaded_asset(
            conn,
            original_filename=file.filename or stored_name,
            stored_path=stored_name,
            media_type=validated.media_type,
            width=validated.width,
            height=validated.height,
            file_size=len(data),
        )
    except Exception:
        # Roll back the stored file if the DB insert fails; never leave
        # orphan bytes in the managed directory.
        (config.UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        raise

    return ImageUploadOut(asset=asset, image_url=f"/api/v1/images/{asset.id}")


@router.get("/images/{asset_id}", response_class=FileResponse)
def serve_image(asset_id: int, conn: DbDep) -> FileResponse:
    """Serve an uploaded image for browser previews.

    The path comes from the database row (server-generated filename inside
    UPLOAD_DIR), never from the client. Anything else is a 404.
    """
    row = conn.execute(
        "SELECT stored_path, media_type FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if row is None or not row["stored_path"]:
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        path = storage_service.resolve_stored_path(row["stored_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(path, media_type=row["media_type"] or "application/octet-stream")
