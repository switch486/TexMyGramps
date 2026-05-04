#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus, urlencode

try:
    import requests
except ImportError:
    raise SystemExit("ERROR: requests is required. Install it with pip install requests.")


def get_env(key: str, default: str = None) -> str:
    if key in os.environ:
        return os.environ[key]
    return default


def required_env(key: str) -> str:
    value = get_env(key)
    if not value:
        raise SystemExit(f"ERROR: environment variable {key} is required")
    return value


def build_url(base_url: str, path_template: str, path_vars: dict = None, query: dict = None) -> str:
    base = base_url.rstrip("/")
    path = path_template.strip("/")
    if path_vars:
        escaped = {k: quote_plus(str(v)) for k, v in path_vars.items()}
        try:
            path = path.format(**escaped)
        except KeyError as exc:
            raise SystemExit(f"ERROR: missing path variable for URL template: {exc}")
    url = f"{base}/{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def fetch_json(url: str, headers: dict, timeout: int):
    print(f"Fetching JSON from: {url}")
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def persist_json(obj, dest_path: Path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    print(f"Saved JSON: {dest_path}")


def extract_handle(record: dict) -> str:
    for key in ("handle", "id", "uri", "guid"):
        value = record.get(key)
        if value:
            if key == "uri":
                return str(value).rstrip("/").split("/")[-1]
            return str(value)
    raise SystemExit("ERROR: record has no identifiable handle or id")


def clean_string(value: str) -> str:
    """Remove all trailing characters from string beginning with '['."""
    if not isinstance(value, str):
        return str(value)
    bracket_pos = value.find("[")
    if bracket_pos >= 0:
        return value[:bracket_pos].strip()
    return value.strip()


def find_single_person(person_id: str, search_path: str, query_param: str, headers: dict, timeout: int):
    url = build_url(os.environ["GRAMPS_API_BASE_URL"], search_path, query={query_param: person_id})
    data = fetch_json(url, headers, timeout)
    if isinstance(data, list):
        if not data:
            raise SystemExit(f"ERROR: no person found for {query_param}={person_id}")
        return data[0]
    if isinstance(data, dict):
        if "people" in data and isinstance(data["people"], list) and data["people"]:
            return data["people"][0]
        return data
    raise SystemExit("ERROR: unexpected person search response")


def fetch_detail(handle: str, path_template: str, headers: dict, timeout: int, query: dict = None):
    if not handle:
        raise SystemExit("ERROR: missing handle when fetching detail")
    url = build_url(os.environ["GRAMPS_API_BASE_URL"], path_template, {"handle": handle}, query=query)
    return fetch_json(url, headers, timeout)


def save_record(record: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    handle = extract_handle(record)
    dest_path = output_dir / f"{handle}.json"
    if dest_path.exists():
        return handle
    persist_json(record, dest_path)
    return handle


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_date_string(date_text: str) -> str:
    if not isinstance(date_text, str):
        return ""
    normalized = date_text.strip()
    # Handle YYYY-MM-DD -> YYYY.MM.DD
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", normalized):
        year, month, day = normalized.split("-")
        return f"{year}.{int(month):02d}.{int(day):02d}"
    # Handle DD.MM.YYYY -> YYYY.MM.DD
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", normalized):
        day, month, year = normalized.split(".")
        return f"{year}.{int(month):02d}.{int(day):02d}"
    return normalized


def parse_event_date(event: dict) -> str:
    date = event.get("date")
    if isinstance(date, dict):
        text = date.get("text") or date.get("format")
        if text:
            return normalize_date_string(str(text).strip())
        dateval = date.get("dateval")
        if isinstance(dateval, list) and len(dateval) >= 3:
            day, month, year = dateval[:3]
            if year and month and day:
                return f"{year}.{int(month):02d}.{int(day):02d}"
            if year:
                return str(year)
        if date.get("year"):
            return str(date.get("year"))
    return ""


def get_place_location(place_handle: str, config: dict, headers: dict, timeout: int) -> dict:
    if not place_handle:
        return {}
    place = fetch_detail(place_handle, config["place_detail_path"], headers, timeout)
    return place if isinstance(place, dict) else {}


def build_location_chain(place_handle: str, config: dict, headers: dict, timeout: int, visited: set = None) -> str:
    """Build a location chain by following place references via placeref_list."""
    if visited is None:
        visited = set()
    if not place_handle or place_handle in visited:
        return ""
    visited.add(place_handle)
    
    place_dict = get_place_location(place_handle, config, headers, timeout)
    if not isinstance(place_dict, dict):
        return ""
    
    # Extract current location name
    location_text = ""
    name_obj = place_dict.get("name")
    if isinstance(name_obj, dict):
        location_text = name_obj.get("value", "")
    if not location_text:
        location_text = place_dict.get("title") or place_dict.get("name") or ""
    # Clean bracketed characters
    location_text = clean_string(location_text)
    
    # Check for place references in placeref_list
    placeref_list = place_dict.get("placeref_list")
    if isinstance(placeref_list, list) and placeref_list:
        for placeref in placeref_list:
            if isinstance(placeref, dict):
                parent_handle = placeref.get("ref")
                if parent_handle:
                    parent_location = build_location_chain(parent_handle, config, headers, timeout, visited)
                    if parent_location:
                        return f"{location_text}, {parent_location}" if location_text else parent_location
    
    return location_text

def get_event_kind(event: dict) -> str:
    event_type = str(event.get("type", "")).lower()
    if "birth" in event_type:
        return "birth"
    if "death" in event_type:
        return "death"
    description = str(event.get("description", "")).lower()
    if "birth" in description:
        return "birth"
    if "death" in description:
        return "death"
    return ""


def enrich_person_birth_death(person: dict, config: dict, headers: dict, timeout: int, assets_dir: Path):
    if not isinstance(person, dict):
        return

    birth_date = ""
    death_date = ""
    birth_location = ""
    death_location = ""

    for event_ref in ensure_list(person.get("event_ref_list")):
        handle = None
        if isinstance(event_ref, dict):
            handle = event_ref.get("ref") or event_ref.get("handle")
        elif event_ref is not None:
            handle = str(event_ref)
        if not handle:
            continue

        event = fetch_detail(handle, config["event_detail_path"], headers, timeout)
        if not isinstance(event, dict):
            continue

        kind = get_event_kind(event)
        if kind not in ("birth", "death"):
            continue

        date_text = parse_event_date(event)
        location_text = ""
        place_dict = {}
        if event.get("place"):
            place_dict = get_place_location(str(event["place"]), config, headers, timeout)
            if isinstance(place_dict, dict):
                location_text = build_location_chain(str(event["place"]), config, headers, timeout)

        # Save event detail for inspection, but only for birth/death events.
        save_record(event, assets_dir / "events")
        # Save place detail if present
        if place_dict:
            save_record(place_dict, assets_dir / "places")

        if kind == "birth":
            if date_text:
                birth_date = birth_date or date_text
            if location_text:
                birth_location = birth_location or location_text
        elif kind == "death":
            if date_text:
                death_date = death_date or date_text
            if location_text:
                death_location = death_location or location_text

    if birth_date:
        person["birth_date"] = birth_date
    if birth_location:
        person["birth_location"] = birth_location
    if death_date:
        person["death_date"] = death_date
    if death_location:
        person["death_location"] = death_location


def main() -> None:
    parser = argparse.ArgumentParser(description="Load GRAMPS person data and related resources via API")
    parser.add_argument("--person-id", required=True, help="Gramps numerical person ID to resolve")
    parser.add_argument("--output", required=True, help="Primary output JSON file path")
    parser.add_argument("--assets-dir", required=True, help="Directory to store downloaded assets and JSON files")
    args = parser.parse_args()

    base_url = required_env("GRAMPS_API_BASE_URL")
    token = get_env("GRAMPS_API_TOKEN", "")
    timeout = int(get_env("GRAMPS_API_TIMEOUT", "30"))
    query_param = get_env("GRAMPS_API_PERSON_QUERY_PARAM", "gramps_id")
    person_search_path = get_env("GRAMPS_API_PERSON_SEARCH_PATH", "people")
    config = {
        "event_detail_path": get_env("GRAMPS_API_EVENT_DETAIL_PATH", "events/{handle}"),
        "place_detail_path": get_env("GRAMPS_API_PLACE_DETAIL_PATH", "places/{handle}"),
    }

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    assets_dir = Path(args.assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    person = find_single_person(args.person_id, person_search_path, query_param, headers, timeout)
    enrich_person_birth_death(person, config, headers, timeout, assets_dir)
    person_handle = save_record(person, assets_dir / "people")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    persist_json(person, output_path)

    print(f"Loaded person {person_handle} into {assets_dir}")


if __name__ == "__main__":
    main()
