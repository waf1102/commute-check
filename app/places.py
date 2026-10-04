"""Location search adapter. No API key required for non-commercial use."""

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/places", tags=["places"])
_cache = TTLCache(maxsize=200, ttl=86400)


@router.get("")
async def search_places(q: str = Query(min_length=2, max_length=120)):
    query = q.strip()
    if len(query) < 2:
        return []
    if query in _cache:
        return _cache[query]
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 6, "language": "en", "format": "json"},
            )
            response.raise_for_status()
        places = [
            {
                "name": ", ".join(
                    dict.fromkeys(
                        filter(None, [r["name"], r.get("admin1"), r.get("country")])
                    )
                ),
                "lat": r["latitude"],
                "lon": r["longitude"],
                "timezone": r.get("timezone", "UTC"),
            }
            for r in response.json().get("results", [])
        ]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            503, "Place search is unavailable. Try again or use your current location."
        ) from exc
    _cache[query] = places
    return places
