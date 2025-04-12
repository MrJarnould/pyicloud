"""Utility functions for the PyiCloud CLI auth commands."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudFailedLoginException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud.utils import (
    delete_password_in_keyring,
    get_password_from_keyring,
    password_exists_in_keyring,
    store_password_in_keyring,
)

console = Console()

# State storage
config_dir = os.path.expanduser("~/.config/pyicloud")
Path(config_dir).mkdir(parents=True, exist_ok=True)
session_path = os.path.join(config_dir, "session.json")
config_path = os.path.join(config_dir, "config.json")


def _handle_2fa(api: PyiCloudService) -> None:
    """Handle two-factor authentication if needed."""
    console.print("\nTwo-factor authentication required.")
    code: str = typer.prompt("Enter the verification code")
    result: bool = api.validate_2fa_code(code)
    if not result:
        console.print("[bold red]Failed to verify verification code[/bold red]")
        console.print("Please check that you entered the correct code and try again.")
        raise typer.Exit(1)

    if not api.is_trusted_session:
        console.print("Session is not trusted. Requesting trust...")
        result = api.trust_session()
        console.print(f"Session trust result: {result}")


def _handle_2sa(api: PyiCloudService) -> None:
    """Handle two-step authentication if needed."""
    console.print("\nTwo-step authentication required.")
    console.print("Your trusted devices are:")
    devices: List[Dict[str, Any]] = api.trusted_devices
    for i, device in enumerate(devices):
        device_name: str = device.get(
            "deviceName", f"SMS to {device.get('phoneNumber')}"
        )
        console.print(f"  {i}: {device_name}")

    device_index: int = typer.prompt("Which device would you like to use?", type=int)

    # Validate index is in range
    if device_index < 0 or device_index >= len(devices):
        console.print("[bold red]Error:[/bold red] Invalid device index")
        raise typer.Exit(1)

    device: Dict[str, Any] = devices[device_index]

    if not api.send_verification_code(device):
        console.print("[bold red]Failed to send verification code[/bold red]")
        console.print("Please check your device is connected and try again.")
        raise typer.Exit(1)

    code: str = typer.prompt("Please enter validation code")
    if not api.validate_verification_code(device, code):
        console.print("[bold red]Failed to verify verification code[/bold red]")
        console.print("Please check that you entered the correct code and try again.")
        raise typer.Exit(1)


def _save_credentials(username: str, password: Optional[str]) -> None:
    """Save user credentials."""
    # Create session file with minimal information
    session_data: Dict[str, str] = {"username": username}
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f)

    # Ensure file has restrictive permissions
    os.chmod(session_path, 0o600)

    # Handle password storage in keyring if appropriate
    if password and not password_exists_in_keyring(username):
        if typer.confirm("Save password in keyring?", default=False):
            store_password_in_keyring(username, password)


def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[yellow]Warning:[/yellow] Could not load config file: {exc}")
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        # Ensure file has restrictive permissions
        os.chmod(config_path, 0o600)
    except OSError as exc:
        console.print(f"[yellow]Warning:[/yellow] Could not save config file: {exc}")


def _get_username(provided_username: Optional[str] = None) -> str:
    """Determine the username to use for authentication."""
    # Try to load from session file first
    saved_username: Optional[str] = None
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            session_data: Dict[str, str] = json.load(f)
            saved_username = session_data.get("username")
    except (json.JSONDecodeError, OSError):
        pass

    # Load config for default settings
    config: Dict[str, Any] = load_config()

    # Determine username: command line arg > session file > config file > prompt
    username = provided_username or saved_username or config.get("username")
    if not username:
        username = typer.prompt("iCloud username (email)")

    return username


def _get_password(username: str, provided_password: Optional[str] = None) -> str:
    """Get password from provided value, keyring, or prompt."""
    if provided_password:
        return provided_password

    # Try to get from keyring
    password = get_password_from_keyring(username)
    if not password:
        password = typer.prompt("iCloud password", hide_input=True)

    return password


def _create_api_instance(
    username: str, password: str, china_mainland: bool
) -> PyiCloudService:
    """Create PyiCloud API instance and handle authentication challenges."""
    api = PyiCloudService(username, password, china_mainland=china_mainland)

    # Handle authentication challenges
    if api.requires_2fa:
        _handle_2fa(api)
    elif api.requires_2sa:
        _handle_2sa(api)

    # Save credentials if successful
    _save_credentials(username, password)

    return api


def _handle_failed_login(
    username: str, failure_count: int, max_retries: int, exc: Exception
) -> None:
    """Handle failed login attempt."""
    # If stored password didn't work, delete it
    if password_exists_in_keyring(username):
        delete_password_in_keyring(username)

    if failure_count >= max_retries:
        console.print(
            f"[bold red]Error:[/bold red] Invalid username or password for {username}"
        )
        console.print(
            Panel(
                "Please check your Apple ID and password are correct.\n"
                "If you use two-factor authentication, make sure it's properly set up.\n"
                "For Apple ID help, visit: https://support.apple.com/apple-id",
                title="Authentication Help",
                border_style="red",
            )
        )
        raise typer.Exit(1) from exc
    else:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Login failed. Attempts remaining: {max_retries - failure_count}"
        )


def _remove_session_files(username: Optional[str]) -> None:
    """Remove session-related files for a given username."""
    if not username:
        return

    # Delete keyring password
    if password_exists_in_keyring(username):
        delete_password_in_keyring(username)

    # Remove cookie and token files
    cookie_file = os.path.join(config_dir, f"{username}.cookiejar")
    session_file = os.path.join(config_dir, f"{username}.session")

    for file_path in [cookie_file, session_file]:
        if os.path.exists(file_path):
            os.remove(file_path)


def remove_session_files(username: Optional[str]) -> None:
    """Public wrapper to remove session-related files for a given username."""
    _remove_session_files(username)


def get_api_instance(
    username: Optional[str] = None,
    password: Optional[str] = None,
    china_mainland: Optional[bool] = None,
    max_retries: int = 3,
) -> PyiCloudService:
    """Get authenticated PyiCloudService instance."""
    # Get username
    resolved_username = _get_username(username)

    # Determine china_mainland setting
    config = load_config()
    resolved_china_mainland = (
        china_mainland
        if china_mainland is not None
        else config.get("china_mainland", False)
    )

    # Retry mechanism
    failure_count: int = 0
    current_password: Optional[str] = None

    while failure_count < max_retries:
        try:
            # Get password if not already obtained
            if not current_password:
                current_password = _get_password(resolved_username, password)

            # Attempt authentication
            api = _create_api_instance(
                resolved_username, current_password, resolved_china_mainland
            )

            # Clear sensitive data from memory before returning
            password = None
            temp = current_password
            current_password = None
            del temp

            return api

        except PyiCloudFailedLoginException as exc:
            failure_count += 1
            _handle_failed_login(resolved_username, failure_count, max_retries, exc)
            # Clear password to force re-prompting
            current_password = None

        except PyiCloudServiceNotActivatedException as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            console.print(
                Panel(
                    "Your iCloud account needs to be set up before using this tool.\n"
                    "Please complete the following steps:\n"
                    "1. Log in to https://icloud.com/ with your Apple ID\n"
                    "2. Accept any Terms and Conditions if prompted\n"
                    "3. Complete the initial setup process\n"
                    "4. Try logging in again with this tool",
                    title="Account Setup Required",
                    border_style="red",
                )
            )
            raise typer.Exit(1) from exc

        except PyiCloudAPIResponseException as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            console.print(
                Panel(
                    "Apple's iCloud API returned an unexpected response.\n"
                    "This could be due to:\n"
                    "- Temporary iCloud service disruption\n"
                    "- Network connectivity issues\n"
                    "- API changes that require this tool to be updated\n\n"
                    "Please try again later or check for updates to this tool.",
                    title="API Error",
                    border_style="red",
                )
            )
            raise typer.Exit(1) from exc

    # Should never reach here due to max_retries check
    console.print("[bold red]Error:[/bold red] Failed to authenticate")
    raise typer.Exit(1)
