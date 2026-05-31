from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests

from services.maps import get_coordinates, fetch_satellite_tile
from services.analysis import analyze_satellite_image
from .models import QueryLog, EstimationResult
from django.conf import settings

from django.shortcuts import render

from services.analysis import analyze_satellite_image, generate_highlight_image

import logging
logger = logging.getLogger(__name__)

# ─── AQI Helper ──────────────────────────────────────────────────────────────

def get_aqi(lat, lon, place_name=None):
    try:
        token = settings.WAQI_API_KEY

        # Extract short city keyword from place name
        # e.g. "Kolkata, West Bengal, India" → "Kolkata"
        keyword = "india"
        if place_name:
            keyword = place_name.split(",")[0].strip()

        # Search by city name
        search_url = f"https://api.waqi.info/search/?token={token}&keyword={keyword}"
        search_resp = requests.get(search_url, timeout=10)
        search_data = search_resp.json()

        if search_data.get("status") == "ok" and search_data.get("data"):
            for station in search_data["data"]:
                aqi_raw = station.get("aqi", "-")

                # Skip stations with no data
                if str(aqi_raw) == "-" or not str(aqi_raw).lstrip('-').isdigit():
                    continue

                aqi_value = float(aqi_raw)
                if aqi_value <= 0:
                    continue

                category, dominant = classify_aqi(aqi_value)
                station_name = station.get("station", {}).get("name", "Unknown")
                return aqi_value, category, f"pm25 ({station_name})"

        return None, None, "No AQI data found near this location."

    except Exception as e:
        return None, None, f"AQI error: {str(e)}"


def classify_aqi(pm25):
    if pm25 <= 12:
        return "Good", "pm25"
    elif pm25 <= 35.4:
        return "Moderate", "pm25"
    elif pm25 <= 55.4:
        return "Unhealthy for Sensitive Groups", "pm25"
    elif pm25 <= 150.4:
        return "Unhealthy", "pm25"
    elif pm25 <= 250.4:
        return "Very Unhealthy", "pm25"
    else:
        return "Hazardous", "pm25"


# ─── Shared Analysis Logic ────────────────────────────────────────────────────

def run_analysis(lat, lon, place_name=None):

    # Validate coordinates
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None, "Invalid coordinates provided.", 400

    # Step 1: Fetch satellite tile
    image_bytes, error = fetch_satellite_tile(lat, lon)
    if error:
        logger.error(f"Satellite fetch failed for {lat},{lon}: {error}")
        return None, error, 502

    # Step 2: Analyse image
    analysis, error = analyze_satellite_image(image_bytes, lat)
    if error:
        logger.error(f"Image analysis failed: {error}")
        return None, error, 500

    # Step 3: Generate highlighted image
    highlight_image, _ = generate_highlight_image(image_bytes)

    # Step 4: Get AQI
    aqi_value, aqi_category, aqi_msg = get_aqi(lat, lon, place_name=place_name)

    # Step 5: Save to database
    try:
        query = QueryLog.objects.create(
            place_name=place_name,
            latitude=lat,
            longitude=lon,
        )
        result = EstimationResult.objects.create(
            query=query,
            open_land_acres=analysis["open_land_acres"],
            trees_possible=analysis["trees_possible"],
            co2_absorbed_kg_year=analysis["co2_absorbed_kg_year"],
            aqi=aqi_value,
            aqi_category=aqi_category or "Unavailable",
            dominant_pollutant=aqi_msg if not aqi_value else "pm25",
            tiles_analyzed=1,
        )
    except Exception as e:
        logger.error(f"Database save failed: {e}")
        return None, "Failed to save result.", 500

    # Step 6: Return response
    data = {
        "place":       place_name or f"{lat}, {lon}",
        "coordinates": {"lat": lat, "lon": lon},
        "land_analysis": {
            "open_land_acres":       analysis["open_land_acres"],
            "trees_possible":        analysis["trees_possible"],
            "co2_absorbed_kg_year":  analysis["co2_absorbed_kg_year"],
            "land_breakdown":        analysis["land_breakdown"],
        },
        "air_quality": {
            "aqi":                aqi_value,
            "category":           aqi_category or "Unavailable",
            "dominant_pollutant": "pm25",
            "note":               aqi_msg if not aqi_value else None,
        },
        "highlight_image": highlight_image,
        "saved_id": result.id,
    }

    return data, None, 200

# ─── View 1: Search by Place Name ────────────────────────────────────────────

class AnalyseByLocationView(APIView):
    """
    POST /api/analyse/location/
    Body: { "place_name": "Kolkata" }
    """

    def post(self, request):
        place_name = request.data.get("place_name", "").strip()

        if not place_name:
            return Response(
                {"error": "place_name is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        coords, error = get_coordinates(place_name)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        lat = coords["lat"]
        lon = coords["lon"]

        data, error, code = run_analysis(lat, lon, place_name=coords["display_name"])

        if error:
            return Response({"error": error}, status=code)

        return Response(data, status=status.HTTP_200_OK)


# ─── View 2: Search by Coordinates ───────────────────────────────────────────

class AnalyseByCoordinatesView(APIView):
    """
    POST /api/analyse/coordinates/
    Body: { "lat": 22.5726, "lon": 88.3639 }
    """

    def post(self, request):
        try:
            lat = float(request.data.get("lat"))
            lon = float(request.data.get("lon"))
        except (TypeError, ValueError):
            return Response(
                {"error": "Valid lat and lon are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        data, error, code = run_analysis(lat, lon)

        if error:
            return Response({"error": error}, status=code)

        return Response(data, status=status.HTTP_200_OK)


# ─── View 3: Get Past Results ─────────────────────────────────────────────────

class ResultHistoryView(APIView):
    """
    GET /api/results/
    Returns last 10 saved results
    """

    def get(self, request):
        results = EstimationResult.objects.select_related("query").order_by("-created_at")[:10]

        data = []
        for r in results:
            data.append({
                "id":                   r.id,
                "place":                r.query.place_name or f"{r.query.latitude}, {r.query.longitude}",
                "open_land_acres":      r.open_land_acres,
                "trees_possible":       r.trees_possible,
                "co2_absorbed_kg_year": r.co2_absorbed_kg_year,
                "aqi":                  r.aqi,
                "aqi_category":         r.aqi_category,
                "created_at":           r.created_at.strftime("%Y-%m-%d %H:%M"),
            })

        return Response({"results": data}, status=status.HTTP_200_OK)
    

    # home view
class HomeView(APIView):
     def get(self, request):
        return render(request, 'index.html')