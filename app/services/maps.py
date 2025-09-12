# function communication  to Google Maps API

import httpx
from app import config

async def search_google_places(query: str, location: str | None = None):
    # Kalau API Key kosong -> fallback ke share link Google Maps
    if not config.GOOGLE_API_KEY:
        return {
            "results": [
                {
                    "name": f"Hasil pencarian: {query}",
                    "formatted_address": None,
                    "geometry": {"location": {"lat": None, "lng": None}},
                    "place_id": None,
                    "maps_link": f"https://www.google.com/maps/search/?q={query.replace(' ', '+')}"
                }
            ]
        }

    # Normal case -> panggil Google Places API
    base = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": config.GOOGLE_API_KEY}
    if location:
        params["location"] = location
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(base, params=params)
        r.raise_for_status()
        return r.json()

