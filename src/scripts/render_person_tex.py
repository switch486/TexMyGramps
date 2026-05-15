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

def create_full_name(person: dict) -> str:
    primary_name = person.get("primary_name") or {}
    alternate_names = person.get("alternate_names") or []

    primary_type, primary_given, primary_surname = name_parts(primary_name)

    alternate_type = alternate_given = alternate_surname = ""
    if isinstance(alternate_names, dict):
        alternate_type, alternate_given, alternate_surname = name_parts(alternate_names)
    elif isinstance(alternate_names, list) and alternate_names:
        alternate_type, alternate_given, alternate_surname = name_parts(alternate_names[0])

    if primary_type == "Married Name" and alternate_type == "Birth Name":
        return f"{primary_given} {primary_surname} (z domu {alternate_surname})".strip()
    elif alternate_type == "Married Name" and primary_type == "Birth Name":
        return f"{alternate_given} {alternate_surname} (z domu {primary_surname})".strip()
    return f"{primary_given} {primary_surname}".strip()
    
def name_parts(name_record: dict) -> tuple[str, str, str]:
    given = name_record.get("first_name") or name_record.get("call") or ""
    surname = ""
    surname_list = name_record.get("surname_list") or []
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
    if not given and name_record.get("display_as"):
        given = str(name_record.get("display_as"))
    return name_record.get("type"), clean_string(given).strip(), clean_string(surname).strip()






def extract_occupations(person: dict) -> str:
    """Extract occupations from attribute_list and join them with commas."""
    occupations = []
    attribute_list = person.get("attribute_list", []) or []
    if isinstance(attribute_list, list):
        for attr in attribute_list:
            if isinstance(attr, dict) and attr.get("type") == "Occupation":
                value = attr.get("value", "").strip()
                if value:
                    occupations.append(value)
    return ", ".join(occupations)


def load_timeline_data(page_dir: Path, person: dict) -> dict:
    """Load timeline data from JSON file if available."""
    timeline_handle = person.get("timeline_handle")
    if not timeline_handle:
        return {}
    
    timeline_path = page_dir / "assets" / "timeline" / f"{timeline_handle}.json"
    if timeline_path.exists():
        try:
            return json.loads(timeline_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {}



def load_person_data(page_dir: Path, person: dict, handle: str) -> dict:
    """Load person data from JSON file if available."""
    person_handle = person.get(handle)
    if not person_handle:
        return {}
    
    person_path = page_dir / "assets" / "people" / f"{person_handle}.json"
    if person_path.exists():
        try:
            return json.loads(person_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {}



def format_timeline_event(event: dict) -> tuple[str, str, str, str, str, str]:
    """Extract date and description from a timeline event."""
    date_text = ""
    place = ""
    description = ""
    age = ""
    person_name = ""
    symbol = ""
    
    # Format date: YYYY.MM.DD when all details present, YYYY if only year
    if "date" in event:
        date_obj = event["date"]
        if isinstance(date_obj, str):
            date_str = date_obj.strip()
            # Handle YYYY-MM-DD -> YYYY.MM.DD
            if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", date_str):
                year, month, day = date_str.split("-")
                date_text = f"{year}.{int(month):02d}.{int(day):02d}"
            # Handle YYYY -> YYYY
            elif re.fullmatch(r"\d{4}", date_str):
                date_text = date_str
            else:
                date_text = date_str
    
    # Add place if available
    if "place" in event and isinstance(event["place"], dict):
        place_name = event["place"].get("display_name", "").strip()
        if place_name:
            place = clean_string(place_name)

    # Add description if available
    if "label" in event:
        description = translate_text_with_brackets(clean_string(event["label"]))
        symbol = translate_symbol_by_prefix(clean_string(event["label"]))

    # Add age if available
    if "age" in event:
        age = translate_age(str(event["age"]))

    # Add person details if not self
    if "person" in event and isinstance(event["person"], dict):
        relationship = event["person"].get("relationship", "")
        if relationship != "self":
            # Add person name
            given_name = event["person"].get("name_given", "").strip()
            surname = event["person"].get("name_surname", "").strip()
            if surname:
                # Clean brackets from surname
                surname = clean_string(surname)
            if given_name or surname:
                person_name = f"{given_name} {surname}".strip()
    
    return symbol, latex_escape(date_text), latex_escape(place), latex_escape(age), latex_escape(description), latex_escape(person_name)    

def translate_text_with_brackets(text):
    match = re.match(r"^(.*?)\s*\((.*?)\)$", text)
    if not match:
        return tr(text)

    main, inner = match.groups()
    return f"{tr(main.strip())} ({tr(inner.strip())})"

def translate_symbol_by_prefix(text):
    match = re.match(r"^(.*?)\s*\((.*?)\)$", text)
    if not match:
        return trSymbol(text)

    main, inner = match.groups()
    return trSymbol(main.strip())

def translate_age(text):
    if not text:
        return ""
    number, unit = text.split(" ", 1)
    return f"{number} {tr(unit)}"

def trSymbol(event_type: str) -> str:
    """Convert event symbol to Polish."""
    symbol_map = {
        "Birth": "\\birthsymbol",
        "Death": "\\deathsymbol", 
        "Marriage": "\\char\"26AD",
    }
    return symbol_map.get(event_type, event_type)


#TODO - translation to be made for all of the stuff in the timeline events, not just the event type. Also, need to handle translation of event types in the main person data (not just timeline events). This will require a more comprehensive mapping of event types and attributes to Polish equivalents.
def tr(event_type: str) -> str:
    """Convert event type to Polish."""
    type_map = {
        "Son": "Syn",
        "Daughter": "Córka",
        "Mother": "Matka",
        "Sister": "Siostra",
        "Brother": "Brat",
        "Father": "Ojciec",

        "days": "dni",
        "years": "lat",

        "Birth": "Narodziny",
        "Death": "Śmierć", 
        "Marriage": "Ślub",
        "Baptism": "Chrzest",
        "Burial": "Pochówek",
        "Divorce": "Rozwód",
        "Residence": "Zamieszkanie",
        "Occupation": "Zawód",
        "Graduation": "Ukończenie szkoły",
        "Confirmation": "Bierzmowanie",
        "Engagement": "Zaręczyny",
        "Adoption": "Adopcja",
        "Immigration": "Imigracja",
        "Emigration": "Emigracja",
        "Census": "Spis ludności",
        "Military Service": "Służba wojskowa",
        "Retirement": "Emerytura",
        "Will": "Testament",
        "Probate": "Sprawdzanie testamentu",
        "Naturalization": "Naturalizacja",
        "Christening": "Chrzest",
        "Funeral": "Pogrzeb",
        "Ordination": "Święcenia",
        "Bar Mitzvah": "Bar micwa",
        "Bat Mitzvah": "Bat micwa",
        "Circumcision": "Obrzezanie",
        "First Communion": "Pierwsza Komunia",
        "Graduation": "Ukończenie szkoły",
        "Medical Information": "Informacje medyczne",
        "Nobility Title": "Tytuł szlachecki",
        "Number of Children": "Liczba dzieci",
        "Number of Marriages": "Liczba małżeństw",
        "Property": "Własność",
        "Religion": "Religia",
        "Social Security Number": "Numer ubezpieczenia społecznego",
        "Travel": "Podróż",
        "Unknown": "Nieznane",
        "Custom": "Niestandardowe"
    }
    return type_map.get(event_type, event_type)


def build_timeline_section(timeline_data: dict) -> list[tuple[str, str, str, str, str]]:
    """Build a list of (date, place, age, description, person_name) tuples from timeline data, sorted chronologically."""
    events = []
    
    # Handle different possible timeline data structures
    events_list = []
    if isinstance(timeline_data, dict):
        if "events" in timeline_data and isinstance(timeline_data["events"], list):
            events_list = timeline_data["events"]
        elif "timeline" in timeline_data and isinstance(timeline_data["timeline"], list):
            events_list = timeline_data["timeline"]
        elif isinstance(timeline_data, list):
            events_list = timeline_data
    elif isinstance(timeline_data, list):
        events_list = timeline_data
    
    # Extract date and description from each event
    for event in events_list:
        if not isinstance(event, dict):
            continue
        tupple = format_timeline_event(event)
        if tupple:
            events.append(tupple)
    
    return events


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
    full_name: str,
    occupations: str,
    birth_date: str,
    birth_location: str,
    death_date: str,
    death_location: str,
    timeline_events: list,
    father_full_name: str,
    mother_full_name: str,
    path_to_file:str,
    descendant_full_name: str,
    formatted_additional_page_details: str = ""
) -> str:
    full_name_tex = latex_escape(full_name)
    descendant_full_name_tex = latex_escape(descendant_full_name)
    occupations_tex = latex_escape(occupations)
    birth_tex = latex_escape(format_event_line(birth_date, birth_location))
    death_tex = latex_escape(format_event_line(death_date, death_location))

    timeline_events = "\n".join(
        f"{a} & {b} & {c} & {d} & {e} & {f}\\\\"
        for a, b, c, d, e, f in timeline_events
    )

    image_if_exists = f"\\includegraphics[width=\\linewidth,height=5.8cm,keepaspectratio]{{{path_to_file}}}" if path_to_file else ""

    leaf = full_name_tex
    root = descendant_full_name_tex

    return f"""% Auto-generated person page
\\documentclass[10pt, a4paper]{{book}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{array}}
\\usepackage{{xcolor}}
\\usepackage{{ragged2e}}
\\usepackage{{graphicx}}
\\newcommand{{\\birthsymbol}}{{\\ensuremath{{\\star}}}}
\\newcommand{{\\deathsymbol}}{{\\ensuremath{{\\dagger}}}}

\\providecommand{{\\recordchapter}}{{2}}

\\begin{{document}}
\\thispagestyle{{empty}}

\\recordchapter{{{root}}}{{{leaf}}}

\\begin{{tabular}}{{@{{}}p{{0.38\\textwidth}} p{{0.58\\textwidth}}}}
  \\fbox{{%
    \\parbox[c][6cm][c]{{\\linewidth}}{{%
      \\centering      
        {{{image_if_exists}}}
    }}%
  }} &
  \\begin{{minipage}}[t]{{\\linewidth}}
    \\vspace{{0pt}}
    \\Huge \\textbf{{{full_name_tex}}}\\\\[0.3em]
    \\small \\textit{{{occupations_tex}}}\\\\[0.3em]

\\begin{{tabular}}{{@{{}}l l}}
Ojciec: & {{{father_full_name}}} \\\\ 
Matka: & {{{mother_full_name}}} \\\\
\\end{{tabular}}
  \\end{{minipage}} \\\\ 
\\end{{tabular}}

\\noindent
\\begin{{tabular}}{{@{{}}l l l}}
  \\birthsymbol & \\textbf{{Data Narodzin:}} & {birth_tex} \\\\ 
  \\deathsymbol & \\textbf{{Data Śmierci: }} & {death_tex} \\\\ 

\\end{{tabular}}
\\vspace{{1.5em}}

\\begin{{tabular}}{{@{{}}l l l l l l}}
& \\textbf{{Data}} & \\textbf{{Miejsce}} & \\textbf{{Wiek}} & \\textbf{{Opis}} & \\textbf{{Osoba}}\\\\
\\hline
    {timeline_events}
\\end{{tabular}}

{formatted_additional_page_details}

\\end{{document}}
"""

def format_additional_page_details(details: list) -> str:
    if not isinstance(details, list) or not details:
        return ""
    formatted_details = ""
    
    for detail in details:
        media_desc = detail.get("mediaDetails", {}).get("desc", "")
        note_desc = None
        if detail.get("noteDetails", {}):
            note_desc = detail.get("noteDetails", {}).get("text", "").get("string", "")
        picture_link = detail.get("pictureDetails_link", "")
        
        formatted_details += f"""\\newpage
        \\begin{{center}}
        \\includegraphics[width=\\textwidth]{{{picture_link}}}
        \\newline
        {{{latex_escape(media_desc)}}}
        \\newline """
        if note_desc:
            formatted_details += f"""
            \\fbox{{
            \\parbox{{\\linewidth}}{{{latex_escape(note_desc)}}}}}
            """
        formatted_details += f"  \\end{{center}} "

    return f"\\vspace{{1.5em}}\n{formatted_details}\n"


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
        data_path = page_dir / "assets" / "data.json"
    if not data_path.exists():
        raise SystemExit(f"ERROR: person data not found: {data_path}")

    output_path = Path(args.output_file).resolve() if args.output_file else page_dir / "output" / "page.tex"

    try:
        person = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: could not load JSON data: {exc}")

    full_name = create_full_name(person)

    occupations = extract_occupations(person)
    birth_date, birth_location, death_date, death_location = infer_birth_death_dates(page_dir, person)
    
    # Extract timeline events
    timeline_data = load_timeline_data(page_dir, person)
    timeline_events = build_timeline_section(timeline_data)

    # Load Parents Data
    parent_data = load_person_data(page_dir, person, "father_handle")
    father_full_name = create_full_name(parent_data)
    parent_data = load_person_data(page_dir, person, "mother_handle")
    mother_full_name = create_full_name(parent_data)

    descendant_full_name = ""
    if person.get("descendant_handle"):
        descendant_data = load_person_data(page_dir, person, "descendant_handle")
        descendant_full_name = create_full_name(descendant_data)
    else :
        descendant_full_name = person.get("descendant_display_name")

    path_to_file = person.get("titlePagePhoto_link", "")
    formatted_additional_page_details = format_additional_page_details(person.get("additional_page_details", []))

    output_path.write_text(
        render_tex(
            full_name,
            occupations,
            birth_date,
            birth_location,
            death_date,
            death_location,
            timeline_events,
            father_full_name,
            mother_full_name,
            path_to_file,
            descendant_full_name,
            formatted_additional_page_details
        ),
        encoding="utf-8",
    )
    print(f"Rendered TeX to: {output_path}")


if __name__ == "__main__":
    main()
