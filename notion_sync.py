import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple
from pprint import pprint
import toml
from notion_client import Client

from exporters import TaskExporter, AppleCalendarExporter

# Order matters; the first existing file is used.
DEFAULT_CONFIG_PATHS = [
    Path("config.toml"),
    Path.home() / ".config" / "notion-cal-sync" / "config.toml",
]


def load_config(explicit_path: str | None) -> Tuple[Dict[str, Any], Path]:
    """Load config from the first existing path."""
    candidate_paths: Iterable[Path] = []
    if explicit_path:
        candidate_paths = [Path(explicit_path).expanduser()]
    candidate_paths = list(candidate_paths) + [
        p for p in DEFAULT_CONFIG_PATHS if p not in candidate_paths
    ]

    for path in candidate_paths:
        if path.exists():
            return toml.load(path), path

    tried = ", ".join(str(p) for p in candidate_paths)
    raise FileNotFoundError(f"No config.toml found; tried: {tried}")


def validate_config(config: Dict[str, Any]) -> None:
    missing = [key for key in ("notion_token", "database_id") if not config.get(key)]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")


def get_data_source_id(client: Client, database_id: str) -> str:
    db_info = client.databases.retrieve(database_id=database_id)
    data_sources = db_info.get("data_sources", [])
    if not data_sources:
        raise ValueError(f"No data sources found in database {database_id}")
    return data_sources[0]["id"]


def fetch_database_rows(client: Client, database_id: str) -> list[Dict[str, Any]]:
    """Read all pages from the database via pagination."""
    # API changed in notion-client 2.x: need to get data_source_id first
    data_source_id = get_data_source_id(client, database_id)

    rows: list[Dict[str, Any]] = []
    cursor = None
    while True:
        response = client.data_sources.query(
            data_source_id=data_source_id, start_cursor=cursor, page_size=100
        )
        rows.extend(response["results"])
        if response.get("has_more"):
            cursor = response.get("next_cursor")
        else:
            break
    return rows


def extract_title(page: Dict[str, Any], title_property: str) -> str:
    title_prop = page["properties"].get(title_property, {})
    parts = title_prop.get("title", [])
    return "".join(part.get("plain_text", "") for part in parts) or "<untitled>"


def parse_property_value(prop: Dict[str, Any]) -> str:
    """Parse different Notion property types into readable strings."""
    prop_type = prop.get("type")

    if prop_type == "title":
        parts = prop.get("title", [])
        return "".join(part.get("plain_text", "") for part in parts) or "<empty>"

    elif prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(part.get("plain_text", "") for part in parts) or "<empty>"

    elif prop_type == "number":
        num = prop.get("number")
        return str(num) if num is not None else "<empty>"

    elif prop_type == "select":
        select = prop.get("select")
        return select.get("name", "<empty>") if select else "<empty>"

    elif prop_type == "multi_select":
        items = prop.get("multi_select", [])
        return ", ".join(item.get("name", "") for item in items) or "<empty>"

    elif prop_type == "status":
        status = prop.get("status")
        return status.get("name", "<empty>") if status else "<empty>"

    elif prop_type == "date":
        date = prop.get("date")
        if not date:
            return "<empty>"
        start = date.get("start", "")
        end = date.get("end")
        return f"{start} → {end}" if end else start

    elif prop_type == "people":
        people = prop.get("people", [])
        names = [person.get("name", "Unknown") for person in people]
        return ", ".join(names) or "<empty>"

    elif prop_type == "files":
        files = prop.get("files", [])
        return f"{len(files)} file(s)" if files else "<empty>"

    elif prop_type == "checkbox":
        checked = prop.get("checkbox", False)
        return "✓" if checked else "✗"

    elif prop_type == "url":
        url = prop.get("url")
        return url or "<empty>"

    elif prop_type == "email":
        email = prop.get("email")
        return email or "<empty>"

    elif prop_type == "phone_number":
        phone = prop.get("phone_number")
        return phone or "<empty>"

    elif prop_type == "relation":
        relations = prop.get("relation", [])
        return f"{len(relations)} related item(s)" if relations else "<empty>"

    elif prop_type == "created_time":
        return prop.get("created_time", "<empty>")

    elif prop_type == "created_by":
        user = prop.get("created_by", {})
        return user.get("name", "<empty>")

    elif prop_type == "last_edited_time":
        return prop.get("last_edited_time", "<empty>")

    elif prop_type == "last_edited_by":
        user = prop.get("last_edited_by", {})
        return user.get("name", "<empty>")

    elif prop_type == "rollup":
        rollup = prop.get("rollup", {})
        rollup_type = rollup.get("type")

        if rollup_type == "number":
            num = rollup.get("number")
            return str(num) if num is not None else "<empty>"

        elif rollup_type == "date":
            date = rollup.get("date")
            if not date:
                return "<empty>"
            start = date.get("start", "")
            end = date.get("end")
            return f"{start} → {end}" if end else start

        elif rollup_type == "array":
            array = rollup.get("array", [])
            if not array:
                return "<empty>"
            # Try to extract values from array items
            values = []
            for item in array:
                item_type = item.get("type")
                if item_type == "formula":
                    formula = item.get("formula", {})
                    formula_type = formula.get("type")
                    if formula_type == "boolean":
                        values.append("✓" if formula.get("boolean") else "✗")
                    elif formula_type == "string":
                        values.append(formula.get("string", ""))
                    elif formula_type == "number":
                        values.append(str(formula.get("number", "")))
            return ", ".join(values) if values else f"{len(array)} item(s)"

        else:
            return f"<rollup: {rollup_type}>"

    elif prop_type == "formula":
        formula = prop.get("formula", {})
        formula_type = formula.get("type")

        if formula_type == "string":
            return formula.get("string", "<empty>")
        elif formula_type == "number":
            num = formula.get("number")
            return str(num) if num is not None else "<empty>"
        elif formula_type == "boolean":
            return "✓" if formula.get("boolean") else "✗"
        elif formula_type == "date":
            date = formula.get("date")
            if not date:
                return "<empty>"
            start = date.get("start", "")
            end = date.get("end")
            return f"{start} → {end}" if end else start
        else:
            return f"<formula: {formula_type}>"

    else:
        return f"<unsupported type: {prop_type}>"


def get_exporter(exporter_type: str, config: Dict[str, Any]) -> TaskExporter | None:
    """Factory function to create the appropriate exporter.

    Args:
        exporter_type: Type of exporter ("apple_calendar", "things", etc.)
        config: Configuration dictionary for the exporter

    Returns:
        TaskExporter instance or None if type not recognized
    """
    exporters = {
        "apple_calendar": AppleCalendarExporter,
        # Future exporters can be added here:
        # "things": ThingsExporter,
        # "todoist": TodoistExporter,
    }

    exporter_class = exporters.get(exporter_type)
    if exporter_class:
        return exporter_class(config)
    return None


def print_parsed_data(rows: list[Dict[str, Any]]) -> None:
    """Parse and print database rows in a readable format."""
    if not rows:
        print("No data found.")
        return

    print(f"\n{'='*80}")
    print(f"Total records: {len(rows)}")
    print(f"{'='*80}\n")

    for idx, page in enumerate(rows, 1):
        print(f"Record #{idx}")
        print(f"  ID: {page.get('id')}")
        print(f"  Created: {page.get('created_time')}")
        print(f"  Last Edited: {page.get('last_edited_time')}")
        print(f"  Properties:")

        properties = page.get("properties", {})
        for prop_name, prop_value in properties.items():
            parsed_value = parse_property_value(prop_value)
            print(f"    • {prop_name}: {parsed_value}")

        print(f"{'-'*80}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query a Notion database using credentials from config.toml."
    )
    parser.add_argument(
        "--config",
        help="Override config file path (defaults to config.toml or ~/.config/notion-cal-sync/config.toml)",
    )
    parser.add_argument(
        "--title-property",
        help="Optional title property name; defaults to config value or 'Name'.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print full Notion JSON instead of a compact summary.",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Print detailed parsed data for all properties.",
    )
    parser.add_argument(
        "--export",
        choices=["apple_calendar", "things"],
        help="Export tasks to the specified system (apple_calendar, things, etc.).",
    )
    args = parser.parse_args()

    config, config_path = load_config(args.config)
    validate_config(config)

    notion = Client(
        auth=config["notion_token"]
    )
    
    database_id = config["database_id"]
    title_property = args.title_property or config.get("title_property", "Name")
    rows = fetch_database_rows(notion, database_id)

    if args.raw:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    if args.detailed:
        print_parsed_data(rows)
        return

    # Handle export functionality
    if args.export:
        exporter_config = config.get("exporters", {}).get(args.export, {})
        exporter = get_exporter(args.export, exporter_config)

        if not exporter:
            print(f"Error: Unknown exporter type '{args.export}'")
            return

        print(f"Exporting {len(rows)} tasks to {args.export}...")
        result = exporter.export_tasks(rows)

        # Print results
        print(f"\n{'='*60}")
        print(f"Export Results:")
        print(f"  Success: {result['success']}")
        print(f"  Created: {result['created']}")
        print(f"  Updated: {result['updated']}")
        print(f"  Skipped: {result['skipped']}")

        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            for error in result['errors']:
                print(f"    - {error}")
        print(f"{'='*60}")
        return

    print(f"Loaded {len(rows)} rows from database {database_id} (config: {config_path})")
    for page in rows:
        title = extract_title(page, title_property)
        print(f"- {title} [{page.get('id')}]")


if __name__ == "__main__":
    main()
