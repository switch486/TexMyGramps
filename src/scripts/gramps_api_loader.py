#!/usr/bin/env python3
import argparse
import json
import os
import re
import requests
from pathlib import Path
from urllib.parse import quote_plus, urlencode

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


def extract_family_handle(record: dict) -> str:
    if record.get("parent_family_list"):
        value = record.get("parent_family_list")
        if value:
            # TODO - error handling TODO
            return str(value[0])
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


def find_single_person_by_handle(person_handle: str, headers: dict, timeout: int):
    path_template = f"people/{person_handle}"
    url = build_url(os.environ["GRAMPS_API_BASE_URL"], path_template)
    data = fetch_json(url, headers, timeout)
    if isinstance(data, list):
        if not data:
            raise SystemExit(f"ERROR: no person found for person_handle={person_handle}")
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


def fetch_person_timeline(person_handle: str, headers: dict, timeout: int) -> dict:
    """Fetch timeline data for a person from the API."""
    if not person_handle:
        return {}
    try:
        path_template = f"people/{person_handle}/timeline"
        url = build_url(os.environ["GRAMPS_API_BASE_URL"], path_template)
        return fetch_json(url, headers, timeout)
    except Exception as e:
        print(f"Warning: failed to fetch timeline for {person_handle}: {e}")
        return {}
    
def fetch_person_parent_family(family_handle: str, headers: dict, timeout: int) -> dict:
    """Fetch family data for a family_handle from the API."""
    if not family_handle:
        return {}
    try:
        path_template = f"families/{family_handle}"
        url = build_url(os.environ["GRAMPS_API_BASE_URL"], path_template)
        return fetch_json(url, headers, timeout)
    except Exception as e:
        print(f"Warning: failed to fetch timeline for {family_handle}: {e}")
        return {}


def enrich_person_timeline(person: dict, headers: dict, timeout: int, assets_dir: Path):
    """Fetch and save timeline data for a person."""
    if not isinstance(person, dict):
        return
    
    handle = extract_handle(person)
    timeline_data = fetch_person_timeline(handle, headers, timeout)
    
    if timeline_data:
        # Save timeline data for inspection
        timeline_path = assets_dir / "timeline" / f"{handle}.json"
        persist_json(timeline_data, timeline_path)
        # Store reference to timeline in person object
        person["timeline_handle"] = handle

def enrich_person_parent_family(person: dict, headers: dict, timeout: int, assets_dir: Path):
    """Fetch and save the parent family data for a person."""
    if not isinstance(person, dict):
        return
    
    family_handle = extract_family_handle(person)
    family_data = fetch_person_parent_family(family_handle, headers, timeout)
    
    if family_data:
        # Save family_data data for inspection
        family_path = assets_dir / "family" / f"{family_handle}.json"
        persist_json(family_data, family_path)

        # get Father
        fetch_parent(person, headers, timeout, assets_dir, family_data, "father_handle")

        # get Mother
        fetch_parent(person, headers, timeout, assets_dir, family_data, "mother_handle")

        # Store reference to family in person object
        person["family_handle"] = family_handle


def fetch_parent(person, headers, timeout, assets_dir, family_data, parent_handle_property):
    parent_handle = family_data.get(parent_handle_property)
    if not parent_handle:
        return {}
    try :
        parent_data = find_single_person_by_handle(parent_handle, headers, timeout)
        parent_path = assets_dir / "people" / f"{parent_handle}.json"
        persist_json(parent_data, parent_path)
        person[parent_handle_property] = parent_handle
    except Exception as e:
        print(f"Warning: failed to fetch parent data for {parent_handle}: {e}")
        return {}   

def load_media_details(media_ID: str, headers, timeout, assets_dir):
    try:
        query_param = get_env("GRAMPS_API_MEDIA_QUERY_PARAM", "gramps_id")
        search_path = get_env("GRAMPS_API_MEDIA_SEARCH_PATH", "media")
        url = build_url(os.environ["GRAMPS_API_BASE_URL"], search_path, query={query_param: media_ID})
        media_list = fetch_json(url, headers, timeout)
        if isinstance(media_list, list):
            media_data = media_list[0]
        else:
            media_data = {}
        save_record(media_data, assets_dir / "media")
        return media_data if isinstance(media_data, dict) else {}
    except Exception as e:
        print(f"Warning: failed to fetch media details for {media_ID}: {e}")
        return {}
    
def load_picture_details(handle: str, headers: dict, timeout: int, assets_dir: Path) -> dict:
    if not handle:
        return {}
    try:
        baseUrl = get_env("GRAMPS_API_BASE_URL")
        path = get_env("GRAMPS_API_PICTURE_PATH", "media/{handle}/file")
        url = build_url(baseUrl, path, path_vars={"handle": handle})
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        picture_path = assets_dir / f"pictures/{handle}.png"
        persist_picture(response.content, picture_path)

        return str(picture_path)
    except Exception as e:
        print(f"Warning: failed to fetch picture details for {handle}: {e}")
        return {}

def persist_picture(obj, dest_path: Path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, 'wb') as f:
        f.write(obj)  
    print(f"Saved Picture: {dest_path}")
    
def load_note_details(note_ID: str, headers: dict, timeout: int, assets_dir: Path) -> dict:
    if not note_ID:
        return {}
    try:
        query_param = get_env("GRAMPS_API_NOTE_QUERY_PARAM", "gramps_id")
        search_path = get_env("GRAMPS_API_NOTE_SEARCH_PATH", "notes")
        url = build_url(os.environ["GRAMPS_API_BASE_URL"], search_path, query={query_param: note_ID})
        note_list = fetch_json(url, headers, timeout)
        if isinstance(note_list, list):
            note_data = note_list[0]
        else:
            note_data = {}
        save_record(note_data, assets_dir / "notes")
        return note_data if isinstance(note_data, dict) else {}
    except Exception as e:
        print(f"Warning: failed to fetch note details for {note_ID}: {e}")
        return {}

def main() -> None:
    parser = argparse.ArgumentParser(description="Load GRAMPS person data and related resources via API")
    parser.add_argument("--source-file", required=True, help="Path to the source JSON file containing the work IDs")
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

    with open(args.source_file, "r") as f:
        task = json.load(f)

    person = find_single_person(task.get("personGrampsID"), person_search_path, query_param, headers, timeout)
    enrich_person_birth_death(person, config, headers, timeout, assets_dir)
    enrich_person_timeline(person, headers, timeout, assets_dir)
    enrich_person_parent_family(person, headers, timeout, assets_dir)
    person_handle = save_record(person, assets_dir / "people")

    if task.get("personPicture_mediaObjectID"):
        mediaDetails = load_media_details(task.get("personPicture_mediaObjectID"), headers, timeout, assets_dir)
        person["titlePagePhoto_link"] = load_picture_details(extract_handle(mediaDetails), headers, timeout, assets_dir)
    person["additional_page_details"] = load_additional_page_details(timeout, headers, assets_dir, task)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    persist_json(person, output_path)

    print(f"Loaded person {person_handle} into {assets_dir}")

def load_additional_page_details(timeout, headers, assets_dir, task):
    # loop over the detailPages in the tasks and collect the gramps IDs for the Media Objects and the Notes
    additional_page_details = []
    for pair in task.get("detailPages", []):
        mediaID = pair.get("mediaObjectID")
        noteID = pair.get("noteID")

        mediaDetails = load_media_details(mediaID, headers, timeout, assets_dir)
        pictureDetails = load_picture_details(extract_handle(mediaDetails), headers, timeout, assets_dir)
        output = {"mediaDetails": mediaDetails,
             "pictureDetails_link": pictureDetails}

        if noteID:
            noteDetails = load_note_details(noteID, headers, timeout, assets_dir)
            output["noteDetails"] = noteDetails

        additional_page_details.append(output)
             
    return additional_page_details


if __name__ == "__main__":
    main()
