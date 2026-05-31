import requests
import os
from django.conf import settings

# ─── Place Lookup (Nominatim - 100% free, no key) ───────────────────────────

def get_coordinates(place_name):
    """Convert a place name to latitude/longitude using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1,
    }
    headers = {
        "User-Agent": "AirPollutionApp/1.0"   # Nominatim requires this
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return None, f"Place '{place_name}' not found."

        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        display_name = data[0]["display_name"]
        return {"lat": lat, "lon": lon, "display_name": display_name}, None

    except requests.exceptions.RequestException as e:
        return None, f"Nominatim error: {str(e)}"


# ─── Bounding Box (Nominatim) ────────────────────────────────────────────────

def get_bounding_box(place_name):
    """Get the bounding box of a place."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "AirPollutionApp/1.0"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return None, f"Place '{place_name}' not found."

        bbox = data[0]["boundingbox"]
        # bbox = [min_lat, max_lat, min_lon, max_lon]
        return {
            "min_lat": float(bbox[0]),
            "max_lat": float(bbox[1]),
            "min_lon": float(bbox[2]),
            "max_lon": float(bbox[3]),
        }, None

    except requests.exceptions.RequestException as e:
        return None, f"Bounding box error: {str(e)}"


# ─── Satellite Tile Fetch (Mapbox - free tier) ───────────────────────────────

def fetch_satellite_tile(lat, lon, zoom=15):
    """Fetch a satellite image tile from Mapbox Static API."""
    token = settings.MAPBOX_API_KEY

    if not token:
        return None, "Mapbox API key not configured."

    # Mapbox Static Images API
    url = (
        f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
        f"{lon},{lat},{zoom}/600x600?access_token={token}"
    )

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.content, None     # returns raw image bytes

    except requests.exceptions.RequestException as e:
        return None, f"Mapbox error: {str(e)}"


# ─── Helper: metres per pixel at given lat/zoom ─────────────────────────────

def metres_per_pixel(lat, zoom):
    """Accurate metres-per-pixel formula (varies with latitude)."""
    import math
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)