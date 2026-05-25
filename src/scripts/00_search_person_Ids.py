#!/usr/bin/env python3
import json
import os
import sys
import requests
from urllib.parse import quote_plus, urlencode


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def require_env(key: str) -> str:
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
            raise SystemExit(f"ERROR: missing path variable in URL template: {exc}")
    url = f"{base}/{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def fetch_json(url: str, headers: dict, timeout: int = 30):
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def extract_handle(record):
    if record is None:
        return ""
    if isinstance(record, str):
        return record
    if isinstance(record, dict):
        for key in ("handle", "id", "uri", "guid", "ref"):
            if key in record and record[key]:
                value = record[key]
                if key == "uri":
                    return str(value).rstrip("/").split("/")[-1]
                return str(value)
    return ""


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_name_record(name_record):
    if not isinstance(name_record, dict):
        return "", ""
    given = (
        name_record.get("first_name")
        or name_record.get("call")
        or name_record.get("display_as")
        or name_record.get("name_given")
        or name_record.get("given")
        or ""
    )
    surname = ""
    surname_list = name_record.get("surname_list") or []
    if isinstance(surname_list, list) and surname_list:
        parts = []
        for item in surname_list:
            if isinstance(item, dict):
                part = item.get("surname") or ""
            else:
                part = str(item)
            part = part.strip()
            if part:
                parts.append(part)
        surname = " ".join(parts)
    if not surname:
        surname = (
            name_record.get("surname")
            or name_record.get("name_surname")
            or name_record.get("last_name")
            or ""
        )
    return given.strip(), surname.strip()


def get_person_name(person):
    primary = person.get("primary_name") or person.get("name") or {}
    if isinstance(primary, str):
        return primary.strip(), ""
    given, surname = normalize_name_record(primary)
    if given or surname:
        return given, surname
    if isinstance(person.get("name"), dict):
        return normalize_name_record(person["name"])
    return person.get("display_name", ""), person.get("display_surname", "")


def get_event_type(record):
    if not isinstance(record, dict):
        return ""
    for key in ("type", "event_type", "eventType", "description"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""

def get_media_desc(record):
    if not isinstance(record, dict):
        return ""
    for key in ("description", "desc", "type"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def make_description(record):
    if not isinstance(record, dict):
        return ""
    description = (
        record.get("description")
        or record.get("value")
        or record.get("title")
        or record.get("name")
        or ""
    )
    return str(description).strip()


def get_hidden_gramps_id(record):
    if not isinstance(record, dict):
        return ""
    return str(
        record.get("gramps_id")
        or record.get("grampsID")
        or record.get("GrampsID")
        or ""
    ).strip()


def extract_linked_records(record, candidate_keys):
    if not isinstance(record, dict):
        return []
    for key in candidate_keys:
        if key in record:
            return ensure_list(record[key]) or []
    return []


def find_person(person_id, base_url, search_path, query_param, headers, timeout):
    url = build_url(base_url, search_path, query={query_param: person_id})
    data = fetch_json(url, headers, timeout)
    if isinstance(data, list):
        if not data:
            raise SystemExit(f"ERROR: no person found for {query_param}={person_id}")
        return data[0]
    if isinstance(data, dict):
        if "people" in data and isinstance(data["people"], list) and data["people"]:
            return data["people"][0]
        return data
    raise SystemExit("ERROR: unexpected person response type")


def find_media(media_id, base_url, search_path, headers, timeout):
    if not media_id:
        return {}
    url = build_url(base_url, search_path, path_vars={"handle": media_id})
    data = fetch_json(url, headers, timeout)
    if isinstance(data, list):
        return data[0] if data else {}
    if isinstance(data, dict):
        return data
    return {}


def find_note(note_id, base_url, search_path, headers, timeout):
    if not note_id:
        return {}
    url = build_url(base_url, search_path, path_vars={"handle": note_id})
    data = fetch_json(url, headers, timeout)
    if isinstance(data, list):
        return data[0] if data else {}
    if isinstance(data, dict):
        return data
    return {}


def find_event(handle, base_url, detail_path, headers, timeout):
    if not handle:
        return {}
    url = build_url(base_url, detail_path, path_vars={"handle": handle})
    data = fetch_json(url, headers, timeout)
    if isinstance(data, list):
        return data[0] if data else {}
    if isinstance(data, dict):
        return data
    return {}


def collect_gallery_objects(person, base_url, media_search_path, headers, timeout):
    gallery_keys = [
        "media_list",
    ]
    objects = []
    for key in gallery_keys:
        if key in person:
            items = ensure_list(person[key])
            for item in items:
                handle = extract_handle(item)
                if not handle:
                    continue
                hidden_id = get_hidden_gramps_id(item)
                if not hidden_id:
                    media = find_media(handle, base_url, media_search_path, headers, timeout)
                    hidden_id = get_hidden_gramps_id(media)
                objects.append(
                    {
                        "id": handle,
                        "gramps_id": hidden_id,
                        "description": get_media_desc(media) or "N/A",
                    }
                )
            if objects:
                return objects
    return []


def collect_event_links(event, base_url, media_search_path, note_search_path, headers, timeout):
    photo_keys = [
        "gallery",
        "media_ref_list",
        "media_list",
        "media",
        "media_object_list",
        "picture_ref_list",
        "picture_list",
    ]
    note_keys = [
        "note_ref_list",
        "note_list",
        "notes",
        "note",
        "note_ref",
    ]
    photos = []
    notes = []

    for item in extract_linked_records(event, photo_keys):
        handle = extract_handle(item)
        if handle:
            media = find_media(handle, base_url, media_search_path, headers, timeout)
            photos.append({"id": handle, "description": make_description(media) or "N/A"})

    for item in extract_linked_records(event, note_keys):
        handle = extract_handle(item)
        if handle:
            note = find_note(handle, base_url, note_search_path, headers, timeout)
            notes.append({"id": handle, "description": make_description(note) or "N/A"})

    return photos, notes


def get_person_events(person, base_url, detail_path, headers, timeout):
    event_refs = extract_linked_records(person, ["event_ref_list", "events", "event_list", "event_ref", "eventRefs"])
    events = []
    for ref in event_refs:
        handle = extract_handle(ref)
        if not handle:
            continue
        event = find_event(handle, base_url, detail_path, headers, timeout)
        events.append(
            {
                "id": handle,
                "gramps_id": get_hidden_gramps_id(event),
                "type": get_event_type(event) or "N/A",
                "photos": [],
                "notes": [],
            }
        )
    return events


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: 00_search_person_Ids.py <GrampsID>")

    person_id = sys.argv[1]
    base_url = require_env("GRAMPS_API_BASE_URL")
    token = require_env("GRAMPS_API_TOKEN")
    person_search_path = get_env("GRAMPS_API_PERSON_SEARCH_PATH", "people")
    person_query_param = get_env("GRAMPS_API_PERSON_QUERY_PARAM", "gramps_id")
    event_detail_path = get_env("GRAMPS_API_EVENT_DETAIL_PATH", "events/{handle}")
    media_search_path = "media/{handle}"
    note_search_path = "notes/{handle}"
    timeout = int(get_env("GRAMPS_API_TIMEOUT", "30"))

    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

    person = find_person(person_id, base_url, person_search_path, person_query_param, headers, timeout)
    person_hidden_id = get_hidden_gramps_id(person)
    person_name, person_surname = get_person_name(person)
    if not person_name and "personString" in person:
        person_name = str(person["personString"]).strip()

    
    print(f"\n-----------------------------")
    if person_hidden_id:
        print(f"Person gramps_id: {person_hidden_id}")
    print(f"Person name: {person_name or 'N/A'}")
    print(f"Person surname: {person_surname or 'N/A'}")
    print("")

    gallery_objects = collect_gallery_objects(
        person,
        base_url,
        media_search_path,
        headers,
        timeout,
    )
    print("Person gallery objects:")
    if gallery_objects:
        for obj in gallery_objects:
            if obj.get("gramps_id"):
                print(f"    gramps_id: {obj['gramps_id']}")
            print(f"    description: {obj['description']}")
    else:
        print("  (none found)")
    print("")

    print("Events:")
    events = get_person_events(person, base_url, event_detail_path, headers, timeout)
    if events:
        for event_item in events:
            if event_item.get("gramps_id"):
                print(f"    gramps_id: {event_item['gramps_id']}")
            print(f"    event type: {event_item['type']}")
            event_data = find_event(event_item["id"], base_url, event_detail_path, headers, timeout)
            photos, notes = collect_event_links(
                event_data,
                base_url,
                media_search_path,
                note_search_path,
                headers,
                timeout,
            )
            print("    photos:")
            if photos:
                for photo in photos:
                    handle = extract_handle(photo)   
                    media = find_media(handle, base_url, media_search_path, headers, timeout)
                    if media:
                        print(f"        gramps_id: {media['gramps_id']}")
                        print(f"        description: {media['desc']}")
            else:
                print("      (none found)")
            print("    notes:")
            if notes:
                for note in notes:

                    handle = extract_handle(note)  
                    note_data = find_note(handle, base_url, note_search_path, headers, timeout)

                    if note_data:
                        print(f"        gramps_id: {note_data['gramps_id']}")
                        print(f"        description: {note_data['text']['string']}")
            else:
                print("      (none found)")
    else:
        print("  (none found)")


if __name__ == "__main__":
    main()
