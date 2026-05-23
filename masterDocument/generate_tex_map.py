
import json
import glob
import argparse
import os
import requests
import math
from datetime import datetime
import traceback
from pathlib import Path
from typing import Optional

def _calculate_zoom(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    width: int,
    height: int,
    padding: int = 40,
) -> float:
    """
    Calculate optimal Mapbox zoom level to fit bbox into image.

    Uses Web Mercator approximation.
    """

    WORLD_DIM = 256
    ZOOM_MAX = 20

    # Prevent invalid bbox
    if min_lon == max_lon and min_lat == max_lat:
        return 14

    # Clamp latitude to Mercator limits
    min_lat = max(min_lat, -85.0511)
    max_lat = min(max_lat, 85.0511)

    def lat_rad(lat):
        sin_val = math.sin(lat * math.pi / 180)
        rad_x2 = math.log((1 + sin_val) / (1 - sin_val)) / 2
        return max(min(rad_x2, math.pi), -math.pi) / 2

    def zoom(map_px, world_px, fraction):
        if fraction == 0:
            return ZOOM_MAX
        return math.floor(math.log(map_px / world_px / fraction) / math.log(2))

    lat_fraction = (lat_rad(max_lat) - lat_rad(min_lat)) / math.pi

    lon_diff = max_lon - min_lon
    if lon_diff < 0:
        lon_diff += 360

    lon_fraction = lon_diff / 360

    usable_width = max(width - 2 * padding, 1)
    usable_height = max(height - 2 * padding, 1)

    lat_zoom = zoom(usable_height, WORLD_DIM, lat_fraction)
    lon_zoom = zoom(usable_width, WORLD_DIM, lon_fraction)

    return min(lat_zoom, lon_zoom, ZOOM_MAX)


def generate_static_map_png(
    map_data: dict,
    output_path: Path,
    mapbox_token: str,
    width: int = 700,
    height: int = 1000,
    zoom: int = None
) -> Optional[Path]:
    """Generate a static map image using Mapbox Static API.

    Args:
        map_data:
            Dictionary containing map configuration

        mapbox_token:
            Mapbox access token

        output_path:
            Path to save PNG

        width, height:
            Image dimensions

        zoom:
            Explicit zoom level (optional)

        points:
            Optional list of markers:
            [
                {
                    "lon": 13.4050,
                    "lat": 52.5200,
                    "color": "ff0000",   # optional
                    "size": "s"          # optional: s/m/l
                }
            ]

    Returns:
        Path to generated PNG or None on failure
    """

    print("[MAP] Generating static map image...")

    if not mapbox_token:
        print("[MAP] ERROR: No Mapbox token provided")
        return None

    try:
        min_lon, min_lat, max_lon, max_lat = map_data.get("bbox", [None] * 4)

        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        # AUTO CALCULATED ZOOM
        zoom = _calculate_zoom(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            width=width,
            height=height,
        )

        # Build marker overlays
        overlays = ""

        if isinstance(map_data["features"], list):
            marker_strings = []

        latest_by_coords = {}

        for feature in map_data.get("features", []):
            p = feature.get("geometry", {}).get("coordinates", [None, None])
            lon = p[0] if len(p) > 0 else None
            lat = p[1] if len(p) > 1 else None

            # skip invalid coordinates
            if lat is None or lon is None:
                continue

            coord_key = (lat, lon)

            date_str = (
                feature.get("properties", {}).get("date", "") or ""
            ).strip()

            parsed_date = parse_feature_date(date_str)

            existing = latest_by_coords.get(coord_key)

            # keep newest dated feature
            if existing is None:
                latest_by_coords[coord_key] = {
                    "feature": feature,
                    "date": parsed_date,
                    "date_str": date_str,
                }
            else:
                existing_date = existing["date"]

                # replace only if new date is newer
                if parsed_date and (
                    existing_date is None or parsed_date > existing_date
                ):
                    latest_by_coords[coord_key] = {
                        "feature": feature,
                        "date": parsed_date,
                        "date_str": date_str,
                    }

        # determine gradient range
        valid_dates = [
            item["date"]
            for item in latest_by_coords.values()
            if item["date"] is not None
        ]

        min_date = min(valid_dates) if valid_dates else None
        max_date = max(valid_dates) if valid_dates else None

        marker_strings = []

        for (lat, lon), item in latest_by_coords.items():
            parsed_date = item["date"]

            # empty/invalid date -> light blue
            if parsed_date is None:
                color = "87ceeb"
            else:
                color = interpolate_color(
                    parsed_date,
                    min_date,
                    max_date,
                    start_rgb=(0, 0, 0),   # black
                    end_rgb=(255, 0, 0),       # red
                )

            size = "s"

            marker = f"pin-{size}+{color}({lon},{lat})"
            marker_strings.append(marker)

        overlays = ",".join(marker_strings)

        # Build map position
        position = f"{center_lon},{center_lat},{zoom},0,0"

        # Build URL
        if overlays:
            url = (
                "https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/"
                f"{overlays}/"
                f"{position}/"
                f"{width}x{height}"
                f"?access_token={mapbox_token}"
            )
        else:
            url = (
                "https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/"
                f"{position}/"
                f"{width}x{height}"
                f"?access_token={mapbox_token}"
            )

        print(f"[MAP] Fetching static map: {url}")

        response = requests.get(
            url,
            timeout=10,
        )

        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        print(f"[MAP] Static map saved to {output_path}")

        return output_path

    except Exception as e:
        print(f"[MAP] ERROR: Failed to generate static map: {e}")
        traceback.print_exc()
        return None

def parse_feature_date(date_str):
    """
    Supports:
    - yyyy
    - yyyy-mm-dd
    - empty/invalid -> None
    """
    if not date_str:
        return None

    for fmt in ("%Y-%m-%d", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass

    return None


def interpolate_color(value, min_value, max_value, start_rgb, end_rgb):
    """
    Returns hex color string between start_rgb and end_rgb.
    """

    if min_value == max_value:
        ratio = 1.0
    else:
        ratio = (
            (value - min_value).total_seconds()
            / (max_value - min_value).total_seconds()
        )

    r = int(start_rgb[0] + ratio * (end_rgb[0] - start_rgb[0]))
    g = int(start_rgb[1] + ratio * (end_rgb[1] - start_rgb[1]))
    b = int(start_rgb[2] + ratio * (end_rgb[2] - start_rgb[2]))

    return f"{r:02x}{g:02x}{b:02x}"


def generate_tex_map_with_legend(map_data: dict, map_png_path: Path, output_tex_path: Path) -> Optional[Path]:
    """Generate a LaTeX page with map and legend (gradient + border years).
    
    Args:
        map_data: GeoJSON-like data with features and bbox
        map_png_path: Path to the generated PNG map
        output_tex_path: Path to save the LaTeX file
    
    Returns:
        Path to generated LaTeX file or None on failure
    """
    
    print("[MAP] Generating LaTeX map page with legend...")
    
    try:
        # Extract date range from features
        valid_dates = []
        
        for feature in map_data.get("features", []):
            date_str = (feature.get("properties", {}).get("date", "") or "").strip()
            parsed_date = parse_feature_date(date_str)
            if parsed_date:
                valid_dates.append(parsed_date)
        
        if not valid_dates:
            min_date = None
            max_date = None
            min_year = "?"
            max_year = "?"
        else:
            min_date = min(valid_dates)
            max_date = max(valid_dates)
            min_year = min_date.strftime("%Y")
            max_year = max_date.strftime("%Y")
        
        print(f"[MAP] Date range: {min_year} - {max_year}")
        
        # Generate gradient boxes for legend (10 steps from black to red)
        gradient_steps = 10
        gradient_boxes = []
        
        for i in range(gradient_steps):
            ratio = i / (gradient_steps - 1) if gradient_steps > 1 else 0
            r = int(0 + ratio * (255 - 0))
            g = int(0 + ratio * (0 - 0))
            b = int(0 + ratio * (0 - 0))
            color_hex = f"{r:02x}{g:02x}{b:02x}"
            gradient_boxes.append(f"\\colorbox[HTML]{{{color_hex}}}{{\\phantom{{W}}}}")
        
        gradient_tex = " ".join(gradient_boxes)
        
        # Get relative path to map PNG (from masterDocument directory)
        rel_map_path = map_png_path.name  # just the filename since it's in output/
        
        # Generate LaTeX content
        tex_content = f"""% Auto-generated map page with legend
\\newpage
\\begin{{center}}
Chronologiczna mapa zdarzeń zawartych w kronice.
\\vspace{{1.5em}}
    \\includegraphics[width=\\textwidth, height=0.90\\textheight, keepaspectratio]{{output/{rel_map_path}}}
\\end{{center}}

\\centerline{{ \\textbf{{{min_year}}}   \\large{{{gradient_tex}}}  \\textbf{{{max_year}}}}}

\\newpage
"""
        
        output_tex_path.parent.mkdir(parents=True, exist_ok=True)
        output_tex_path.write_text(tex_content, encoding="utf-8")
        
        print(f"[MAP] LaTeX map page saved to {output_tex_path}")
        return output_tex_path
        
    except Exception as e:
        print(f"[MAP] ERROR: Failed to generate LaTeX map page: {e}")
        traceback.print_exc()
        return None


def load_merged_map(outputFilepath):
    
    # Try to generate static map image and LaTeX page
    try:
        map_data = json.loads(outputFilepath.read_text(encoding="utf-8"))
        if map_data:
            # Try to get Mapbox token from environment
            mapbox_token = os.environ.get("MAPBOX_TOKEN")
            if mapbox_token:
                print(f"[MAP] Found MAPBOX_TOKEN in environment (length: {len(mapbox_token)})")

                root_dir = Path(__file__).resolve().parent.parent
                map_png_path = root_dir / "masterDocument" / "output" / "merged_map.png"
                map_tex_path = root_dir / "masterDocument" / "output" / "merged_map.tex"
                
                # Generate PNG map
                generate_static_map_png(map_data, map_png_path, mapbox_token)
                
                # Generate LaTeX page with legend
                generate_tex_map_with_legend(map_data, map_png_path, map_tex_path)
            else:
                print("[MAP] WARNING: MAPBOX_TOKEN not found in environment")
    except Exception as e:
        print(f"[MAP] Warning: Could not generate static map image: {e}")

def main():
    outputFilepath = merge_map_jsons()
    load_merged_map(outputFilepath)

def merge_map_jsons():
    parser = argparse.ArgumentParser(
        description="Merge GeoJSON map files into a single output file."
    )
    parser.add_argument(
        "stage",
        nargs="?",
        default="",
        help="Optional stage suffix used in src/pages_<stage>/...",
    )

    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    print(f"Root directory: {root_dir}")

    pages_dir = f"pages_{args.stage}" if args.stage else "pages"

    # Keep "map" strictly in the path, but allow flexible substructure under it
    pattern = str(
        root_dir
        / "src"
        / pages_dir
        / "page*"
        / "assets"
        / "map"
        / "*.json"
    )

    files = glob.glob(pattern, recursive=True)

    print(f"Found {len(files)} map files to merge.")

    merged = {
        "type": "FeatureCollection",
        "features": [],
    }

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if isinstance(data, dict) and "features" in data:
            merged["features"].extend(data.get("features", []))

            bbox = data.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4:
                min_x = min(min_x, bbox[0])
                min_y = min(min_y, bbox[1])
                max_x = max(max_x, bbox[2])
                max_y = max(max_y, bbox[3])

    if merged["features"] and min_x != float("inf"):
        merged["bbox"] = [min_x, min_y, max_x, max_y]

    output_dir = root_dir / "masterDocument" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "merged_map.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Merged {len(files)} files into: {output_file}")
    return output_file


if __name__ == "__main__":
    main()