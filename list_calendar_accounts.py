#!/usr/bin/env python3
"""List all available calendar accounts on this Mac."""

import sys

try:
    from EventKit import EKEventStore
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False
    print("Error: EventKit not available. Install with: pip install pyobjc-framework-EventKit")
    sys.exit(1)


def list_calendar_accounts():
    """List all available calendar sources/accounts."""
    event_store = EKEventStore.alloc().init()

    # Try to access calendars
    try:
        calendars = event_store.calendarsForEntityType_(0)  # 0 = EKEntityTypeEvent
    except Exception as e:
        print(f"Error accessing calendars: {e}")
        print("Please grant calendar access in System Settings > Privacy & Security > Calendars")
        return

    # Get all sources
    sources = event_store.sources()

    print("="*60)
    print("Available Calendar Accounts:")
    print("="*60)

    # Source type mapping
    source_types = {
        0: "Local",
        1: "CalDAV (iCloud)",
        2: "Exchange",
        3: "Subscribed",
        4: "Birthdays",
    }

    for i, source in enumerate(sources, 1):
        source_type = source.sourceType()
        source_title = source.title()
        type_name = source_types.get(source_type, f"Unknown ({source_type})")

        print(f"\n{i}. {source_title}")
        print(f"   Type: {type_name}")
        print(f"   Source ID: {source.sourceIdentifier()}")

        # Count calendars in this source
        source_calendars = [cal for cal in calendars if cal.source().sourceIdentifier() == source.sourceIdentifier()]
        print(f"   Calendars: {len(source_calendars)}")

        if source_calendars:
            for cal in source_calendars[:3]:  # Show first 3 calendars
                print(f"     - {cal.title()}")
            if len(source_calendars) > 3:
                print(f"     ... and {len(source_calendars) - 3} more")

    print("\n" + "="*60)
    print("Configuration:")
    print("="*60)
    print("\nTo specify which account to use, add this to your config.toml:")
    print("\n[exporters.apple_calendar]")
    print('account_name = "iCloud"  # or "Local" or your account name')
    print("\nIf not specified, the system will prioritize accounts in this order:")
    print("1. iCloud (recommended)")
    print("2. Local")
    print("3. First available account")


if __name__ == "__main__":
    list_calendar_accounts()
