#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


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
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def escape_latex(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("\\", r"\textbackslash ")
         .replace("&", r"\&")
         .replace("%", r"\%")
         .replace("$", r"\$")
         .replace("#", r"\#")
         .replace("_", r"\_")
         .replace("{", r"\{")
         .replace("}", r"\}")
    )


def sanitize_macro_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip()).strip("_")
    if not sanitized:
        sanitized = "source"
    return f"source_{sanitized}"


def normalize_source(source: dict) -> dict:
    if not isinstance(source, dict):
        return {}

    abbreviation = (
        source.get("abbreviation")
        or source.get("abbr")
        or source.get("Abbreviation")
        or source.get("abbrev")
        or ""
    )
    title = (
        source.get("title")
        or source.get("description")
        or source.get("name")
        or source.get("text")
        or ""
    )
    source_id = (
        source.get("gramps_id")
        or source.get("id")
        or source.get("handle")
        or source.get("uri")
        or ""
    )

    return {
        "abbreviation": str(abbreviation).strip() if abbreviation is not None else "",
        "title": str(title).strip() if title is not None else "",
        "source_id": str(source_id).strip() if source_id is not None else "",
    }


def build_source_macro(source: dict) -> str:
    normalized = normalize_source(source)
    if not normalized["abbreviation"]:
        return ""

    macro_name = sanitize_macro_name(normalized["abbreviation"])
    body_parts = ["Źródło:", normalized["title"]]
    body_content = " ".join(part for part in body_parts if part).strip()
    if not body_content:
        body_content = normalized["abbreviation"]

    return f"\\def\\{macro_name}{{{escape_latex(body_content)} \\vspace{{0.5em}}}}"


def render_source_headers(sources, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for source in sources:
        macro = build_source_macro(source)
        if macro:
            lines.append(macro)

    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return output_path


def load_sources_from_gramps(base_url: str, headers: dict, timeout: int, search_path: str) -> list[dict]:
    url = build_url(base_url, search_path)
    try:
        data = fetch_json(url, headers, timeout)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Warning: failed to load source objects from {url}: {exc}")
        return []

    if isinstance(data, list):
        return [source for source in data if isinstance(source, dict)]

    if isinstance(data, dict):
        for key in ("sources", "results", "source_list"):
            value = data.get(key)
            if isinstance(value, list):
                return [source for source in value if isinstance(source, dict)]

    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Load source objects with abbreviations from GRAMPS and write a TeX header file")
    parser.add_argument("--output", default="output/source_headers.tex", help="Path to the generated TeX file")
    parser.add_argument("--source-search-path", default=None, help="GRAMPS API path for source discovery")
    args = parser.parse_args()

    base_url = get_env("GRAMPS_API_BASE_URL", "")
    if not base_url:
        print("Warning: GRAMPS_API_BASE_URL not set. Creating an empty source header file.")
        render_source_headers([], args.output)
        return

    token = get_env("GRAMPS_API_TOKEN", "")
    timeout = int(get_env("GRAMPS_API_TIMEOUT", "30"))
    search_path = args.source_search_path or get_env("GRAMPS_API_SOURCE_SEARCH_PATH", "sources")

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    sources = load_sources_from_gramps(base_url, headers, timeout, search_path)
    filtered_sources = [source for source in sources if normalize_source(source)["abbreviation"]]
    render_source_headers(filtered_sources, args.output)

    print(f"Wrote {len(filtered_sources)} source definitions to {args.output}")


if __name__ == "__main__":
    main()
