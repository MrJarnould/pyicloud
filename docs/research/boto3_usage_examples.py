"""
Boto3-Style PyiCloud Usage Examples

This file demonstrates how to use the new boto3-style PyiCloud architecture
with credential provider chains, service models, and resource interfaces.
"""

import os

from spike_architecture import (
    CloudSession,
    EnvironmentCredentialProvider,
    InteractiveCredentialProvider,
    Result,
)

# ======================== EXAMPLE 1: BASIC USAGE ========================


def basic_usage():
    """Basic boto3-style usage with automatic credential detection"""
    print("=== Example 1: Basic Usage ===")

    # Session automatically tries credential providers in order:
    # 1. Environment variables (APPLE_ID, APPLE_PASSWORD)
    # 2. System keyring (if apple_id provided)
    # 3. Interactive prompt
    session = CloudSession()

    if not session.is_authenticated():
        print("❌ No credentials available")
        return

    # High-level resource usage (recommended)
    devices_result = session.devices()
    if devices_result.is_success:
        device_collection = devices_result.value

        print(f"📱 Found {len(device_collection.all())} devices:")
        for device in device_collection.all():
            print(f"  - {device.name}: {device.battery_level}% battery")


# ======================== EXAMPLE 2: CUSTOM CREDENTIAL PROVIDERS ========================


def custom_credential_providers():
    """Using custom credential provider chain"""
    print("\n=== Example 2: Custom Credential Providers ===")

    # Create custom provider chain
    providers = [
        EnvironmentCredentialProvider(),
        InteractiveCredentialProvider(),  # Skip keyring
    ]

    session = CloudSession(credential_providers=providers)

    # Show which provider was used
    credentials = session.get_credentials()
    if credentials:
        print(f"✅ Using credentials for: {credentials.apple_id}")


# ======================== EXAMPLE 3: LOW-LEVEL CLIENT USAGE ========================


def low_level_client_usage():
    """Using low-level client for direct API calls"""
    print("\n=== Example 3: Low-Level Client Usage ===")

    session = CloudSession()

    # Get low-level client
    client_result = session.client("apple-device-management")
    if client_result.is_failure:
        print(f"❌ Client creation failed: {client_result.error.message}")
        return

    client = client_result.value

    # Direct API operation
    result = client.invoke_operation("LocateDevice", {})
    if result.is_success:
        print("✅ Raw API call successful")
        # result.value contains raw JSON response
    else:
        print(f"❌ API call failed: {result.error.message}")


# ======================== EXAMPLE 4: HIGH-LEVEL RESOURCE OPERATIONS ========================


def high_level_resource_operations():
    """Using high-level resource interface for device operations"""
    print("\n=== Example 4: High-Level Resource Operations ===")

    session = CloudSession()

    # Get resource interface
    resource_result = session.resource("apple-device-management")
    if resource_result.is_failure:
        print(f"❌ Resource creation failed: {resource_result.error.message}")
        return

    apple_devices = resource_result.value

    # High-level operations
    print("📱 Device Management Operations:")

    # Get all devices
    all_devices = apple_devices.devices.all()
    print(f"  • Total devices: {len(all_devices)}")

    # Filter devices
    low_battery = apple_devices.devices.filter(battery_below=20.0)
    print(f"  • Low battery devices: {len(low_battery)}")

    online_devices = apple_devices.devices.filter(online=True)
    print(f"  • Online devices: {len(online_devices)}")

    # Find device by name
    if all_devices:
        first_device = apple_devices.devices.find_by_name(all_devices[0].name)
        if first_device:
            print(f"  • Found device by name: {first_device.name}")


# ======================== EXAMPLE 5: DEVICE-SPECIFIC OPERATIONS ========================


def device_specific_operations():
    """Working with individual devices"""
    print("\n=== Example 5: Device-Specific Operations ===")

    session = CloudSession()
    devices_result = session.devices()

    if devices_result.is_failure:
        print(f"❌ Failed to get devices: {devices_result.error.message}")
        return

    device_collection = devices_result.value
    all_devices = device_collection.all()

    if not all_devices:
        print("📱 No devices found")
        return

    # Work with first device
    device = all_devices[0]
    print(f"📱 Working with device: {device.name}")

    # Device properties (lazy loaded)
    print(f"  • Battery: {device.battery_level}%")
    print(f"  • Device class: {device.device_class}")
    print(f"  • Online: {device.is_online}")

    # Get location
    location = device.last_location
    if location:
        print(f"  • Location: ({location.latitude:.4f}, {location.longitude:.4f})")
        print(f"  • Accuracy: ±{location.accuracy}m")
    else:
        print("  • Location: Not available")

    # Device operations can be performed using:
    # - device.play_sound("Test Sound")
    # - device.send_message(subject="Test", text="Message", play_sound=True)
    # - device.remote_wipe()  # Use with extreme caution!
    print("  • Available operations: play_sound, send_message, remote_wipe")


# ======================== EXAMPLE 6: BULK OPERATIONS ========================


def bulk_operations():
    """Performing operations on multiple devices"""
    print("\n=== Example 6: Bulk Operations ===")

    session = CloudSession()
    resource_result = session.resource("apple-device-management")

    if resource_result.is_failure:
        print(f"❌ Resource creation failed: {resource_result.error.message}")
        return

    apple_devices = resource_result.value

    # Get low battery devices
    low_battery_devices = apple_devices.get_low_battery_devices(threshold=30.0)
    print(f"🔋 Found {len(low_battery_devices)} devices with low battery")

    if low_battery_devices:
        print("🔋 Low battery devices:")
        for device in low_battery_devices:
            print(f"  - {device.name}: {device.battery_level}%")

        # Bulk operations available:
        # - apple_devices.play_sound_on_all_devices("Alert Message")
        # - apple_devices.locate_all_devices()
        print("  • Bulk operations: play_sound_on_all_devices, locate_all_devices")

    # Get offline devices
    offline_devices = apple_devices.get_offline_devices()
    if offline_devices:
        print(f"📴 Found {len(offline_devices)} offline devices:")
        for device in offline_devices:
            print(f"  - {device.name}")
    else:
        print("🌐 All devices are online")


# ======================== EXAMPLE 7: ERROR HANDLING PATTERNS ========================


def error_handling_patterns():
    """Demonstrating error handling with Result pattern"""
    print("\n=== Example 7: Error Handling Patterns ===")

    session = CloudSession()

    # Chain operations with Result pattern
    result = (
        session.devices()
        .flat_map(
            lambda devices: Result.success(devices.filter(online=True))
            if devices.all()
            else session.devices()
        )
        .map(
            lambda devices: len(devices.all())
            if hasattr(devices, "all")
            else len(devices)
        )
    )

    if result.is_success:
        print(f"✅ Found {result.value} online devices")
    else:
        print(f"❌ Operation failed: {result.error.message}")
        print(f"   Error code: {result.error.code}")
        print(f"   Retryable: {result.error.retryable}")

    # Alternative handling
    device_count = (
        session.devices().map(lambda devices: len(devices.all())).or_else(0)
    )  # Default to 0 on error

    print(f"📱 Device count (with fallback): {device_count}")


# ======================== EXAMPLE 8: EVENT HANDLING ========================


def event_handling():
    """Using event system for monitoring"""
    print("\n=== Example 8: Event Handling ===")

    session = CloudSession()

    # Register event handlers
    def log_before_call(operation, **_kwargs):
        print(f"🔄 Starting operation: {operation}")

    def log_after_call(operation, success, **_kwargs):
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{status} Operation completed: {operation}")

    session.add_event_handler("before-call.*", log_before_call)
    session.add_event_handler("after-call.*", log_after_call)

    # Operations will now trigger events
    print("📡 Making API call with event monitoring...")
    devices_result = session.devices()

    if devices_result.is_success:
        device_collection = devices_result.value
        print(f"📱 Found {len(device_collection.all())} devices with event monitoring")


# ======================== EXAMPLE 9: SERVICE INTROSPECTION ========================


def service_introspection():
    """Exploring available services and operations"""
    print("\n=== Example 9: Service Introspection ===")

    session = CloudSession()

    # List available services
    services = session.list_available_services()
    print(f"📋 Available services: {services}")

    # Get service information
    if "apple-device-management" in services:
        client_result = session.client("apple-device-management")
        if client_result.is_success:
            client = client_result.value
            service_model = client.service_model

            print(f"🔧 Service: {service_model.name}")
            print(f"🌐 Base URL: {service_model.base_url}")
            print(f"📡 Protocol: {service_model.default_protocol}")
            print("🛠️  Available operations:")
            for op_name, op_model in service_model.operations.items():
                print(f"  - {op_name}: {op_model.method} {op_model.endpoint}")


# ======================== EXAMPLE 10: FUNCTIONAL PROGRAMMING PATTERNS ========================


def functional_patterns():
    """Using functional programming patterns with Result"""
    print("\n=== Example 10: Functional Programming Patterns ===")

    session = CloudSession()

    # Functional chain with Result pattern
    device_names = (
        session.devices()
        .map(lambda devices: devices.all())
        .map(lambda device_list: [d.name for d in device_list])
        .or_else([])
    )

    print(f"📱 Device names: {device_names}")

    # Filter and transform
    battery_levels = (
        session.devices()
        .map(lambda devices: devices.all())
        .map(
            lambda device_list: [
                d.battery_level for d in device_list if d.battery_level
            ]
        )
        .or_else([])
    )

    if battery_levels:
        avg_battery = sum(battery_levels) / len(battery_levels)
        print(f"🔋 Average battery level: {avg_battery:.1f}%")

    # Complex filtering
    critical_devices = (
        session.devices()
        .map(lambda devices: devices.filter(battery_below=10.0))
        .filter(lambda devices: len(devices) > 0)
        .or_else([])
    )

    if critical_devices:
        print(f"⚠️ {len(critical_devices)} devices have critical battery levels")


def main():
    """Run all examples"""
    print("🚀 Boto3-Style PyiCloud Usage Examples")
    print("=" * 50)

    # Check for credentials
    if not os.environ.get("APPLE_ID"):
        print(
            "💡 Set APPLE_ID and APPLE_PASSWORD environment variables for automatic authentication"
        )
        print()

    examples = [
        basic_usage,
        custom_credential_providers,
        low_level_client_usage,
        high_level_resource_operations,
        device_specific_operations,
        bulk_operations,
        error_handling_patterns,
        event_handling,
        service_introspection,
        functional_patterns,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        print()


if __name__ == "__main__":
    main()
