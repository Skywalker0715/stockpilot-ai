# Image upload validation, storage, and safe serving (MVP core workflow).

import io

import pytest
from PIL import Image

from app import config


def _png_bytes(width: int = 4, height: int = 4, color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int = 4, height: int = 4) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def _webp_bytes(width: int = 4, height: int = 4) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (5, 150, 90)).save(buf, format="WEBP")
    return buf.getvalue()


def _upload(client, data: bytes, filename: str, content_type: str = "image/png"):
    return client.post(
        "/api/v1/uploads",
        files={"file": (filename, data, content_type)},
    )


# ---- happy path ------------------------------------------------------------


def test_upload_png_returns_201_with_asset_and_image_url(client, upload_dir):
    resp = _upload(client, _png_bytes(), "sunset.png")
    assert resp.status_code == 201
    body = resp.json()
    asset = body["asset"]
    assert asset["display_name"] == "sunset.png"
    assert asset["media_type"] == "image/png"
    assert asset["width"] == 4 and asset["height"] == 4
    assert asset["file_size"] > 0
    assert asset["image_url"] == f"/api/v1/images/{asset['id']}"
    # Metadata starts empty: the AI draft must never be auto-persisted.
    assert asset["title"] is None
    assert asset["keywords"] == []
    assert asset["metadata_origin"] == "manual"
    # File really exists in the app-managed directory (server-generated name).
    stored = list(upload_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].name == asset["stored_path"]
    assert stored[0].read_bytes() == _png_bytes()


def test_upload_jpeg_and_webp_accepted(client):
    for data, name, media in (
        (_jpeg_bytes(), "photo.jpg", "image/jpeg"),
        (_jpeg_bytes(), "photo.jpeg", "image/jpeg"),
        (_webp_bytes(), "art.webp", "image/webp"),
    ):
        resp = _upload(client, data, name, media)
        assert resp.status_code == 201, name
        assert resp.json()["asset"]["media_type"] == media


def test_image_serving_returns_stored_bytes(client):
    upload = _upload(client, _png_bytes(), "preview.png").json()
    resp = client.get(upload["image_url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content == _png_bytes()


# ---- validation rejects ----------------------------------------------------


def test_upload_rejects_disallowed_extension(client, upload_dir):
    resp = _upload(client, b"GIF89a...", "anim.gif", "image/gif")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "JPG" in detail or "extension" in detail.lower()
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_upload_rejects_extension_content_mismatch(client):
    # Real PNG bytes but named .jpg -> content must match extension.
    resp = _upload(client, _png_bytes(), "fake.jpg", "image/jpeg")
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "extension" in detail or "content" in detail


def test_upload_rejects_non_image_bytes_with_image_extension(client):
    resp = _upload(client, b"not an image at all" * 10, "bogus.png", "image/png")
    assert resp.status_code == 400


def test_upload_rejects_empty_file(client):
    resp = _upload(client, b"", "empty.png")
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_upload_rejects_oversize_file(client, monkeypatch):
    # 10-byte limit: any real PNG exceeds it, exercising the streaming cap.
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    resp = _upload(client, _png_bytes(width=64, height=64), "big.png")
    assert resp.status_code == 413
    assert "large" in resp.json()["detail"].lower()


def test_upload_requires_multipart_file(client):
    assert client.post("/api/v1/uploads").status_code == 422


def test_failed_upload_insert_removes_the_orphaned_file(client, upload_dir, monkeypatch):
    """If the DB insert fails after the image was written, the stored file
    must be removed — the managed directory must never keep orphan bytes
    that no asset row points to.
    """
    from app.services import asset_service

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(asset_service, "create_uploaded_asset", _boom)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        _upload(client, _png_bytes(), "orphan.png")

    # The upload failed...
    assert list(upload_dir.iterdir()) == []
    # ...and no asset row was created either.
    assert client.get("/api/v1/assets").json()["total"] == 0


# ---- serving safety --------------------------------------------------------


def test_serving_404_for_unknown_asset_and_for_record_only_asset(client):
    assert client.get("/api/v1/images/999999").status_code == 404
    created = client.post(
        "/api/v1/assets", json={"display_name": "record only"}
    ).json()
    resp = client.get(f"/api/v1/images/{created['id']}")
    assert resp.status_code == 404  # no stored image -> not served


def test_serving_never_escapes_upload_dir(client, upload_dir):
    """A poisoned stored_path must not read files outside UPLOAD_DIR."""
    import sqlite3

    secret = upload_dir.parent / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")
    upload = _upload(client, _png_bytes(), "ok.png").json()
    # Tamper with the DB directly (simulates corruption / injection).
    db_conn = sqlite3.connect(str(config.DB_PATH))
    db_conn.execute(
        "UPDATE assets SET stored_path = ? WHERE id = ?",
        ("../secret.txt", upload["asset"]["id"]),
    )
    db_conn.commit()
    db_conn.close()

    resp = client.get(upload["image_url"])
    assert resp.status_code == 404
    assert b"TOP SECRET" not in resp.content


def test_library_filter_has_image(client):
    """GET /assets?has_image=true returns only uploaded-image assets."""
    client.post("/api/v1/assets", json={"display_name": "record only"})
    client.post(
        "/api/v1/uploads",
        files={"file": ("a.png", _png_bytes(), "image/png")},
    )
    with_images = client.get("/api/v1/assets?has_image=true").json()
    assert with_images["total"] == 1
    assert with_images["items"][0]["image_url"] is not None
    without = client.get("/api/v1/assets?has_image=false").json()
    assert without["total"] == 1
    assert without["items"][0]["image_url"] is None
    # Default: unchanged behavior (all assets).
    assert client.get("/api/v1/assets").json()["total"] == 2


def test_library_archive_and_restore_flow(client, upload_dir):
    """The Library's Archive action (PATCH archived=true) hides the item
    from the Library without deleting anything; Unarchive restores it."""
    upload = _upload(client, _png_bytes(), "library.png").json()
    asset_id = upload["asset"]["id"]
    stored = upload_dir / upload["asset"]["stored_path"]

    def library():
        return client.get(
            "/api/v1/assets", params={"has_image": True}
        ).json()

    assert [item["id"] for item in library()["items"]] == [asset_id]

    # Archive: exactly what the Library card's Archive button sends.
    resp = client.patch(f"/api/v1/assets/{asset_id}", json={"archived": True})
    assert resp.status_code == 200
    assert resp.json()["archived"] is True

    # Hidden from the Library view, but nothing was deleted...
    assert library()["total"] == 0
    detail = client.get(f"/api/v1/assets/{asset_id}")
    assert detail.status_code == 200
    assert detail.json()["archived"] is True
    assert detail.json()["display_name"] == "library.png"  # metadata kept
    # ...the uploaded file survives and is still served.
    assert stored.exists()
    assert client.get(f"/api/v1/images/{asset_id}").status_code == 200

    # Restore through the Assets page flow: "Show archived" -> Unarchive.
    archived_list = client.get(
        "/api/v1/assets", params={"archived": True}
    ).json()
    assert [item["id"] for item in archived_list["items"]] == [asset_id]
    resp = client.patch(f"/api/v1/assets/{asset_id}", json={"archived": False})
    assert resp.status_code == 200
    assert resp.json()["archived"] is False
    assert [item["id"] for item in library()["items"]] == [asset_id]


def test_delete_asset_removes_stored_image_and_spares_others(client, upload_dir):
    keep = _upload(client, _png_bytes(), "keep.png").json()
    doomed = _upload(client, _png_bytes(color=(1, 2, 3)), "doomed.png").json()
    keep_path = upload_dir / keep["asset"]["stored_path"]
    doomed_path = upload_dir / doomed["asset"]["stored_path"]
    assert keep_path.exists() and doomed_path.exists()

    resp = client.delete(f"/api/v1/assets/{doomed['asset']['id']}")
    assert resp.status_code == 200
    assert resp.json()["image_removed"] is True
    # The doomed file is gone; the unrelated file is untouched.
    assert not doomed_path.exists()
    assert keep_path.exists()
    # Image serving reflects the deletion immediately.
    assert (
        client.get(f"/api/v1/images/{doomed['asset']['id']}").status_code == 404
    )
    assert client.get(f"/api/v1/images/{keep['asset']['id']}").status_code == 200


def test_delete_commits_even_when_file_removal_fails(client, upload_dir, monkeypatch):
    """File cleanup runs AFTER the DB commit; if it fails, the response must
    still report the deletion as done, with image_removed=false (honest)."""
    from app.services import storage_service

    upload = _upload(client, _png_bytes(), "stuck.png").json()
    asset_id = upload["asset"]["id"]
    stored = upload_dir / upload["asset"]["stored_path"]
    assert stored.exists()

    def _locked(name):
        raise PermissionError("file is locked by another process")

    monkeypatch.setattr(storage_service, "resolve_stored_path", _locked)

    resp = client.delete(f"/api/v1/assets/{asset_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["image_removed"] is False
    assert body["deleted_submissions"] == 0
    # The database deletion is committed regardless of the file failure...
    assert client.get(f"/api/v1/assets/{asset_id}").status_code == 404
    # ...and the file was left behind and reported, never silently dropped.
    assert stored.exists()


def test_draft_versus_save_metadata_flow(client, ai_key):
    """Upload -> draft handled client-side -> nothing saved until PATCH."""
    ai_key()  # configure AI; provider behavior is mocked in test_ai.py
    upload = _upload(client, _png_bytes(), "draft.png").json()
    asset_id = upload["asset"]["id"]

    # Simulate the frontend receiving a draft: it does NOT touch the server.
    asset = client.get(f"/api/v1/assets/{asset_id}").json()
    assert asset["title"] is None
    assert asset["keywords"] == []

    # Explicit save persists metadata and marks origin.
    resp = client.patch(
        f"/api/v1/assets/{asset_id}",
        json={
            "title": "Generated title",
            "description": "Generated description",
            "category": "Nature",
            "keywords": ["forest", "trees"],
            "metadata_origin": "ai_suggested",
        },
    )
    assert resp.status_code == 200
    saved = client.get(f"/api/v1/assets/{asset_id}").json()
    assert saved["title"] == "Generated title"
    assert saved["metadata_origin"] == "ai_suggested"
    # Image reference survived the metadata save.
    assert saved["image_url"] == f"/api/v1/images/{asset_id}"
    assert client.get(saved["image_url"]).status_code == 200
