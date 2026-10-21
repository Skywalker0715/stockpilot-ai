# One-off live smoke test against a running uvicorn (port from argv).
# Exercises: upload -> image serving -> analyze -> save -> reload -> library
# filter. Adapts to whether COHERE_API_KEY is configured. Exits non-zero on any
# failure.

import io
import sys

import httpx
from PIL import Image

BASE = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else '8017'}"
failures: list[str] = []

# A live Cohere call can take well over 30s, so the whole client needs a
# generous timeout; the fast local endpoints still return immediately.
TIMEOUT = 180.0


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


buf = io.BytesIO()
Image.new("RGB", (96, 72), (20, 140, 90)).save(buf, format="PNG")
png = buf.getvalue()

with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
    # 0. status honesty
    r = c.get("/api/v1/ai/status")
    check("GET /ai/status 200", r.status_code == 200, str(r.status_code))
    status = r.json()
    ai_configured = bool(status["ai_configured"])
    if ai_configured:
        check(
            "status reports configured",
            status["model"] is not None,
            str(status.get("model")),
        )
    else:
        check(
            "status not configured (no key)",
            status["ai_configured"] is False and "manually" in status["message"].lower(),
            status["message"][:60],
        )

    # 1. upload
    r = c.post(
        "/api/v1/uploads",
        files={"file": ("smoke.png", png, "image/png")},
    )
    check("POST /uploads 201", r.status_code == 201, str(r.status_code))
    if r.status_code != 201:
        print(r.text)
        sys.exit(1)
    body = r.json()
    asset = body["asset"]
    asset_id = asset["id"]
    image_url = body["image_url"]
    check("upload has image_url", image_url == f"/api/v1/images/{asset_id}")
    check("upload has dimensions", asset["width"] == 96 and asset["height"] == 72)
    check("metadata empty after upload", asset["title"] is None and asset["keywords"] == [])

    # 2. image serving
    r = c.get(image_url)
    check("GET image 200 image/png", r.status_code == 200 and r.headers["content-type"].startswith("image/png"))
    check("served bytes match upload", r.content == png)

    # 3. analyze: 503 + actionable message without a key, a real draft with one.
    r = c.post("/api/v1/ai/analyze", json={"asset_id": asset_id, "consent": True})
    if ai_configured:
        check("analyze with key => 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            draft = r.json()
            check(
                "draft has title + keywords",
                bool(draft.get("title")) and len(draft.get("keywords") or []) > 0,
                str(draft.get("title"))[:50],
            )
    else:
        check("analyze without key => 503", r.status_code == 503, str(r.status_code))
        check(
            "503 message actionable",
            "COHERE_API_KEY" in r.json()["detail"] and ".env" in r.json()["detail"],
            r.json()["detail"][:70],
        )
    # consent enforcement (would be masked by missing key only if checked later;
    # validation runs first, so expect 422)
    r = c.post("/api/v1/ai/analyze", json={"asset_id": asset_id, "consent": False})
    check("analyze without consent => 422", r.status_code == 422, str(r.status_code))

    # 4. draft-versus-save: analysis did NOT persist anything
    r = c.get(f"/api/v1/assets/{asset_id}")
    check("asset untouched by failed analyze", r.json()["title"] is None)

    # 5. explicit save
    r = c.patch(
        f"/api/v1/assets/{asset_id}",
        json={
            "title": "Green gradient abstract background",
            "description": "A smooth solid green field suitable as a background.",
            "category": "Abstract",
            "keywords": ["green", "background", "abstract", "green"],
            "metadata_origin": "ai_suggested",
        },
    )
    check("PATCH save 200", r.status_code == 201 or r.status_code == 200, str(r.status_code))
    saved = r.json()
    check("keywords deduped on save", saved["keywords"] == ["green", "background", "abstract"])
    check("origin recorded", saved["metadata_origin"] == "ai_suggested")

    # 6. reload (reopen from library)
    r = c.get(f"/api/v1/assets/{asset_id}")
    reloaded = r.json()
    check(
        "reload returns saved metadata + image",
        reloaded["title"] == "Green gradient abstract background"
        and reloaded["image_url"] == image_url,
    )

    # 7. library filter
    r = c.get("/api/v1/assets", params={"has_image": "true"})
    check(
        "library contains uploaded asset",
        any(i["id"] == asset_id for i in r.json()["items"]),
    )

    # 8. reject a bogus upload over the live server
    r = c.post(
        "/api/v1/uploads",
        files={"file": ("evil.gif", b"GIF89a-not-a-real-image", "image/gif")},
    )
    check("bogus .gif rejected 400", r.status_code == 400, str(r.status_code))

    # 9. clean up after ourselves so repeated runs leave no probe assets
    r = c.delete(f"/api/v1/assets/{asset_id}")
    check("cleanup delete 200", r.status_code == 200, str(r.status_code))
    r = c.get(f"/api/v1/assets/{asset_id}")
    check("asset gone after delete", r.status_code == 404, str(r.status_code))

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("LIVE SMOKE TEST: ALL PASS")
