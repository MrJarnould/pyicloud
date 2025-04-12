"""Authentication module for the PyiCloud CLI."""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

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

app = typer.Typer(help="Authentication commands")
console = Console()

# State storage
config_dir = os.path.expanduser("~/.config/pyicloud")
Path(config_dir).mkdir(parents=True, exist_ok=True)
session_path = os.path.join(config_dir, "session.json")


def _handle_2fa(api):
    """Handle two-factor authentication if needed."""
    console.print("\nTwo-factor authentication required.")
    code = typer.prompt("Enter the verification code")
    result = api.validate_2fa_code(code)
    if not result:
        console.print("[bold red]Failed to verify verification code[/bold red]")
        raise typer.Exit(1)

    if not api.is_trusted_session:
        console.print("Session is not trusted. Requesting trust...")
        result = api.trust_session()
        console.print(f"Session trust result: {result}")


def _handle_2sa(api):
    """Handle two-step authentication if needed."""
    console.print("\nTwo-step authentication required.")
    console.print("Your trusted devices are:")
    devices = api.trusted_devices
    for i, device in enumerate(devices):
        device_name = device.get("deviceName", f"SMS to {device.get('phoneNumber')}")
        console.print(f"  {i}: {device_name}")

    device_index = typer.prompt("Which device would you like to use?", type=int)
    device = devices[device_index]

    if not api.send_verification_code(device):
        console.print("[bold red]Failed to send verification code[/bold red]")
        raise typer.Exit(1)

    code = typer.prompt("Please enter validation code")
    if not api.validate_verification_code(device, code):
        console.print("[bold red]Failed to verify verification code[/bold red]")
        raise typer.Exit(1)


def _save_credentials(username, password):
    """Save user credentials."""
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump({"username": username}, f)

    if password and not password_exists_in_keyring(username):
        if typer.confirm("Save password in keyring?", default=False):
            store_password_in_keyring(username, password)


def get_api_instance(
    username: Optional[str] = None,
    password: Optional[str] = None,
    china_mainland: bool = False,
    max_retries: int = 3,
):
    """Get authenticated PyiCloudService instance."""
    # Try to load from session file first
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            saved_username = json.load(f).get("username")
            username = username or saved_username
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if not username:
        username = typer.prompt("iCloud username (email)")

    # Retry mechanism
    failure_count = 0
    while failure_count < max_retries:
        if not password:
            # Try to get from keyring
            password = get_password_from_keyring(username)
            if not password:
                password = typer.prompt("iCloud password", hide_input=True)

        # Create API instance
        try:
            api = PyiCloudService(username, password, china_mainland=china_mainland)

            # Handle authentication challenges
            if api.requires_2fa:
                _handle_2fa(api)
            elif api.requires_2sa:
                _handle_2sa(api)

            # Save credentials if successful
            _save_credentials(username, password)

            return api

        except PyiCloudFailedLoginException as exc:
            failure_count += 1
            # If stored password didn't work, delete it
            if password_exists_in_keyring(username):
                delete_password_in_keyring(username)

            password = None  # Reset password to force re-prompting

            if failure_count >= max_retries:
                console.print(
                    f"[bold red]Error:[/bold red] Invalid username or password for {username}"
                )
                raise typer.Exit(1) from exc
            else:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] Login failed. Attempts remaining: {max_retries - failure_count}"
                )

        except PyiCloudServiceNotActivatedException as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            console.print(
                "Please log in to https://icloud.com/ to set up your iCloud account"
            )
            raise typer.Exit(1) from exc

        except PyiCloudAPIResponseException as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1) from exc

    # Should never reach here due to max_retries check
    console.print("[bold red]Error:[/bold red] Failed to authenticate")
    raise typer.Exit(1)


@app.command("login")
def login(
    username: Optional[str] = typer.Option(None, help="Apple ID (email)"),
    password: Optional[str] = typer.Option(None, help="iCloud password"),
    china_mainland: bool = typer.Option(
        False, help="Set if your Apple ID is based in China mainland"
    ),
):
    """Login to iCloud."""
    api = get_api_instance(username, password, china_mainland)
    console.print(f"Successfully logged in as [bold]{api.account_name}[/bold]")


@app.command("logout")
def logout():
    """Remove saved credentials."""
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            username = json.load(f).get("username")
        if username:
            delete_password_in_keyring(username)
        os.remove(session_path)
        console.print("Logged out successfully")
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
    ):
        console.print("No session found")
