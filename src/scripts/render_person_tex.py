#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import re

LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "%": r"\%",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "{" : r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\^{}",
}


def latex_escape(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    return "".join(LATEX_SPECIAL_CHARS.get(ch, ch) for ch in value)


def clean_string(value: str) -> str:
    """Remove all trailing characters from string beginning with '['."""
    if not isinstance(value, str):
        return str(value)
    bracket_pos = value.find("[")
    if bracket_pos >= 0:
        return value[:bracket_pos].strip()
    return value.strip()


def build_location_chain(place_data: dict, places_dir: Path) -> str:
    """Build a location chain by following place references via placeref_list."""
    if not isinstance(place_data, dict):
        return ""
    
    # Extract current location name
    location_text = ""
    name_obj = place_data.get("name")
    if isinstance(name_obj, dict):
        location_text = name_obj.get("value", "")
    if not location_text:
        location_text = place_data.get("title") or place_data.get("name") or ""
    # Clean bracketed characters
    location_text = clean_string(location_text)
    
    # Check for place references in placeref_list
    placeref_list = place_data.get("placeref_list")
    if isinstance(placeref_list, list) and placeref_list:
        for placeref in placeref_list:
            if isinstance(placeref, dict):
                parent_handle = placeref.get("ref")
                if parent_handle:
                    parent_path = places_dir / f"{parent_handle}.json"
                    if parent_path.exists():
                        try:
                            parent_data = json.loads(parent_path.read_text(encoding="utf-8"))
                            parent_location = build_location_chain(parent_data, places_dir)
                            if parent_location:
                                return f"{location_text}, {parent_location}" if location_text else parent_location
                        except (ValueError, OSError):
                            pass
    
    return location_text


def name_parts(person: dict) -> tuple[str, str]:
    """Build a location chain by following place references via placeref_list."""
    if not isinstance(place_data, dict):
        return ""
    
    # Extract current location name
    location_text = ""
    name_obj = place_data.get("name")
    if isinstance(name_obj, dict):
        location_text = name_obj.get("value", "")
    if not location_text:
        location_text = place_data.get("title") or place_data.get("name") or ""
    
    # Check for place references in placeref_list
    placeref_list = place_data.get("placeref_list")
    if isinstance(placeref_list, list) and placeref_list:
        for placeref in placeref_list:
            if isinstance(placeref, dict):
                parent_handle = placeref.get("ref")
                if parent_handle:
                    parent_path = places_dir / f"{parent_handle}.json"
                    if parent_path.exists():
                        try:
                            parent_data = json.loads(parent_path.read_text(encoding="utf-8"))
                            parent_location = build_location_chain(parent_data, places_dir)
                            if parent_location:
                                return f"{location_text}, {parent_location}" if location_text else parent_location
                        except (ValueError, OSError):
                            pass
    
    return location_text


def name_parts(person: dict) -> tuple[str, str]:
    primary = person.get("primary_name", {})
    given = person.get("name_given") or primary.get("first_name") or primary.get("call") or ""
    surname = person.get("name_surname") or ""
    if not surname:
        surname_list = primary.get("surname_list") or []
        if isinstance(surname_list, list) and surname_list:
            parts = []
            for surname_part in surname_list:
                if not isinstance(surname_part, dict):
                    continue
                prefix = surname_part.get("prefix", "")
                surname_text = surname_part.get("surname", "")
                if prefix and surname_text:
                    parts.append(f"{prefix} {surname_text}".strip())
                elif surname_text:
                    parts.append(surname_text)
            surname = " ".join(parts)
    if not given and primary.get("display_as"):
        given = str(primary.get("display_as"))
    return clean_string(given).strip(), clean_string(surname).strip()


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


def extract_date_from_event(event: dict) -> str:
    if not isinstance(event, dict):
        return ""
    date = event.get("date") or {}
    dateval = date.get("dateval")
    if isinstance(dateval, list) and len(dateval) >= 3:
        day, month, year = dateval[:3]
        if year and month and day:
            return f"{year}.{int(month):02d}.{int(day):02d}"
        if year:
            return str(year)
    if isinstance(date, str) and date:
        return normalize_date_string(date.strip())
    description = event.get("description", "")
    if isinstance(description, str):
        return description.strip()
    return ""


def infer_birth_death_dates(page_dir: Path, person: dict) -> tuple[str, str, str, str]:
    birth_date = str(person.get("birth_date", "") or "").strip()
    birth_location = str(person.get("birth_location", "") or "").strip()
    death_date = str(person.get("death_date", "") or "").strip()
    death_location = str(person.get("death_location", "") or "").strip()

    if birth_date and birth_location and death_date and death_location:
        return birth_date, birth_location, death_date, death_location

    event_refs = person.get("event_ref_list", []) or []
    if isinstance(event_refs, list):
        events_dir = page_dir / "assets" / "events"
        places_dir = page_dir / "assets" / "places"
        for event_ref in event_refs:
            if not isinstance(event_ref, dict):
                continue
            handle = event_ref.get("ref")
            if not handle:
                continue
            event_path = events_dir / f"{handle}.json"
            if not event_path.exists():
                continue
            try:
                event_data = json.loads(event_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            event_type = str(event_data.get("type", "")).lower()
            date_value = extract_date_from_event(event_data)
            location_value = ""
            place_handle = event_data.get("place")
            if place_handle:
                place_path = places_dir / f"{place_handle}.json"
                if place_path.exists():
                    try:
                        place_data = json.loads(place_path.read_text(encoding="utf-8"))
                        location_value = build_location_chain(place_data, places_dir)
                    except (ValueError, OSError):
                        pass
            if "birth" in event_type:
                if not birth_date:
                    birth_date = date_value
                if not birth_location:
                    birth_location = location_value
            elif "death" in event_type:
                if not death_date:
                    death_date = date_value
                if not death_location:
                    death_location = location_value

    return birth_date, birth_location, death_date, death_location


def format_event_line(date_text: str, location_text: str) -> str:
    if date_text and location_text:
        return f"{date_text}, {location_text}"
    return date_text or location_text or ""


def render_tex(
    first_name: str,
    surname: str,
    birth_date: str,
    birth_location: str,
    death_date: str,
    death_location: str,
) -> str:
    title = latex_escape(first_name)
    surname_tex = latex_escape(surname)
    birth_tex = latex_escape(format_event_line(birth_date, birth_location))
    death_tex = latex_escape(format_event_line(death_date, death_location))

    return f"""% Auto-generated person page
\\documentclass[12pt]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{array}}
\\usepackage{{xcolor}}
\\usepackage{{ragged2e}}
\\newcommand{{\\birthsymbol}}{{\\ensuremath{{\\star}}}}
\\newcommand{{\\deathsymbol}}{{\\ensuremath{{\\dagger}}}}
\\begin{{document}}
\\thispagestyle{{empty}}
\\begin{{tabular}}{{@{{}}p{{0.38\\textwidth}} p{{0.58\\textwidth}}}}
  \\fbox{{\\parbox[c][4cm][c]{{\\linewidth}}{{\\centering \\textbf{{Photo}}\\newline (skipped)}}}} &
  \\begin{{minipage}}[t]{{\\linewidth}}
    \\vspace{{0pt}}
    \\Huge \\textbf{{{title}}}\\\\[0.3em]
    \\LARGE \\textbf{{{surname_tex}}}
  \\end{{minipage}} \\\\ 
\\end{{tabular}}

\\vspace{{1.5em}}
\\noindent
\\begin{{tabular}}{{@{{}}l l}}
  \\birthsymbol & \\textbf{{Data Narodzin:}} \\quad {birth_tex} \\\\ 
  \\deathsymbol & \\textbf{{Data Śmierci: }} \\quad {death_tex} \\\\ 
\\end{{tabular}}

\\end{{document}}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a simple LaTeX page from a person JSON file.")
    parser.add_argument("--page-dir", required=True, help="Page directory containing output/data.json and optional assets/events")
    parser.add_argument("--data-file", help="Person JSON data file path")
    parser.add_argument("--output-file", help="Output TeX file path")
    args = parser.parse_args()

    page_dir = Path(args.page_dir).resolve()
    if args.data_file:
        data_path = Path(args.data_file).resolve()
    else:
        data_path = page_dir / "output" / "data.json"
    if not data_path.exists():
        raise SystemExit(f"ERROR: person data not found: {data_path}")

    output_path = Path(args.output_file).resolve() if args.output_file else page_dir / "output" / "page.tex"

    try:
        person = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: could not load JSON data: {exc}")

    first_name, surname = name_parts(person)
    if not first_name and not surname:
        first_name = person.get("gramps_id", "Person")

    birth_date, birth_location, death_date, death_location = infer_birth_death_dates(page_dir, person)

    output_path.write_text(
        render_tex(
            first_name,
            surname,
            birth_date,
            birth_location,
            death_date,
            death_location,
        ),
        encoding="utf-8",
    )
    print(f"Rendered TeX to: {output_path}")


if __name__ == "__main__":
    main()
