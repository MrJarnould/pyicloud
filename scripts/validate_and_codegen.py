# scripts/validate_and_codegen.py
"""
Validate devices.json against schema and generate Python enums using modern best practices.

Usage:
    python scripts/validate_and_codegen.py \
        --schema devices.schema.json \
        --data devices.json \
        --output generated/device_models.py
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from jinja2 import Template
from jsonschema import ValidationError, validate


@dataclass
class EnumMember:
    """Represents a single enum member with name and value."""

    name: str
    value: str


@dataclass
class EnumClass:
    """Represents a complete enum class with metadata and members."""

    name: str
    docstring: str
    members: List[EnumMember]


@dataclass
class DeviceEntry:
    """Represents a single device entry focused on rawDeviceModel mappings."""

    device_class: str
    raw_model: str
    display_name: str
    class_enum_name: str
    raw_enum_name: str
    display_enum_name: str


class StringCleaner:
    """Centralized string cleaning utilities using efficient regex patterns."""

    # Compile regex patterns once for better performance
    INVALID_CHARS = re.compile(r"[^A-Z0-9_]")  # Keep only alphanumeric and underscore
    MULTIPLE_UNDERSCORES = re.compile(
        r"_{2,}"
    )  # Match 2 or more consecutive underscores
    LEADING_TRAILING_UNDERSCORES = re.compile(
        r"(^_+)|(_+$)"
    )  # Leading/trailing underscores

    @classmethod
    def create_python_identifier(cls, text: str) -> str:
        """Create a valid Python identifier from arbitrary text using regex."""
        # Step 1: Convert to uppercase
        identifier = text.upper()

        # Step 2: Replace invalid characters with underscores (single regex operation)
        identifier = cls.INVALID_CHARS.sub("_", identifier)

        # Step 3: Collapse multiple underscores to single (single regex operation)
        identifier = cls.MULTIPLE_UNDERSCORES.sub("_", identifier)

        # Step 4: Remove leading/trailing underscores (single regex operation)
        identifier = cls.LEADING_TRAILING_UNDERSCORES.sub("", identifier)

        # Step 5: Ensure identifier doesn't start with a digit (Python requirement)
        if identifier and identifier[0].isdigit():
            identifier = "N" + identifier  # Prefix with 'N' for numeric start

        return identifier or "UNKNOWN"  # Fallback for edge cases


class DataProcessor:
    """Processes raw device data into structured enum classes."""

    @staticmethod
    def create_valid_identifier(text: str) -> str:
        """Create a valid Python identifier from arbitrary text."""
        return StringCleaner.create_python_identifier(text)

    @staticmethod
    def create_raw_device_identifier(raw_model: str) -> str:
        """Create identifier for raw device model enum."""
        # Use the same robust cleaning logic for consistency
        return StringCleaner.create_python_identifier(raw_model)

    @classmethod
    def process_device_data(
        cls, data: List[dict]
    ) -> tuple[List[EnumClass], List[DeviceEntry]]:
        """Process raw device data into structured enum classes and device entries."""
        processor = cls()

        # Create device entries with all relationships
        device_entries = []
        for item in data:
            entry = DeviceEntry(
                device_class=item["class"],
                raw_model=item["raw"],
                display_name=item["display"],
                class_enum_name=processor.create_valid_identifier(item["class"]),
                raw_enum_name=processor.create_raw_device_identifier(item["raw"]),
                display_enum_name=processor.create_valid_identifier(item["display"]),
            )
            device_entries.append(entry)

        # Extract unique device classes
        device_classes = sorted({item["class"] for item in data})
        device_class_members = [
            EnumMember(name=processor.create_valid_identifier(cls_name), value=cls_name)
            for cls_name in device_classes
        ]

        # Process raw device models
        raw_device_members = [
            EnumMember(
                name=processor.create_raw_device_identifier(item["raw"]),
                value=item["raw"],
            )
            for item in data
        ]

        # Process display names with unique identifiers
        display_name_members = []
        seen_identifiers = set()
        for _, item in enumerate(data):
            base_identifier = processor.create_valid_identifier(item["display"])
            identifier = base_identifier
            # Handle duplicates by adding a suffix
            counter = 1
            while identifier in seen_identifiers:
                identifier = f"{base_identifier}_{counter}"
                counter += 1
            seen_identifiers.add(identifier)
            display_name_members.append(
                EnumMember(name=identifier, value=item["display"])
            )

        enum_classes = [
            EnumClass(
                name="DeviceClass",
                docstring="Device family/class enumeration (e.g., iPhone, iPad, Apple TV).",
                members=device_class_members,
            ),
            EnumClass(
                name="RawDeviceModel",
                docstring="Raw device model identifiers from Apple's rawDeviceModel field (e.g., iPhone17,5, iPad8,1).",
                members=raw_device_members,
            ),
            EnumClass(
                name="DeviceDisplayName",
                docstring='Human-readable device display names (e.g., "iPhone 16e", "Apple TV 4K").',
                members=display_name_members,
            ),
        ]

        return enum_classes, device_entries


class CodeGenerator:
    """Generates Python code from structured enum data using Jinja2 templates."""

    TEMPLATE = Template('''"""Generated device models - DO NOT EDIT. Regenerate via scripts/validate_and_codegen.py"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict


{% for enum_class in enums -%}
class {{ enum_class.name }}(str, Enum):
    """{{ enum_class.docstring }}"""
{% for member in enum_class.members %}
    {{ member.name }} = "{{ member.value }}"
{%- endfor %}


{% endfor %}

@dataclass
class DeviceInfo:
    """Device information based on Apple's rawDeviceModel field with intelligent methods."""

    device_class: DeviceClass
    raw_model: RawDeviceModel
    display_name: DeviceDisplayName

    @classmethod
    def from_raw(cls, raw_identifier: str) -> Optional['DeviceInfo']:
        """Smart constructor from Apple's rawDeviceModel identifier.

        Args:
            raw_identifier: rawDeviceModel value like "iPhone17,5", "iPad8,1", "Watch6,7"

        Returns:
            DeviceInfo instance if device is known, None otherwise

        Example:
            device = DeviceInfo.from_raw("iPhone17,5")
            if device:
                print(f"{device.display_name} is a {device.device_class}")
        """
        return _DEVICE_REGISTRY.get(raw_identifier)

    @classmethod
    def all_devices(cls) -> List['DeviceInfo']:
        """Get all known devices."""
        return list(_DEVICE_REGISTRY.values())

    @classmethod
    def filter_by_class(cls, device_class: DeviceClass) -> List['DeviceInfo']:
        """Get all devices of a specific class.

        Args:
            device_class: Device class to filter by

        Returns:
            List of matching devices

        Example:
            iphones = DeviceInfo.filter_by_class(DeviceClass.IPHONE)
        """
        return [d for d in cls.all_devices() if d.device_class == device_class]

    def is_iphone(self) -> bool:
        """Check if this device is an iPhone."""
        return self.device_class == DeviceClass.IPHONE

    def is_ipad(self) -> bool:
        """Check if this device is an iPad."""
        return self.device_class == DeviceClass.IPAD

    def is_mac(self) -> bool:
        """Check if this device is a Mac."""
        return self.device_class.value.startswith("Mac")

    def is_apple_tv(self) -> bool:
        """Check if this device is an Apple TV."""
        return self.device_class == DeviceClass.APPLE_TV

    def __str__(self) -> str:
        return f"{self.display_name} ({self.raw_model.value})"

    def __repr__(self) -> str:
        return f"DeviceInfo(class={self.device_class.value}, raw={self.raw_model.value}, display='{self.display_name.value}')"


# Generated device registry for fast lookups
_DEVICE_REGISTRY: Dict[str, DeviceInfo] = {
{% for device in devices -%}
    "{{ device.raw_model }}": DeviceInfo(
        device_class=DeviceClass.{{ device.class_enum_name }},
        raw_model=RawDeviceModel.{{ device.raw_enum_name }},
        display_name=DeviceDisplayName.{{ device.display_enum_name }}
    ),
{% endfor -%}
}


# Convenience functions for simple lookups
def get_display_name(raw_model: str) -> Optional[str]:
    """Get display name for Apple's rawDeviceModel value.

    Args:
        raw_model: rawDeviceModel value like "iPhone17,5", "iPad8,1"

    Returns:
        Human-readable display name or None if unknown

    Example:
        name = get_display_name("iPhone17,5")  # → "iPhone 16e"
        name = get_display_name("iPad8,1")     # → "iPad Pro 11-inch"
    """
    device = DeviceInfo.from_raw(raw_model)
    return device.display_name.value if device else None


def get_device_class(raw_model: str) -> Optional[str]:
    """Get device class for Apple's rawDeviceModel value.

    Args:
        raw_model: rawDeviceModel value like "iPhone17,5", "iPad8,1"

    Returns:
        Device class string or None if unknown

    Example:
        class_name = get_device_class("iPhone17,5")  # → "iPhone"
        class_name = get_device_class("iPad8,1")     # → "iPad"
    """
    device = DeviceInfo.from_raw(raw_model)
    return device.device_class.value if device else None


def resolve_device(raw_model: str) -> Optional[DeviceInfo]:
    """One-stop device resolution from Apple's rawDeviceModel value.

    Args:
        raw_model: rawDeviceModel value like "iPhone17,5", "iPad8,1"

    Returns:
        Complete DeviceInfo or None if unknown

    Example:
        device = resolve_device("iPhone17,5")
        if device:
            print(f"Found: {device}")
            if device.is_iphone():
                print("It's an iPhone!")
    """
    return DeviceInfo.from_raw(raw_model)
''')

    @classmethod
    def generate_code(
        cls, enum_classes: List[EnumClass], device_entries: List[DeviceEntry]
    ) -> str:
        """Generate Python code from enum classes and device entries."""
        return cls.TEMPLATE.render(enums=enum_classes, devices=device_entries)


class FileManager:
    """Handles file operations and formatting."""

    @staticmethod
    def load_json(path: Path):
        """Load and parse a JSON file."""
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def write_code(content: str, output_path: Path) -> None:
        """Write generated code to file and format with Ruff."""
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the generated code
        output_path.write_text(content, encoding="utf-8")

        # Format with Black (fallback to Ruff if needed)
        formatters = [
            ["black", str(output_path)],
            ["uv", "run", "ruff", "format", str(output_path)],
        ]

        formatted = False
        for formatter in formatters:
            try:
                subprocess.run(formatter, check=True, capture_output=True)
                formatted = True
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue

        if not formatted:
            print(
                "⚠️  Warning: No formatter available (tried Black, Ruff), skipping formatting",
                file=sys.stderr,
            )


def validate_data(data: dict, schema: dict, data_path: Path) -> None:
    """Validate device data against JSON schema."""
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        print(f"🚨 Validation error in {data_path}: {e.message}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function orchestrating the validation and code generation process."""
    parser = argparse.ArgumentParser(description="Validate & generate device enums")
    parser.add_argument("--schema", type=Path, required=True, help="JSON Schema path")
    parser.add_argument("--data", type=Path, required=True, help="devices.json path")
    parser.add_argument("--output", type=Path, required=True, help="Output Python file")
    args = parser.parse_args()

    # Load and validate data
    schema = FileManager.load_json(args.schema)
    device_data = FileManager.load_json(args.data)
    validate_data(device_data, schema, args.data)

    # Process data into structured format
    enum_classes, device_entries = DataProcessor.process_device_data(device_data)

    # Generate code from templates
    generated_code = CodeGenerator.generate_code(enum_classes, device_entries)

    # Write and format output
    FileManager.write_code(generated_code, args.output)

    print(f"✅ Generated {args.output} with {len(device_entries)} device mappings")


if __name__ == "__main__":
    main()

# ---------------------
# DESIGN DECISION: Focus on rawDeviceModel only
#
# Apple's Find My API provides multiple device identifier fields:
# - rawDeviceModel: Consistent, documented pattern (e.g., "iPhone17,5", "iPad8,1")
# - deviceModel: Opaque, contains metadata (e.g., "iphone12Pro-1-1-0", "iPad8_1-1-1-0")
# - deviceDisplayName: Human-readable but inconsistent formatting
#
# This system focuses ONLY on rawDeviceModel because:
# 1. It's the most consistent field across all device types
# 2. deviceModel contains undocumented encoding (color, config, etc.)
# 3. Trying to parse deviceModel would be reverse-engineering Apple's internals
# 4. rawDeviceModel is sufficient for device identification and feature detection
#
# Example integration in your Pydantic model file:
#
# from generated.device_models import DeviceClass, RawDeviceModel, DeviceDisplayName
# from pydantic import BaseModel, Field
#
# class MyDevice(BaseModel):
#     device_class: DeviceClass = Field(..., description="Family of device, e.g. iPhone")
#     raw_model: RawDeviceModel = Field(..., description="rawDeviceModel, e.g. iPhone17,5")
#     display_name: DeviceDisplayName = Field(..., description="Friendly name")
#
#     # Store deviceModel as opaque field - don't try to parse it
#     device_model: Optional[str] = Field(None, description="Opaque deviceModel from API")
#
# Usage:
#   device_info = resolve_device("iPhone17,5")  # rawDeviceModel lookup
#   if device_info:
#       d = MyDevice(
#           device_class=device_info.device_class,
#           raw_model=device_info.raw_model,
#           display_name=device_info.display_name,
#           device_model="iphone12Pro-1-1-0"  # Store as-is, don't parse
#       )
