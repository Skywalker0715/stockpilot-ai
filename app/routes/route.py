# endpoint /search

from fastapi import APIRouter, HTTPException, Header
from app.models import SearchRequest
from app.services.llm_service import call_llm
from app.services.maps import search_google_places
from app import config

router = APIRouter()

@router.post("/search")
async def search(req: SearchRequest, x_api_key: str | None = Header(None)):
    # API key check
    if config.ALLOWED_API_KEYS and (x_api_key not in config.ALLOWED_API_KEYS):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Call LLM
    prompt = f'User asked: "{req.query}". Extract a short search phrase for Google Places API. Return only the search text.'
    try:
        llm_out = await call_llm(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    search_text = llm_out.strip().split("\n")[0] or req.query

    # Call Google Maps (or fallback)
    try:
        places_resp = await search_google_places(search_text, req.location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Maps API failed: {e}")

    # 🔹 Fallback kalau API Key kosong
    if not config.GOOGLE_API_KEY:
        return {
            "query": req.query,
            "llm_search_text": search_text,
            "places": [
                {
                    "name": f"Hasil pencarian: {search_text}",
                    "address": None,
                    "place_id": None,
                    "lat": None,
                    "lng": None,
                    "iframe_src": None,
                    "maps_link": f"https://www.google.com/maps/search/?q={search_text.replace(' ', '+')}",
                }
            ],
            "embed_iframe": None
        }

    # 🔹 Normal case (pakai API Key Google Maps)
    results = places_resp.get("results", [])
    simplified = []
    for p in results[:10]:
        loc = p.get("geometry", {}).get("location", {})
        lat, lng = loc.get("lat"), loc.get("lng")
        iframe_src = f"https://www.google.com/maps/embed/v1/view?key={config.GOOGLE_API_KEY}&center={lat},{lng}&zoom=15" if lat and lng else None
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}" if lat and lng else None

        simplified.append({
            "name": p.get("name"),
            "address": p.get("formatted_address"),
            "place_id": p.get("place_id"),
            "lat": lat,
            "lng": lng,
            "iframe_src": iframe_src,
            "maps_link": maps_link,
        })

    embed_iframe = None
    if simplified:
        embed_iframe = f"<iframe width='600' height='450' style='border:0;' loading='lazy' allowfullscreen src='{simplified[0]['iframe_src']}'></iframe>"

    return {
        "query": req.query,
        "llm_search_text": search_text,
        "places": simplified,
        "embed_iframe": embed_iframe,
    }
