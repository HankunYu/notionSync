#!/usr/bin/env python3
"""Check calendar access permission status."""

import sys
import platform

try:
    from EventKit import EKEventStore, EKAuthorizationStatus
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False
    print("Error: EventKit not available. Install with: pip install pyobjc-framework-EventKit")
    sys.exit(1)


def check_permission():
    """Check calendar permission status and request access if needed."""
    print("="*60)
    print("Calendar Permission Diagnostic")
    print("="*60)

    # Get macOS version
    macos_version = platform.mac_ver()[0]
    print(f"\nmacOS Version: {macos_version}")

    # Create event store
    event_store = EKEventStore.alloc().init()

    # Check authorization status
    # EKAuthorizationStatusNotDetermined = 0
    # EKAuthorizationStatusRestricted = 1
    # EKAuthorizationStatusDenied = 2
    # EKAuthorizationStatusAuthorized = 3
    # EKAuthorizationStatusFullAccess = 4 (macOS 14+)
    # EKAuthorizationStatusWriteOnly = 5 (macOS 14+)

    try:
        # For macOS 14+, use authorizationStatusForEntityType_
        # For older versions, this still works
        status = EKEventStore.authorizationStatusForEntityType_(0)  # 0 = EKEntityTypeEvent

        status_names = {
            0: "Not Determined (Permission not requested yet)",
            1: "Restricted (Cannot grant access)",
            2: "Denied (User denied access)",
            3: "Authorized (Full access granted)",
            4: "Full Access (macOS 14+)",
            5: "Write Only (macOS 14+)",
        }

        status_name = status_names.get(status, f"Unknown ({status})")
        print(f"\nAuthorization Status: {status_name}")

        if status == 0:  # Not Determined
            print("\n⚠️  Permission has not been requested yet.")
            print("   The system will prompt for permission when you run the export.")
            print("\n💡 Solution:")
            print("   1. Run: python notion_sync.py --export apple_calendar")
            print("   2. When the permission dialog appears, click 'Allow'")
            print("   3. If no dialog appears, manually grant permission in:")
            print("      System Settings > Privacy & Security > Calendars")

        elif status == 1:  # Restricted
            print("\n❌ Calendar access is restricted (likely by parental controls or MDM).")
            print("\n💡 Solution:")
            print("   Contact your system administrator to enable calendar access.")

        elif status == 2:  # Denied
            print("\n❌ Calendar access was denied.")
            print("\n💡 Solution:")
            print("   1. Open System Settings")
            print("   2. Go to Privacy & Security > Calendars")
            print("   3. Find 'Python' or 'Terminal' and enable access")
            print("   4. Restart Terminal and try again")

        elif status >= 3:  # Authorized
            print("\n✅ Calendar access is granted!")

            # Try to get sources
            sources = event_store.sources()
            print(f"\nAvailable calendar sources: {len(sources)}")

            if len(sources) == 0:
                print("\n⚠️  No calendar sources found!")
                print("\n💡 This might mean:")
                print("   1. Calendar app has never been opened")
                print("   2. iCloud Calendar is not set up")
                print("   3. No calendar accounts are configured")
                print("\n💡 Solution:")
                print("   1. Open the Calendar app")
                print("   2. Go to Calendar > Settings (or Preferences)")
                print("   3. Check the 'Accounts' tab")
                print("   4. Ensure at least one account is enabled:")
                print("      - iCloud (recommended)")
                print("      - Or add a local calendar account")
                print("   5. Close and reopen Calendar app")
                print("   6. Try the export again")
            else:
                print("\n✅ Calendar sources are available!")
                for i, source in enumerate(sources, 1):
                    print(f"   {i}. {source.title()} (Type: {source.sourceType()})")

    except Exception as e:
        print(f"\n❌ Error checking permission: {e}")
        print("\n💡 This might indicate a system-level issue.")

    print("\n" + "="*60)


if __name__ == "__main__":
    check_permission()
