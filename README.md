# AirVerde — Air Quality & Afforestation Estimation Tool

A Django web application that analyses satellite imagery of any city to detect open/plantable land, estimate afforestation potential, and display real-time air quality data — all using free APIs.

---

## Table of Contents

- [What the project does](#what-the-project-does)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Setup & installation](#setup--installation)
- [API keys required](#api-keys-required)
- [How the map works](#how-the-map-works)
- [How empty areas are detected](#how-empty-areas-are-detected)
- [How plantation regions are chosen](#how-plantation-regions-are-chosen)
- [HSV colour ranges explained](#hsv-colour-ranges-explained)
- [Calculations explained](#calculations-explained)
- [API endpoints](#api-endpoints)
- [Database models](#database-models)
- [Limitations](#limitations)

---

## What the project does

1. User types any city name (e.g. "Kolkata", "Delhi", "Mumbai")
2. The app finds the coordinates using Nominatim (OpenStreetMap)
3. A satellite image of that location is fetched from Mapbox
4. OpenCV analyses the image and classifies every pixel as vegetation, open land, water, or urban
5. Open land pixels are highlighted in green on the satellite image — showing exactly where trees can be planted
6. Real-time AQI (air quality index) is fetched from WAQI for that city
7. Results are saved to the database and shown on the dashboard

---

## Tech stack

| Tool | Purpose | Cost |
|---|---|---|
| Django 4+ | Web framework, ORM, admin panel | Free |
| Django REST Framework | JSON API views | Free |
| Nominatim (OpenStreetMap) | City name to coordinates | Free, no key needed |
| Mapbox Static API | Satellite imagery tiles | Free tier (50k/month) |
| OpenCV + NumPy | Satellite image analysis | Free, open source |
| WAQI API | Real-time air quality data | Free key |
| SQLite | Database | Free |
| python-dotenv | Environment variable management | Free |

---

## Project structure

```
air_pollution_django/
├── config/
│   ├── settings.py         ← Django settings, loads .env keys
│   ├── urls.py             ← Root URL routing
│   └── wsgi.py
├── pollution/
│   ├── models.py           ← QueryLog and EstimationResult models
│   ├── views.py            ← All API views and AQI logic
│   ├── urls.py             ← App-level URL patterns
│   └── admin.py            ← Admin panel registration
├── services/
│   ├── maps.py             ← Nominatim place lookup + Mapbox tile fetch
│   └── analysis.py         ← OpenCV image processing and land detection
├── templates/
│   └── index.html          ← Frontend dashboard
├── logs/
│   └── .gitkeep
├── .env                    ← API keys (never commit this)
├── .gitignore
├── requirements.txt
└── manage.py
```

---

## Setup & installation

### Step 1 — Clone and create virtual environment

```bash
git clone <your-repo-url>
cd air_pollution_django
python -m venv venv
```

### Step 2 — Activate virtual environment

```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Create `.env` file

```
MAPBOX_API_KEY=your_mapbox_token_here
WAQI_API_KEY=your_waqi_token_here
```

### Step 5 — Run migrations

```bash
python manage.py migrate
```

### Step 6 — Create admin user

```bash
python manage.py createsuperuser
```

### Step 7 — Run the server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser.

---

## API keys required

### Mapbox (satellite imagery)
- Go to [mapbox.com](https://mapbox.com) and sign up — no credit card needed
- Copy the default public token from your account page
- Looks like: `pk.eyJ1IjoieW91cnVzZXJuYW1lIi...`

### WAQI (air quality data)
- Go to [aqicn.org/data-platform/token](https://aqicn.org/data-platform/token/)
- Enter name and email — token arrives by email instantly
- Looks like: `a1b2c3d4e5f6...`

### Nominatim (place lookup)
- No key needed — completely free, just requires a User-Agent header

---

## How the map works

The dashboard shows two side-by-side panels:

### Left panel — OpenStreetMap (location map)

This is a live interactive map embedded using an `<iframe>`. It is **not a static image** — it loads fresh from OpenStreetMap servers every time you search a city.

```javascript
// How the map URL is built in index.html
`https://www.openstreetmap.org/export/embed.html
 ?bbox=${lon-0.05},${lat-0.05},${lon+0.05},${lat+0.05}
 &layer=mapnik
 &marker=${lat},${lon}`
```

**How the visible area is decided:**

The `bbox` (bounding box) parameter controls how much area is shown around the city centre. The value `±0.05 degrees` means the map shows roughly 5–6 km in every direction, giving a ~10–12 km wide view of the city.

| Parameter | Value | Effect |
|---|---|---|
| `lon-0.05, lat-0.05` | South-west corner | Bottom-left of the map |
| `lon+0.05, lat+0.05` | North-east corner | Top-right of the map |
| `marker=lat,lon` | City centre | The orange pin |

To zoom in or out, change `0.05` in `index.html`:
- `±0.025` → neighbourhood level (~5 km wide)
- `±0.05` → district level (~10 km wide, default)
- `±0.10` → city level (~20 km wide)

The dark green colour is applied using a CSS filter:
```css
filter: invert(0.9) hue-rotate(140deg) saturate(0.7) brightness(0.85);
```
This inverts the map colours and shifts the hue to match the dashboard's green theme.

### Right panel — Mapbox satellite image

This is a **fixed 600×600 pixel PNG** fetched from Mapbox every time a city is searched. It shows the actual satellite view of the location.

```python
# In services/maps.py
url = (
    f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
    f"{lon},{lat},{zoom}/600x600?access_token={token}"
)
```

**How the visible area is decided:**

The area shown depends on the `zoom` level:

| Zoom level | Area covered | Best for |
|---|---|---|
| 13 | ~10 km wide | Whole city overview |
| 14 | ~5 km wide | Large district |
| 15 | ~2.6 km wide | Neighbourhood (default) |
| 16 | ~1.3 km wide | Street level |

The default zoom is 15, which gives a good balance between area coverage and pixel detail for OpenCV analysis.

---

## How empty areas are detected

The satellite image is analysed by OpenCV using **HSV colour segmentation**. HSV stands for Hue, Saturation, Value — a colour model that separates the actual colour (hue) from its brightness and vividness, making it more reliable than RGB for satellite images.

### Why HSV and not RGB?

In RGB, the same green field looks completely different in sunlight versus shadow. In HSV, the hue value stays consistent regardless of lighting conditions — making colour-based detection far more reliable across different cities, seasons, and times of day.

### The detection process step by step

1. The Mapbox PNG arrives as raw bytes
2. It is converted from bytes → PIL Image → NumPy array → OpenCV BGR format → HSV colour space
3. `cv2.inRange()` is applied four times — once for each land type — to create four binary masks
4. Each mask is a black-and-white image where white = that land type, black = not that land type
5. White pixels are counted and converted to real-world acres using the metres-per-pixel formula

```python
# The conversion in services/analysis.py
metres_per_pixel = 156543.03392 * cos(latitude_in_radians) / (2 ** zoom)
area_m2          = pixel_count * (metres_per_pixel ** 2)
area_acres       = area_m2 * 0.000247105
```

The formula accounts for latitude because map projections stretch near the poles — a pixel in London covers a different real-world distance than the same pixel in Chennai.

---

## How plantation regions are chosen

A pixel is marked as **plantable (open land)** if its HSV values fall within this specific range:

```python
"open_land": {
    "lower": np.array([15, 20, 150]),
    "upper": np.array([35, 120, 255]),
}
```

In plain English — the system looks for **bright, sandy, yellowish-brown pixels** that represent bare soil, empty plots, and dry open ground.

### Why these specific values?

| Channel | Range | Reason |
|---|---|---|
| Hue 15–35 | Yellow to yellow-orange | Bare soil and dry earth appear in this hue range on satellite images |
| Saturation 20–120 | Low to medium vivid | Excludes grey urban surfaces (too low S) and vivid coloured structures (too high S) |
| Value 150–255 | Bright only | Excludes shadowed areas that look dark even if they are open ground |

### What gets detected as plantable

- Bare soil and sandy ground
- Empty construction plots (before building)
- Dry open fields with no vegetation
- Unpaved open spaces between buildings
- Dry riverbanks and open floodplains

### What does NOT get detected as plantable

| Land type | HSV range | Why excluded |
|---|---|---|
| Existing trees/grass | H: 35–85 (greens) | Already has vegetation — no need to plant |
| Roads and buildings | H: 0–180, low S | Grey/concrete surfaces excluded by low saturation |
| Water bodies | H: 90–130 (blues) | Cannot plant trees in water |
| Shadowed areas | V below 150 | Too dark to classify reliably |

### The green highlight overlay

Once open land pixels are detected, they are visually highlighted on the satellite image:

```python
# In services/analysis.py — generate_highlight_image()
overlay[mask > 0] = (0, 220, 80)          # paint open land pixels bright green
blended = cv2.addWeighted(img, 0.6, overlay, 0.4, 0)  # 60% original, 40% green
contours, _ = cv2.findContours(mask, ...)
cv2.drawContours(blended, contours, -1, (0, 255, 80), 2)  # draw green outlines
```

The result is sent as a Base64-encoded PNG string in the API response and displayed directly in the browser — no file saving needed.

---

## HSV colour ranges explained

All four land types and their detection ranges:

| Land type | Hue | Saturation | Value | What it detects |
|---|---|---|---|---|
| Vegetation | 35–85 | 40–255 | 40–255 | Trees, grass, parks, gardens |
| Open land | 15–35 | 20–120 | 150–255 | Bare soil, empty plots, dry ground |
| Water | 90–130 | 50–255 | 50–255 | Rivers, lakes, ponds |
| Urban | 0–180 | 0–30 | 80–220 | Roads, concrete, rooftops |

**Hue reference (OpenCV uses 0–180):**
- 0–15: Red / brick
- 15–35: Yellow-orange / bare soil ← open land range
- 35–85: Yellow-green to green ← vegetation range
- 90–130: Cyan to blue ← water range
- 0–180 with low S: Grey tones ← urban range

---

## Calculations explained

### Trees possible
```
trees_possible = open_land_acres × TREES_PER_ACRE
```
`TREES_PER_ACRE = 450` — the number of trees that can be planted per acre of open land. This is a configurable constant in `services/analysis.py`.

### CO₂ absorbed per year
```
co2_absorbed_kg_year = trees_possible × CO2_PER_TREE_KG
```
`CO2_PER_TREE_KG = 21` — a mature tree absorbs approximately 21 kg of CO₂ per year on average (standard forestry estimate).

### Metres per pixel (latitude-adjusted)
```
mpp = 156543.03392 × cos(latitude in radians) / (2 ^ zoom)
```
This formula correctly accounts for Web Mercator projection distortion. Without latitude correction, area estimates would be inaccurate at any location other than the equator.

### Example for Delhi (lat 28.6°, zoom 15)
```
mpp   = 156543 × cos(28.6°) / 2^15 = 4.19 metres per pixel
area  = pixel_count × 4.19² m² per pixel
acres = area × 0.000247105
```

---

## API endpoints

| Method | URL | Description |
|---|---|---|
| GET | `/` | Frontend dashboard |
| POST | `/api/analyse/location/` | Analyse by city name |
| POST | `/api/analyse/coordinates/` | Analyse by lat/lon |
| GET | `/api/results/` | Last 10 saved results |
| GET | `/admin/` | Django admin panel |

### Example request — analyse by location

```bash
POST /api/analyse/location/
Content-Type: application/json

{ "place_name": "Kolkata" }
```

### Example response

```json
{
  "place": "Kolkata, West Bengal, India",
  "coordinates": { "lat": 22.5726, "lon": 88.3638 },
  "land_analysis": {
    "open_land_acres": 88.85,
    "trees_possible": 39983,
    "co2_absorbed_kg_year": 839643,
    "land_breakdown": {
      "vegetation_percent": 15.96,
      "open_land_percent": 5.13,
      "water_percent": 1.02,
      "urban_percent": 4.26
    }
  },
  "air_quality": {
    "aqi": 105.0,
    "category": "Unhealthy",
    "dominant_pollutant": "pm25"
  },
  "highlight_image": "data:image/png;base64,...",
  "saved_id": 1
}
```

---

## Database models

### QueryLog
Stores every search request.

| Field | Type | Description |
|---|---|---|
| id | AutoField | Primary key |
| place_name | CharField | Full display name from Nominatim |
| latitude | FloatField | Latitude coordinate |
| longitude | FloatField | Longitude coordinate |
| created_at | DateTimeField | Timestamp, auto-set |

### EstimationResult
Stores the analysis output, linked to QueryLog.

| Field | Type | Description |
|---|---|---|
| query | OneToOneField | Links to QueryLog |
| open_land_acres | FloatField | Plantable land in acres |
| trees_possible | IntegerField | Estimated trees that can be planted |
| co2_absorbed_kg_year | FloatField | Annual CO₂ absorption in kg |
| aqi | FloatField | PM2.5 air quality index value |
| aqi_category | CharField | Good / Moderate / Unhealthy / Hazardous |
| dominant_pollutant | CharField | Primary pollutant (pm25) |
| tiles_analyzed | IntegerField | Number of satellite tiles processed |
| created_at | DateTimeField | Timestamp, auto-set |

---

## Limitations

| Limitation | Explanation |
|---|---|
| Colour-based only | Detection relies on pixel colour, not ground truth. Rocky land and bare soil look similar. |
| Single tile | Only one 600×600 satellite tile is analysed per search — not the entire city |
| No land ownership data | Private and public land look identical on a satellite image |
| Seasonal variation | Dry season images show more "open land" than monsoon season images of the same place |
| Shadow confusion | Shadows from buildings can make urban areas appear as open land |
| Fixed zoom | Zoom level 15 gives neighbourhood-level detail — not suitable for whole-city analysis |
| AQI station coverage | If no WAQI station exists near the searched city, AQI shows as unavailable |

---

## Future improvements

- Use NDVI (Normalized Difference Vegetation Index) for more accurate vegetation detection
- Analyse multiple tiles to cover a larger city area
- Add land ownership layer using government open data
- Train a CNN model on labelled satellite images for pixel-level classification
- Add seasonal comparison (summer vs monsoon satellite images)
- Switch to PostgreSQL for production deployment
- Add Celery for async processing of large analysis requests

---

## License

This project is built entirely on free and open-source tools. All external API usage is subject to the respective provider's terms of service.
