"""Authentication module for the PyiCloud CLI."""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException
from pyicloud.utils import (
    delete_password_in_keyring,
    get_password_from_keyring,
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
    code = typer.prompt("Enter the verification code")
    result = api.validate_2fa_code(code)
    if not result:
        typer.echo("Failed to verify verification code")
        raise typer.Exit(1)

    if not api.is_trusted_session:
        typer.echo("Session is not trusted. Requesting trust...")
        result = api.trust_session()
        typer.echo(f"Session trust result: {result}")


def _handle_2sa(api):
    """Handle two-step authentication if needed."""
    typer.echo("Two-step authentication required. Your trusted devices are:")
    devices = api.trusted_devices
    for i, device in enumerate(devices):
        device_name = device.get("deviceName", f"SMS to {device.get('phoneNumber')}")
        typer.echo(f"  {i}: {device_name}")

    device_index = typer.prompt("Which device would you like to use?", type=int)
    device = devices[device_index]

    if not api.send_verification_code(device):
        typer.echo("Failed to send verification code")
        raise typer.Exit(1)

    code = typer.prompt("Please enter validation code")
    if not api.validate_verification_code(device, code):
        typer.echo("Failed to verify verification code")
        raise typer.Exit(1)


def _save_credentials(username, password):
    """Save user credentials."""
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump({"username": username}, f)

    if password and typer.confirm("Save password in keyring?", default=False):
        store_password_in_keyring(username, password)


def get_api_instance(username: Optional[str] = None, password: Optional[str] = None):
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

    if not password:
        # Try to get from keyring
        password = get_password_from_keyring(username)
        if not password:
            password = typer.prompt("iCloud password", hide_input=True)

    # Create API instance
    try:
        api = PyiCloudService(username, password)
    except PyiCloudFailedLoginException as exc:
        typer.echo("Invalid username or password")
        raise typer.Exit(1) from exc

    # Handle authentication challenges
    if api.requires_2fa:
        _handle_2fa(api)
    elif api.requires_2sa:
        _handle_2sa(api)

    # Save credentials
    _save_credentials(username, password)

    return api


@app.command("login")
def login(username: Optional[str] = None, password: Optional[str] = None):
    """Login to iCloud."""
    api = get_api_instance(username, password)
    typer.echo(f"Successfully logged in as {api.account_name}")


@app.command("logout")
def logout():
    """Remove saved credentials."""
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            username = json.load(f).get("username")
        if username:
            delete_password_in_keyring(username)
        os.remove(session_path)
        typer.echo("Logged out successfully")
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
    ):
        typer.echo("No session found")
