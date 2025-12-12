#!/usr/bin/env python3
"""
Generate comprehensive devices.json from AppleDB data.

This script processes the complete AppleDB dataset to generate a comprehensive
devices.json file with proper device class mappings and Find My compatibility.

Key features:
- Maps AppleDB device types to Find My deviceClass values
- Converts AirPods Device1,XXXX to AirPods_XXXX format
- Handles device deduplication intelligently
- Validates against real Find My API data patterns
- Generates 450+ device entries from authoritative Apple data

Usage:
    python scripts/generate_devices_file.py
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set


class DeviceClassMapper:
    """Maps AppleDB device types to Find My deviceClass values."""

    # Validated mapping based on real Find My API data analysis
    APPLEDB_TO_FINDMY_MAPPING = {
        # Core Apple devices with standard identifier patterns
        "iPhone": "iPhone",
        "iPad": "iPad",
        "iPad Pro": "iPad",
        "iPad Air": "iPad",
        "iPad mini": "iPad",
        "iPod touch": "iPod",
        "Apple Watch": "Watch",
        "Apple TV": "Apple TV",
        # Mac devices (exact class names from real API data)
        "MacBook Pro": "MacBookPro",
        "MacBook Air": "MacBookAir",
        "MacBook": "MacBook",
        "Mac mini": "Macmini",
        "Mac Pro": "Mac Pro",
        "Mac Studio": "Mac Studio",
        "iMac": "iMac",
        "iMac Pro": "iMac Pro",
        # Find My accessories (all use "Accessory" class)
        "AirPods": "Accessory",
        "AirTag": "Accessory",
        "Beats Earbuds": "Accessory",
        "Beats Headphones": "Accessory",
        "HomePod": "Accessory",
    }

    @classmethod
    def get_device_class(cls, appledb_type: str) -> Optional[str]:
        """Get Find My deviceClass for AppleDB device type."""
        return cls.APPLEDB_TO_FINDMY_MAPPING.get(appledb_type)

    @classmethod
    def is_supported_type(cls, appledb_type: str) -> bool:
        """Check if AppleDB device type is supported for Find My."""
        return appledb_type in cls.APPLEDB_TO_FINDMY_MAPPING


class AirPodsConverter:
    """Converts AirPods Device1,XXXX identifiers to AirPods_XXXX format and provides Find My API-compatible display names."""

    # Mapping from AirPods_XXXX to Find My API-compatible display names
    # Based on real Find My API data analysis
    AIRPODS_DISPLAY_NAMES = {
        "AirPods_8194": "AirPods",  # AirPods 1st generation
        "AirPods_8202": "AirPods Max",  # AirPods Max
        "AirPods_8206": "AirPods Pro",  # AirPods Pro 1st generation
        "AirPods_8207": "AirPods",  # AirPods 2nd generation
        "AirPods_8211": "AirPods",  # AirPods 3rd generation
        "AirPods_8212": "AirPods Pro (2nd generation)",  # AirPods Pro 2nd generation
        "AirPods_8217": "AirPods 4",  # AirPods 4
        "AirPods_8219": "AirPods 4 with Active Noise Cancellation",  # AirPods 4 ANC
        "AirPods_8223": "AirPods Max with USB-C",  # AirPods Max USB-C
        "AirPods_8228": "AirPods Pro (2nd generation)",  # AirPods Pro 2nd generation
    }

    @staticmethod
    def extract_device1_number(identifier: str) -> Optional[str]:
        """Extract number from Device1,XXXX pattern."""
        match = re.match(r"Device1,(\d+)", identifier)
        return match.group(1) if match else None

    @classmethod
    def convert_to_airpods_format(cls, device1_identifier: str) -> Optional[str]:
        """Convert Device1,XXXX to AirPods_XXXX format."""
        number = cls.extract_device1_number(device1_identifier)
        return f"AirPods_{number}" if number else None

    @classmethod
    def get_find_my_display_name(cls, airpods_raw_model: str) -> Optional[str]:
        """Get Find My API-compatible display name for AirPods rawDeviceModel."""
        return cls.AIRPODS_DISPLAY_NAMES.get(airpods_raw_model)

    @classmethod
    def select_best_display_name(cls, names: List[str], raw_model: str = None) -> str:
        """Select the best display name for AirPods, preferring Find My API format."""
        # If we have the raw model, use our mapping for Find My API compatibility
        if raw_model and raw_model.startswith("AirPods_"):
            find_my_name = cls.get_find_my_display_name(raw_model)
            if find_my_name:
                return find_my_name

        # Fallback to original logic for cases where mapping doesn't exist
        # Priority: generic names > specific Left/Right variants > charging cases
        priorities = [
            # Generic AirPods names (highest priority)
            lambda name: not any(
                keyword in name.lower()
                for keyword in ["left", "right", "case", "charging"]
            ),
            # Left/Right variants (medium priority)
            lambda name: any(keyword in name.lower() for keyword in ["left", "right"]),
            # Charging cases (lowest priority)
            lambda name: "case" in name.lower(),
        ]

        for priority_func in priorities:
            matching_names = [name for name in names if priority_func(name)]
            if matching_names:
                # Return shortest name within this priority level
                return min(matching_names, key=len)

        # Fallback: return shortest name overall
        return min(names, key=len)


class DeviceExtractor:
    """Extracts and processes device entries from AppleDB data."""

    def __init__(self, appledb_data: List[Dict]):
        self.appledb_data = appledb_data
        self.device_mapper = DeviceClassMapper()
        self.airpods_converter = AirPodsConverter()

    def extract_all_devices(self) -> List[Dict[str, str]]:
        """Extract all supported devices from AppleDB."""
        devices = []

        for device in self.appledb_data:
            extracted_device = self._extract_single_device(device)
            if extracted_device:
                devices.append(extracted_device)

        return devices

    def _extract_single_device(self, device: Dict) -> Optional[Dict[str, str]]:
        """Extract a single device entry from AppleDB device data."""
        device_type = device.get("type")
        identifiers = device.get("identifier", [])
        device_name = device.get("name", "")

        # Skip unsupported device types or devices without identifiers
        if (
            not identifiers
            or not device_type
            or not self.device_mapper.is_supported_type(device_type)
        ):
            return None

        device_class = self.device_mapper.get_device_class(device_type)
        raw_device_model = self._determine_raw_device_model(device_type, identifiers)

        if not raw_device_model or not device_class:
            return None

        # For AirPods, use Find My API-compatible display name
        if raw_device_model.startswith("AirPods_"):
            find_my_display_name = self.airpods_converter.get_find_my_display_name(
                raw_device_model
            )
            if find_my_display_name:
                device_name = find_my_display_name

        return {
            "class": device_class,
            "raw": raw_device_model,
            "display": device_name,
            "appledb_type": device_type,  # Keep for debugging/validation
        }

    def _determine_raw_device_model(
        self, device_type: str, identifiers: List[str]
    ) -> Optional[str]:
        """Determine the correct rawDeviceModel from AppleDB identifiers."""
        if device_type == "AirPods":
            return self._handle_airpods_identifier(identifiers)
        elif device_type in ["AirTag", "Beats Earbuds", "Beats Headphones", "HomePod"]:
            return self._handle_accessory_identifier(identifiers)
        else:
            return self._handle_standard_identifier(identifiers)

    def _handle_airpods_identifier(self, identifiers: List[str]) -> Optional[str]:
        """Handle AirPods Device1,XXXX → AirPods_XXXX conversion."""
        device1_identifiers = [id for id in identifiers if id.startswith("Device1,")]
        if device1_identifiers:
            return self.airpods_converter.convert_to_airpods_format(
                device1_identifiers[0]
            )
        return None

    def _handle_accessory_identifier(self, identifiers: List[str]) -> Optional[str]:
        """Handle other accessories with Device1,XXXX pattern."""
        device1_identifiers = [id for id in identifiers if id.startswith("Device1,")]
        if device1_identifiers:
            # For now, keep Device1,XXXX format for non-AirPods accessories
            # Future enhancement: could convert to standardized format
            return device1_identifiers[0]
        return identifiers[0] if identifiers else None

    def _handle_standard_identifier(self, identifiers: List[str]) -> str:
        """Handle standard device identifiers (iPhone, iPad, etc.)."""
        return identifiers[0]


class DeviceDeduplicator:
    """Handles deduplication of devices with identical rawDeviceModel values."""

    def __init__(self, airpods_converter: AirPodsConverter):
        self.airpods_converter = airpods_converter

    def deduplicate_devices(
        self, devices: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Remove duplicate devices and select best display names."""
        # Group devices by rawDeviceModel
        grouped_devices = defaultdict(list)
        for device in devices:
            grouped_devices[device["raw"]].append(device)

        deduplicated = []
        for raw_model, device_group in grouped_devices.items():
            if len(device_group) == 1:
                deduplicated.append(device_group[0])
            else:
                best_device = self._select_best_device(device_group)
                deduplicated.append(best_device)

        return deduplicated

    def _select_best_device(self, device_group: List[Dict[str, str]]) -> Dict[str, str]:
        """Select the best device from a group of duplicates."""
        display_names = [device["display"] for device in device_group]
        raw_model = device_group[0]["raw"]  # All devices in group have same raw model

        # Use AirPods-specific logic for AirPods devices
        if raw_model.startswith("AirPods_"):
            best_name = self.airpods_converter.select_best_display_name(
                display_names, raw_model
            )
        else:
            # For other devices, select shortest/most generic name
            best_name = min(display_names, key=len)

        # Find the device with the selected name
        for device in device_group:
            if device["display"] == best_name:
                return device

        # Fallback: return first device
        return device_group[0]


class DeviceValidator:
    """Validates generated devices against real Find My API data."""

    def __init__(self, real_data_path: str = "data.json"):
        self.real_data_path = real_data_path
        self.real_raw_models = self._load_real_raw_models()

    def _load_real_raw_models(self) -> Set[str]:
        """Load rawDeviceModel values from real Find My API data."""
        try:
            with Path(self.real_data_path).open("r") as f:
                real_data = json.load(f)

            raw_models = set()
            for device in real_data.get("content", []):
                raw_models.add(device["rawDeviceModel"])

            return raw_models
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            print(f"⚠️  Warning: Could not load real data from {self.real_data_path}")
            return set()

    def validate_coverage(
        self, generated_devices: List[Dict[str, str]]
    ) -> Dict[str, any]:
        """Validate coverage of generated devices against real data."""
        if not self.real_raw_models:
            return {
                "coverage_percent": 0,
                "covered_models": set(),
                "missing_models": set(),
            }

        generated_raw_models = {device["raw"] for device in generated_devices}
        covered_models = self.real_raw_models.intersection(generated_raw_models)
        missing_models = self.real_raw_models - generated_raw_models
        coverage_percent = (len(covered_models) / len(self.real_raw_models)) * 100

        return {
            "coverage_percent": coverage_percent,
            "covered_models": covered_models,
            "missing_models": missing_models,
            "total_real": len(self.real_raw_models),
            "total_covered": len(covered_models),
        }


class DeviceFileGenerator:
    """Main class for generating devices.json from AppleDB data."""

    def __init__(
        self, appledb_path: str = "appledb.json", output_path: str = "devices.json"
    ):
        self.appledb_path = appledb_path
        self.output_path = output_path

        # Load AppleDB data
        self.appledb_data = self._load_appledb_data()

        # Initialize components
        self.extractor = DeviceExtractor(self.appledb_data)
        self.deduplicator = DeviceDeduplicator(AirPodsConverter())
        self.validator = DeviceValidator()

    def _load_appledb_data(self) -> List[Dict]:
        """Load AppleDB data from file."""
        try:
            with Path(self.appledb_path).open("r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"Failed to load AppleDB data from {self.appledb_path}: {e}"
            )

    def generate_devices_file(self) -> bool:
        """Generate comprehensive devices.json from AppleDB data."""
        print("🚀 Generating comprehensive devices.json from AppleDB")
        print("=" * 55)

        try:
            # Step 1: Extract devices
            print("📤 Extracting devices from AppleDB...")
            raw_devices = self.extractor.extract_all_devices()
            print(f"   ✅ Extracted {len(raw_devices)} raw device entries")

            # Step 2: Deduplicate
            print("🔄 Deduplicating devices...")
            devices = self.deduplicator.deduplicate_devices(raw_devices)
            print(f"   ✅ Deduplicated to {len(devices)} unique devices")

            # Step 3: Validate coverage
            print("✅ Validating coverage against real Find My data...")
            validation_results = self.validator.validate_coverage(devices)
            self._print_validation_results(validation_results)

            # Step 4: Generate output
            print("💾 Writing devices.json...")
            self._write_devices_file(devices)
            print(f"   ✅ Generated {self.output_path}")

            # Step 5: Summary
            self._print_summary(devices, validation_results)

            return True

        except Exception as e:
            print(f"❌ Generation failed: {e}")
            return False

    def _print_validation_results(self, results: Dict[str, any]) -> None:
        """Print validation results."""
        coverage = results["coverage_percent"]
        print(
            f"   ✅ Coverage: {results['total_covered']}/{results['total_real']} ({coverage:.1f}%)"
        )

        if results["missing_models"]:
            print(
                f"   ⚠️  Missing models: {', '.join(sorted(results['missing_models']))}"
            )

    def _write_devices_file(self, devices: List[Dict[str, str]]) -> None:
        """Write devices to JSON file."""
        # Remove internal fields before writing
        clean_devices = []
        for device in devices:
            clean_device = {
                "class": device["class"],
                "raw": device["raw"],
                "display": device["display"],
            }
            clean_devices.append(clean_device)

        # Sort devices for consistent output
        clean_devices.sort(key=lambda d: (d["class"], d["raw"]))

        with Path(self.output_path).open("w") as f:
            json.dump(clean_devices, f, indent="\t", ensure_ascii=False)

    def _print_summary(
        self, devices: List[Dict[str, str]], validation_results: Dict[str, any]
    ) -> None:
        """Print generation summary."""
        print("\n📊 Generation Summary")
        print("=" * 25)

        # Device count by class
        class_counts = defaultdict(int)
        for device in devices:
            class_counts[device["class"]] += 1

        print(f"📈 Total devices generated: {len(devices)}")
        print(f"🎯 Real data coverage: {validation_results['coverage_percent']:.1f}%")
        print("\n📋 Device breakdown:")
        for device_class, count in sorted(class_counts.items()):
            print(f"   {device_class}: {count} devices")


def main():
    """Main function to generate devices.json."""
    generator = DeviceFileGenerator()
    success = generator.generate_devices_file()

    if success:
        print("\n🎉 SUCCESS: Comprehensive devices.json generated!")
        print("   Next steps:")
        print("   1. Validate with: uv run python scripts/validate_and_codegen.py")
        print("   2. Regenerate enums with updated comprehensive data")
    else:
        print("\n❌ FAILED: Could not generate devices.json")

    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
