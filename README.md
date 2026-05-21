**Mapbox timeline integration**

- **What**: When rendering a person page the pipeline now extracts geo-coordinates from timeline events (when available) and writes a JSON file under `assets/map/<timeline_handle>.json`. Additionally, a static map image is generated and included in the LaTeX output.
- **Where**: `src/scripts/render_person_tex.py` writes both the JSON file and the static map image as part of the render flow.
- **Map loader**: A small helper `src/scripts/mapbox_loader.js` can initialize a Mapbox GL map and add markers from the generated JSON (for web applications).
- **LaTeX integration**: The static map is automatically included in the generated PDF on a new page titled "Mapa czasowa" (Polish for "Timeline Map").

Getting started

1. Create a token file at the project root or scripts directory. The script will automatically load from any of these locations:
   - `token.env` (project root)
   - `local.env` (project root)
   - `.env` (project root)
   - `api_token.env` (project root)
   - `gramps_api_token.env` (scripts directory)

Add your Mapbox token to any of these files:
```
MAPBOX_TOKEN=pk.your_mapbox_token_here
```

2. Install dependencies (if not already installed):
```
pip install -r requirements.txt
```

3. Run the renderer - it will automatically load the token from the `.env` file:
```
python3 src/scripts/render_person_tex.py --page-dir <page-dir>
```

The `.env` file loading is automatic—no need to `source` it manually anymore.

4. When generating a person page the JSON file and static map image will be created at:

```
<page-dir>/assets/map/<timeline_handle>.json
<page-dir>/assets/map/<timeline_handle>.png
```

5. The map will be automatically included in the LaTeX output on a new page. To render a map in an HTML page include Mapbox GL JS/CSS, inject the token into `window.MAPBOX_TOKEN` at build time or via a small inline script (do not commit your token), then include `src/scripts/mapbox_loader.js` and call:

```
initTimelineMap('map', '/path/to/assets/map/<timeline_handle>.json')
```

Debugging

Detailed logging is now included in the map processing pipeline. When running the renderer, look for log lines prefixed with `[MAP]` and `[ENV]` to debug:
- Environment: Shows which `.env` file was loaded
- Event extraction: Shows how many events were found and processed
- Place coordinate lookup: Shows which place files were loaded and their coordinates
- Feature collection: Shows the final number of features with coordinates
- Bounding box: Shows the padded bounds for the map
- Token check: Shows if MAPBOX_TOKEN was found in the environment
- Static map generation: Shows the API call to Mapbox static API
- Errors: Detailed error messages if something fails

Example output:
```
[ENV] Loading environment from /path/to/project/api_token.env
[MAP] Starting map JSON extraction...
[MAP] Found 'events' key in dict: 25 events
[MAP] Processing 25 events for geo-coordinates...
[MAP] Event 0 (Birth): place is dict with lat=52.2, lon=20.7
[MAP] Extracted 18 features with coordinates
[MAP] Bounds: lat [52.09, 52.22], lon [20.61, 20.81]
[MAP] Padded bbox: [20.61, 52.08, 20.81, 52.23]
[MAP] Successfully wrote map JSON to /path/to/assets/map/timeline.json
[MAP] Generating static map image...
[MAP] Found MAPBOX_TOKEN in environment (length: 128)
[MAP] Fetching static map from Mapbox API...
[MAP] Static map saved to /path/to/assets/map/timeline.png
```

Notes

- The generated JSON includes a `bbox` expanded slightly so `fitBounds` will leave a margin around markers.
- The loader uses `data.bbox` when present and falls back to computing bounds from markers.
- The script automatically loads from multiple possible `.env` file locations so you don't need to manually source them.
- If `MAPBOX_TOKEN` is not found in any `.env` file, map image generation is skipped but processing continues normally.
- The static map is centered on the bounding box with a default zoom level of 2.
- Your existing `api_token.env` will be automatically loaded if it contains `MAPBOX_TOKEN`.
