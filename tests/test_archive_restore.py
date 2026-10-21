# Archive / restore round-trip, FK relationships, and persistence (FR-01/FR-02, NFR-05).
#
# Archive is a soft-delete (archived = 1): it must never remove the image file,
# metadata, or submission history. Restore is the symmetric PATCH archived = 0.
# Permanent deletion lives in tests/test_assets.py (DELETE /assets/{id}).

import io

from PIL import Image


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _create(client, name="Asset"):
    return client.post("/api/v1/assets", json={"display_name": name}).json()


def _upload(client):
    return client.post(
        "/api/v1/uploads",
        files={"file": ("img.png", _png_bytes(), "image/png")},
    ).json()


def test_archive_hides_and_unarchive_restores(client):
    a = _create(client, "Kept")
    b = _create(client, "ToArchive")

    resp = client.patch(f"/api/v1/assets/{b['id']}", json={"archived": True})
    assert resp.status_code == 200
    assert resp.json()["archived"] is True

    # Default list excludes archived records.
    active = client.get("/api/v1/assets").json()
    assert active["total"] == 1
    assert active["items"][0]["id"] == a["id"]

    # Archived-only list includes b.
    archived = client.get("/api/v1/assets", params={"archived": True}).json()
    assert archived["total"] == 1
    assert archived["items"][0]["id"] == b["id"]

    # Restore (unarchive) brings b back into the default list.
    resp = client.patch(f"/api/v1/assets/{b['id']}", json={"archived": False})
    assert resp.status_code == 200
    assert resp.json()["archived"] is False

    active = client.get("/api/v1/assets").json()
    assert active["total"] == 2


def test_archive_preserves_metadata_image_and_submissions(client, upload_dir):
    upload = _upload(client)
    asset_id = upload["asset"]["id"]
    image_url = upload["image_url"]
    stored_path = upload["asset"]["stored_path"]

    # Save metadata while active.
    client.patch(f"/api/v1/assets/{asset_id}", json={
        "title": "T",
        "description": "D",
        "category": "photo",
        "keywords": ["k1"],
        "metadata_origin": "ai_suggested",
    })
    # Add submission history while active.
    client.post("/api/v1/submissions", json={
        "asset_id": asset_id,
        "platform": "Adobe Stock",
        "status": "submitted",
        "submitted_at": "2026-10-01",
    })

    before = client.get(f"/api/v1/assets/{asset_id}").json()

    # Archive.
    client.patch(f"/api/v1/assets/{asset_id}", json={"archived": True})

    after = client.get(f"/api/v1/assets/{asset_id}").json()
    # Nothing is deleted: metadata, image reference, stored file, submissions intact.
    assert after["archived"] is True
    assert after["title"] == before["title"]
    assert after["description"] == before["description"]
    assert after["category"] == before["category"]
    assert after["keywords"] == before["keywords"]
    assert after["metadata_origin"] == before["metadata_origin"]
    assert after["image_url"] == image_url
    assert after["stored_path"] == stored_path
    assert (upload_dir / stored_path).exists()

    subs = client.get("/api/v1/submissions", params={"asset_id": asset_id}).json()
    assert subs["total"] == 1

    # Restore.
    client.patch(f"/api/v1/assets/{asset_id}", json={"archived": False})
    restored = client.get(f"/api/v1/assets/{asset_id}").json()
    assert restored["archived"] is False
    assert restored["title"] == "T"
    assert restored["image_url"] == image_url


def test_archived_asset_can_receive_submission(client):
    a = _create(client, "Archived")
    client.patch(f"/api/v1/assets/{a['id']}", json={"archived": True})
    resp = client.post("/api/v1/submissions", json={
        "asset_id": a["id"],
        "platform": "ShutterStock",
        "status": "draft",
    })
    assert resp.status_code == 201


def test_delete_asset_cascades_submissions_fk(client):
    doomed = _create(client, "Doomed")
    keeper = _create(client, "Keeper")
    for aid, plat in ((doomed["id"], "Adobe"), (keeper["id"], "Shutter")):
        client.post("/api/v1/submissions", json={
            "asset_id": aid, "platform": plat, "status": "submitted",
        })

    resp = client.delete(f"/api/v1/assets/{doomed['id']}")
    assert resp.status_code == 200
    assert resp.json()["deleted_submissions"] == 1
    assert client.get(f"/api/v1/assets/{doomed['id']}").status_code == 404
    assert client.get("/api/v1/submissions").json()["total"] == 1
    assert client.get(f"/api/v1/assets/{keeper['id']}").status_code == 200
    kept = client.get("/api/v1/submissions", params={"asset_id": keeper["id"]}).json()
    assert kept["total"] == 1
    assert kept["items"][0]["platform"] == "Shutter"
