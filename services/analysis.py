import cv2
import numpy as np
import math
from PIL import Image
import io
import base64


# ─── HSV Color Ranges for Land Classification ────────────────────────────────

LAND_COLORS = {
    "vegetation": {
        "lower": np.array([35, 40, 40]),
        "upper": np.array([85, 255, 255]),
    },
    "open_land": {
        "lower": np.array([15, 20, 150]),
        "upper": np.array([35, 120, 255]),
    },
    "water": {
        "lower": np.array([90, 50, 50]),
        "upper": np.array([130, 255, 255]),
    },
    "urban": {
        "lower": np.array([0, 0, 80]),
        "upper": np.array([180, 30, 220]),
    },
}

TREES_PER_ACRE    = 500   # standard planting density
CO2_PER_TREE_KG   = 22      # kg CO2 absorbed per tree per year


# ─── Main Analysis Function ──────────────────────────────────────────────────

def analyze_satellite_image(image_bytes, lat, zoom=15):
    """
    Takes raw image bytes from Mapbox, runs HSV segmentation,
    returns a dict with land breakdown and afforestation estimates.
    """
    try:
        # Convert bytes → numpy array → OpenCV BGR image
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(pil_image)
        img_bgr   = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_hsv   = cv2.cvtColor(img_bgr,   cv2.COLOR_BGR2HSV)

        total_pixels = img_bgr.shape[0] * img_bgr.shape[1]

        # ── Segment each land type ──
        masks = {}
        pixel_counts = {}
        for land_type, ranges in LAND_COLORS.items():
            mask = cv2.inRange(img_hsv, ranges["lower"], ranges["upper"])
            masks[land_type]        = mask
            pixel_counts[land_type] = int(np.sum(mask > 0))

        # ── Pixels → real-world area ──
        mpp          = metres_per_pixel(lat, zoom)        # metres per pixel
        sqm_per_pixel = mpp ** 2                          # m² per pixel
        sqm_to_acres  = 0.000247105

        areas_acres = {
            k: round(v * sqm_per_pixel * sqm_to_acres, 4)
            for k, v in pixel_counts.items()
        }

        open_land_acres = areas_acres.get("open_land", 0)

        # ── Afforestation estimates ──
        trees_possible      = int(open_land_acres * TREES_PER_ACRE)
        co2_absorbed_kg_year = round(trees_possible * CO2_PER_TREE_KG, 2)

        # ── Percentage breakdown ──
        percentages = {
            k: round((v / total_pixels) * 100, 2)
            for k, v in pixel_counts.items()
        }

        return {
            "success":             True,
            "open_land_acres":     round(open_land_acres, 4),
            "trees_possible":      trees_possible,
            "co2_absorbed_kg_year": co2_absorbed_kg_year,
            "land_breakdown": {
                "vegetation_percent": percentages.get("vegetation", 0),
                "open_land_percent":  percentages.get("open_land", 0),
                "water_percent":      percentages.get("water", 0),
                "urban_percent":      percentages.get("urban", 0),
            },
            "image_size": {
                "width":  img_bgr.shape[1],
                "height": img_bgr.shape[0],
            },
        }, None

    except Exception as e:
        return None, f"Image analysis error: {str(e)}"


# ─── Save Debug Image (optional, helps visualize segmentation) ───────────────

def save_debug_image(image_bytes, output_path="debug_segmentation.png"):
    """
    Saves a color-coded segmentation overlay image for debugging.
    Green=vegetation, Yellow=open land, Blue=water, Gray=urban
    """
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(pil_image)
        img_bgr   = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_hsv   = cv2.cvtColor(img_bgr,   cv2.COLOR_BGR2HSV)

        overlay = img_bgr.copy()

        color_map = {
            "vegetation": (0,   200,   0),    # green
            "open_land":  (0,   255, 255),    # yellow
            "water":      (200,   0,   0),    # blue
            "urban":      (128, 128, 128),    # gray
        }

        for land_type, ranges in LAND_COLORS.items():
            mask    = cv2.inRange(img_hsv, ranges["lower"], ranges["upper"])
            color   = color_map[land_type]
            overlay[mask > 0] = color

        # Blend original + overlay
        blended = cv2.addWeighted(img_bgr, 0.4, overlay, 0.6, 0)
        cv2.imwrite(output_path, blended)
        return output_path

    except Exception as e:
        return f"Debug image error: {str(e)}"


# ─── Helper ──────────────────────────────────────────────────────────────────

def metres_per_pixel(lat, zoom):
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)



def generate_highlight_image(image_bytes):
    """
    Takes satellite image bytes, paints all open land pixels
    bright green, returns a Base64 encoded PNG string.
    """
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(pil_image)
        img_bgr   = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_hsv   = cv2.cvtColor(img_bgr,   cv2.COLOR_BGR2HSV)

        # Get open land mask
        mask = cv2.inRange(
            img_hsv,
            LAND_COLORS["open_land"]["lower"],
            LAND_COLORS["open_land"]["upper"]
        )

        # Create overlay — paint open land bright green
        overlay = img_bgr.copy()
        overlay[mask > 0] = (0, 220, 80)   # bright green in BGR

        # Blend original + overlay (60% original, 40% highlight)
        blended = cv2.addWeighted(img_bgr, 0.6, overlay, 0.4, 0)

        # Draw a green border around detected regions
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(blended, contours, -1, (0, 255, 80), 2)

        # Encode to Base64 PNG
        _, buffer = cv2.imencode('.png', blended)
        encoded   = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/png;base64,{encoded}", None

    except Exception as e:
        return None, f"Highlight image error: {str(e)}"