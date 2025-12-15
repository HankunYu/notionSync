"""Abstract base class for task exporters."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path

from .cache import ExportCache


class TaskExporter(ABC):
    """Abstract base class for exporting tasks to different systems.

    Subclasses should implement the export_tasks method to integrate
    with specific systems like Apple Calendar, Things, etc.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the exporter with optional configuration.

        Args:
            config: Optional configuration dictionary for the exporter
        """
        self.config = config or {}

        # Initialize cache
        cache_dir = Path.home() / ".cache" / "notion_sync"
        cache_file = cache_dir / f"{self.get_exporter_name()}_cache.json"
        self.cache = ExportCache(cache_file)

    @abstractmethod
    def get_exporter_name(self) -> str:
        """Get the name of this exporter (used for cache file naming).

        Returns:
            Exporter name (e.g., "apple_calendar", "things")
        """
        pass

    @abstractmethod
    def export_tasks(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Export tasks to the target system.

        Args:
            tasks: List of Notion page objects containing task data

        Returns:
            A dictionary with export results containing:
                - success: bool, whether the export succeeded
                - created: int, number of items created
                - updated: int, number of items updated
                - skipped: int, number of items skipped
                - errors: list of error messages if any
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that the exporter is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    def extract_task_data(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract common task data from a Notion page object.

        This is a helper method that can be used by subclasses to extract
        standard fields from Notion tasks.

        Args:
            task: A Notion page object

        Returns:
            Dictionary with extracted task data
        """
        properties = task.get("properties", {})

        # Extract title
        title_prop = properties.get("Task name", {})
        title_parts = title_prop.get("title", [])
        title = "".join(part.get("plain_text", "") for part in title_parts) or "Untitled"

        # Extract due date
        due_prop = properties.get("Due", {})
        due_date = due_prop.get("date", {})
        due_start = due_date.get("start") if due_date else None
        due_end = due_date.get("end") if due_date else None

        # Extract status
        status_prop = properties.get("Status", {})
        status = status_prop.get("status", {})
        status_name = status.get("name") if status else None

        # Extract assignees
        assign_prop = properties.get("Assign", {})
        people = assign_prop.get("people", [])
        assignees = [person.get("name", "Unknown") for person in people]

        return {
            "id": task.get("id"),
            "title": title,
            "due_start": due_start,
            "due_end": due_end,
            "status": status_name,
            "assignees": assignees,
            "created_time": task.get("created_time"),
            "last_edited_time": task.get("last_edited_time"),
            "url": task.get("url"),
        }
