"""Cache manager for tracking exported tasks."""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class ExportCache:
    """Manages cache for tracking exported tasks and their external IDs.

    The cache stores mappings between Notion task IDs and external system IDs
    (e.g., Apple Calendar event IDs), along with task metadata to detect changes.
    """

    def __init__(self, cache_file: Path | str):
        """Initialize the cache manager.

        Args:
            cache_file: Path to the cache file (JSON format)
        """
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load cache from {self.cache_file}: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def _save(self) -> None:
        """Save cache to file."""
        # Ensure parent directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Failed to save cache to {self.cache_file}: {e}")

    def get_entry(self, notion_id: str) -> Optional[Dict[str, Any]]:
        """Get a cache entry by Notion task ID.

        Args:
            notion_id: Notion task/page ID

        Returns:
            Cache entry dictionary or None if not found
        """
        return self.cache.get(notion_id)

    def has_changes(self, notion_id: str, task_data: Dict[str, Any]) -> bool:
        """Check if a task has changes compared to cached version.

        Args:
            notion_id: Notion task/page ID
            task_data: Current task data to compare

        Returns:
            True if task has changes or is not in cache, False otherwise
        """
        entry = self.get_entry(notion_id)
        if not entry:
            return True

        # Compare key fields that would require calendar update
        cached_data = entry.get("task_data", {})

        # Check for changes in important fields
        fields_to_check = ["title", "due_start", "due_end", "status"]
        for field in fields_to_check:
            if task_data.get(field) != cached_data.get(field):
                return True

        return False

    def set_entry(
        self,
        notion_id: str,
        external_id: str,
        task_data: Dict[str, Any],
        exporter_type: str,
    ) -> None:
        """Set or update a cache entry.

        Args:
            notion_id: Notion task/page ID
            external_id: External system ID (e.g., calendar event ID)
            task_data: Task data to cache
            exporter_type: Type of exporter (e.g., "apple_calendar")
        """
        self.cache[notion_id] = {
            "external_id": external_id,
            "task_data": task_data,
            "exporter_type": exporter_type,
            "last_synced": datetime.now().isoformat(),
        }
        self._save()

    def remove_entry(self, notion_id: str) -> None:
        """Remove a cache entry.

        Args:
            notion_id: Notion task/page ID to remove
        """
        if notion_id in self.cache:
            del self.cache[notion_id]
            self._save()

    def get_all_entries(self, exporter_type: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get all cache entries, optionally filtered by exporter type.

        Args:
            exporter_type: Optional filter by exporter type

        Returns:
            Dictionary of cache entries
        """
        if exporter_type:
            return {
                k: v
                for k, v in self.cache.items()
                if v.get("exporter_type") == exporter_type
            }
        return self.cache.copy()

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache = {}
        self._save()

    def get_external_id(self, notion_id: str) -> Optional[str]:
        """Get the external system ID for a Notion task.

        Args:
            notion_id: Notion task/page ID

        Returns:
            External system ID or None if not found
        """
        entry = self.get_entry(notion_id)
        return entry.get("external_id") if entry else None
