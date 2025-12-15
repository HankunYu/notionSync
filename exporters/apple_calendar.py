"""Apple Calendar exporter using EventKit."""

import sys
from typing import Any, Dict, List
from datetime import datetime, timedelta

try:
    from EventKit import (
        EKEventStore,
        EKEvent,
        EKCalendar,
    )
    from Foundation import NSDate
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False

from .base import TaskExporter


class AppleCalendarExporter(TaskExporter):
    """Export Notion tasks to Apple Calendar as events."""

    def get_exporter_name(self) -> str:
        """Get the name of this exporter."""
        return "apple_calendar"

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the Apple Calendar exporter.

        Args:
            config: Configuration dictionary with optional keys:
                - calendar_name: Name of the calendar to use (default: "Notion Tasks")
                - default_duration_hours: Duration for tasks without end date (default: 1)
                - skip_completed: Whether to skip completed tasks (default: True)
                - event_prefix: Prefix to add to event titles (default: "[Notion] ")
        """
        super().__init__(config)
        self.calendar_name = self.config.get("calendar_name", "Notion Tasks")
        self.default_duration_hours = self.config.get("default_duration_hours", 1)
        self.skip_completed = self.config.get("skip_completed", True)
        self.event_prefix = self.config.get("event_prefix", "[Notion] ")

        self.event_store = None
        self.calendar = None

    def validate_config(self) -> bool:
        """Validate that EventKit is available and we have calendar access."""
        if not EVENTKIT_AVAILABLE:
            print("Error: EventKit not available. Install with: pip install pyobjc-framework-EventKit")
            return False

        if sys.platform != "darwin":
            print("Error: Apple Calendar is only available on macOS")
            return False

        return True

    def _request_calendar_access(self) -> bool:
        """Request access to calendar and initialize event store.

        Returns:
            True if access granted, False otherwise
        """
        # Initialize event store if needed
        if self.event_store is None:
            self.event_store = EKEventStore.alloc().init()

        # Check current authorization status
        status = EKEventStore.authorizationStatusForEntityType_(0)  # 0 = EKEntityTypeEvent

        # Status codes:
        # 0 = Not Determined, 1 = Restricted, 2 = Denied, 3+ = Authorized
        if status == 2:  # Denied
            print("❌ Calendar access was denied.")
            print("Please enable calendar access in:")
            print("System Settings > Privacy & Security > Calendars > Python/Terminal")
            return False
        elif status == 1:  # Restricted
            print("❌ Calendar access is restricted by system policy.")
            return False
        elif status >= 3:  # Already authorized
            return True

        # Status is 0 (Not Determined) - need to request permission
        print("🔐 Requesting calendar access...")
        print("⚠️  A permission dialog should appear. Please click 'Allow'")
        print("⚠️  Note: The dialog might appear behind other windows - check all spaces/desktops")

        # Use RunLoop to ensure the callback is processed
        from Foundation import NSRunLoop, NSDefaultRunLoopMode, NSDate
        import time

        access_granted = [False]
        request_completed = [False]

        def completion_handler(granted, error):
            access_granted[0] = granted
            request_completed[0] = True
            if error:
                print(f"Permission error: {error}")

        # Request access
        self.event_store.requestAccessToEntityType_completion_(0, completion_handler)

        # Run the run loop to process the callback
        timeout = 60  # 60 seconds timeout
        start_time = time.time()

        while not request_completed[0] and (time.time() - start_time) < timeout:
            # Run the run loop for a short time to process callbacks
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.1)
            )

        if not request_completed[0]:
            print("\n❌ Permission request timed out or no dialog appeared.")
            print("\n💡 Manual authorization required:")
            print("   1. Open the Calendar app (to ensure calendar system is initialized)")
            print("   2. Open System Settings > Privacy & Security > Calendars")
            print("   3. Look for 'Python' or 'Terminal' or 'python3' in the list")
            print("   4. Enable calendar access")
            print("   5. If not in the list, you may need to run this from within an app")
            print("      or grant permission to Terminal itself")
            print("\n💡 Alternative: Try running with 'sudo' or from a GUI application")
            return False

        if not access_granted[0]:
            print("\n❌ Calendar access was denied.")
            print("\n💡 To enable access:")
            print("   System Settings > Privacy & Security > Calendars > Enable for Python/Terminal")
            return False

        print("✅ Calendar access granted!")
        return True

    def _get_or_create_calendar(self) -> bool:
        """Get the target calendar or create it if it doesn't exist.

        Returns:
            True if calendar is ready, False otherwise
        """
        # Search for existing calendar
        calendars = self.event_store.calendarsForEntityType_(0)  # 0 = EKEntityTypeEvent

        for cal in calendars:
            if cal.title() == self.calendar_name:
                self.calendar = cal
                source = cal.source()
                account_name = source.title() if source else "Unknown"
                print(f"Using existing calendar '{self.calendar_name}' in account: {account_name}")
                return True

        # Create new calendar
        new_calendar = EKCalendar.calendarForEntityType_eventStore_(0, self.event_store)
        new_calendar.setTitle_(self.calendar_name)

        # Get all available sources and choose the best one
        sources = self.event_store.sources()
        preferred_account = self.config.get("account_name")  # User preference from config

        selected_source = None
        icloud_source = None
        local_source = None

        # Categorize sources
        for source in sources:
            source_type = source.sourceType()
            source_title = source.title()

            # Check if this matches user's preferred account
            if preferred_account and source_title == preferred_account:
                selected_source = source
                break

            # Keep track of iCloud and local sources as fallbacks
            if source_type == 1:  # CalDAV (iCloud)
                if not icloud_source:
                    icloud_source = source
            elif source_type == 0:  # Local
                if not local_source:
                    local_source = source

        # Priority: User preference > iCloud > Local > First available
        if not selected_source:
            selected_source = icloud_source or local_source or (sources[0] if sources else None)

        if not selected_source:
            print("Error: No calendar source available")
            return False

        new_calendar.setSource_(selected_source)

        # Save the calendar
        error = None
        success = self.event_store.saveCalendar_commit_error_(new_calendar, True, error)

        if success:
            self.calendar = new_calendar
            account_name = selected_source.title()
            print(f"Created new calendar '{self.calendar_name}' in account: {account_name}")
            return True
        else:
            print(f"Failed to create calendar: {error}")
            return False

    def _parse_date(self, date_string: str, all_day: bool = False) -> NSDate:
        """Convert ISO date string to NSDate.

        Args:
            date_string: ISO format date string (e.g., "2025-12-15" or "2025-12-15T10:00:00")
            all_day: If True, set time to midnight for all-day events

        Returns:
            NSDate object
        """
        # Parse the date string
        if "T" in date_string:
            dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        else:
            # Date only
            dt = datetime.fromisoformat(date_string)

        # For all-day events, always use midnight (00:00:00)
        if all_day:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif "T" not in date_string:
            # If not all-day and no time specified, set to 9 AM
            dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)

        # Convert to NSDate
        timestamp = dt.timestamp()
        return NSDate.dateWithTimeIntervalSince1970_(timestamp)

    def _get_event_by_id(self, event_id: str) -> Any:
        """Retrieve an event by its ID.

        Args:
            event_id: Calendar event ID

        Returns:
            EKEvent object or None if not found
        """
        try:
            event = self.event_store.eventWithIdentifier_(event_id)
            return event
        except Exception as e:
            print(f"Failed to retrieve event {event_id}: {e}")
            return None

    def _update_event(self, event: Any, task_data: Dict[str, Any]) -> bool:
        """Update an existing calendar event.

        Args:
            event: EKEvent object to update
            task_data: New task data

        Returns:
            True if event updated successfully, False otherwise
        """
        try:
            # Update title
            title = self.event_prefix + task_data["title"]
            event.setTitle_(title)

            # Set as all-day event
            event.setAllDay_(True)

            # Update dates (for all-day events, use date-only format)
            start_date = self._parse_date(task_data["due_start"], all_day=True)
            event.setStartDate_(start_date)

            if task_data.get("due_end"):
                end_date = self._parse_date(task_data["due_end"], all_day=True)
                event.setEndDate_(end_date)
            else:
                # For all-day events without end date, end date = start date + 1 day
                end_timestamp = start_date.timeIntervalSince1970() + 86400  # 24 hours
                end_date = NSDate.dateWithTimeIntervalSince1970_(end_timestamp)
                event.setEndDate_(end_date)

            # Update notes
            notes = []
            if task_data.get("status"):
                notes.append(f"Status: {task_data['status']}")
            if task_data.get("assignees"):
                notes.append(f"Assignees: {', '.join(task_data['assignees'])}")
            if task_data.get("url"):
                notes.append(f"\nNotion URL: {task_data['url']}")

            event.setNotes_("\n".join(notes))

            # Save updated event
            error = None
            success = self.event_store.saveEvent_span_commit_error_(event, 0, True, error)

            if not success:
                print(f"Failed to update event for '{task_data['title']}': {error}")

            return success

        except Exception as e:
            print(f"Error updating event for '{task_data['title']}': {e}")
            return False

    def _create_event(self, task_data: Dict[str, Any]) -> str | None:
        """Create a calendar event from task data.

        Args:
            task_data: Extracted task data dictionary

        Returns:
            Event ID if created successfully, None otherwise
        """
        # Skip if no due date
        if not task_data.get("due_start"):
            return None

        # Skip completed tasks if configured
        if self.skip_completed and task_data.get("status") == "Done":
            return None

        # Create event
        event = EKEvent.eventWithEventStore_(self.event_store)
        event.setCalendar_(self.calendar)

        # Set title
        title = self.event_prefix + task_data["title"]
        event.setTitle_(title)

        # Set as all-day event
        event.setAllDay_(True)

        # Set dates (for all-day events, use date-only format)
        start_date = self._parse_date(task_data["due_start"], all_day=True)
        event.setStartDate_(start_date)

        if task_data.get("due_end"):
            end_date = self._parse_date(task_data["due_end"], all_day=True)
            event.setEndDate_(end_date)
        else:
            # For all-day events without end date, end date = start date + 1 day
            end_timestamp = start_date.timeIntervalSince1970() + 86400  # 24 hours
            end_date = NSDate.dateWithTimeIntervalSince1970_(end_timestamp)
            event.setEndDate_(end_date)

        # Set notes with task details
        notes = []
        if task_data.get("status"):
            notes.append(f"Status: {task_data['status']}")
        if task_data.get("assignees"):
            notes.append(f"Assignees: {', '.join(task_data['assignees'])}")
        if task_data.get("url"):
            notes.append(f"\nNotion URL: {task_data['url']}")

        event.setNotes_("\n".join(notes))

        # Save event
        # EKSpanThisEvent = 0, EKSpanFutureEvents = 1
        error = None
        success = self.event_store.saveEvent_span_commit_error_(event, 0, True, error)

        if not success:
            print(f"Failed to create event for '{task_data['title']}': {error}")
            return None

        # Return event ID
        return event.eventIdentifier()

    def export_tasks(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Export tasks to Apple Calendar.

        Args:
            tasks: List of Notion page objects

        Returns:
            Dictionary with export results
        """
        result = {
            "success": False,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        # Validate configuration
        if not self.validate_config():
            result["errors"].append("Configuration validation failed")
            return result

        # Request calendar access
        if not self._request_calendar_access():
            result["errors"].append("Calendar access denied")
            return result

        # Get or create calendar
        if not self._get_or_create_calendar():
            result["errors"].append("Failed to get/create calendar")
            return result

        # Process each task
        for task in tasks:
            try:
                notion_id = task.get("id")
                task_data = self.extract_task_data(task)

                # Check if we should skip this task
                if not task_data.get("due_start"):
                    result["skipped"] += 1
                    continue

                if self.skip_completed and task_data.get("status") == "Done":
                    result["skipped"] += 1
                    continue

                # Check if task exists in cache and has changes
                if self.cache.has_changes(notion_id, task_data):
                    # Check if we have an existing event
                    event_id = self.cache.get_external_id(notion_id)

                    if event_id:
                        # Try to update existing event
                        event = self._get_event_by_id(event_id)
                        if event:
                            if self._update_event(event, task_data):
                                result["updated"] += 1
                                # Update cache with new task data
                                self.cache.set_entry(
                                    notion_id, event_id, task_data, self.get_exporter_name()
                                )
                            else:
                                result["skipped"] += 1
                        else:
                            # Event not found, create new one
                            new_event_id = self._create_event(task_data)
                            if new_event_id:
                                result["created"] += 1
                                self.cache.set_entry(
                                    notion_id, new_event_id, task_data, self.get_exporter_name()
                                )
                            else:
                                result["skipped"] += 1
                    else:
                        # Create new event
                        event_id = self._create_event(task_data)
                        if event_id:
                            result["created"] += 1
                            # Save to cache
                            self.cache.set_entry(
                                notion_id, event_id, task_data, self.get_exporter_name()
                            )
                        else:
                            result["skipped"] += 1
                else:
                    # No changes, skip
                    result["skipped"] += 1

            except Exception as e:
                error_msg = f"Error processing task {task.get('id', 'unknown')}: {str(e)}"
                result["errors"].append(error_msg)
                print(error_msg)

        result["success"] = len(result["errors"]) == 0
        return result
