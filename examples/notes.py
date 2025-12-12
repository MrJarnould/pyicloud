"""Example of how to use the Notes service."""

import argparse
import logging
from typing import Any, List

from rich import inspect, pretty, print_json
from rich.console import Console
from rich.traceback import install

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudServiceUnavailable
from pyicloud.utils import get_password

install(show_locals=True)
pretty.install()

console = Console()


def insp(arg):
    return inspect(arg, all=True, help=True)


def print_d(input_dict):
    return print_json(data=input_dict)


def ensure_auth(api: PyiCloudService) -> None:
    if api.requires_2fa:
        logging.info("Two-factor authentication required.")
        code = input("Enter the 2FA code: ")
        if not api.validate_2fa_code(code):
            raise RuntimeError("Failed to verify 2FA code")
        if not api.is_trusted_session:
            api.trust_session()
    elif api.requires_2sa:
        logging.info("Two-step authentication required.")
        devices: List[dict[str, Any]] = api.trusted_devices
        if not devices:
            raise RuntimeError("No trusted devices available for 2SA")
        for i, d in enumerate(devices):
            name = d.get("deviceName", f"SMS to {d.get('phoneNumber', 'unknown')}")
            logging.info(f"  {i}: {name}")
        sel = input("Select device index [0]: ").strip()
        try:
            idx = int(sel) if sel else 0
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(devices):
            logging.warning("Invalid selection; defaulting to device 0")
            idx = 0
        device = devices[idx]
        if not api.send_verification_code(device):
            raise RuntimeError("Failed to send verification code")
        code = input("Enter verification code: ")
        if not api.validate_verification_code(device, code):
            raise RuntimeError("Failed to verify code")


def main():
    """Main function."""
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Notes service example.")
    parser.add_argument("--username", required=True, help="Your Apple ID username.")
    parser.add_argument(
        "--password",
        help="Your Apple ID password. If not provided, you will be prompted.",
    )
    args = parser.parse_args()

    password = args.password or get_password(args.username)
    api = PyiCloudService(args.username, password)

    ensure_auth(api)

    try:
        notes_service = api.notes
    except PyiCloudServiceUnavailable:
        logging.error("Notes service is not available.")
        return

    insp(notes_service)
    """
    rprint("Fetching 5 most recent notes...")
    for note_idx, note_summary in enumerate(notes_service.recents(limit=5)):
        console.rule(f"Note #{note_idx}")
        rprint(note_summary, end="\n\n")
        note_id = note_summary.id
    """


if __name__ == "__main__":
    main()
