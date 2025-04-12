"""Authentication module for the PyiCloud CLI."""

import json
import os
from pathlib import Path
from typing import Optional

import keyring
import typer
from rich.console import Console

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException

app = typer.Typer(help="Authentication commands")
console = Console()

# State storage
config_dir = os.path.expanduser("~/.config/pyicloud")
Path(config_dir).mkdir(parents=True, exist_ok=True)
session_path = os.path.join(config_dir, "session.json")


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
        password = keyring.get_password("pyicloud", username)
        if not password:
            password = typer.prompt("iCloud password", hide_input=True)

    # Create API instance
    try:
        api = PyiCloudService(username, password)
    except PyiCloudFailedLoginException:
        typer.echo("Invalid username or password")
        raise typer.Exit(1)

    # Handle 2FA if needed
    if api.requires_2fa:
        code = typer.prompt("Enter the verification code")
        result = api.validate_2fa_code(code)
        if not result:
            typer.echo("Failed to verify verification code")
            raise typer.Exit(1)

        if not api.is_trusted_session:
            typer.echo("Session is not trusted. Requesting trust...")
            result = api.trust_session()
            typer.echo(f"Session trust result: {result}")

    # Handle 2SA if needed
    elif api.requires_2sa:
        typer.echo("Two-step authentication required. Your trusted devices are:")
        devices = api.trusted_devices
        for i, device in enumerate(devices):
            device_name = device.get(
                "deviceName", f"SMS to {device.get('phoneNumber')}"
            )
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

    # Save username for future use
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump({"username": username}, f)

    # Ask to save password
    if password and typer.confirm("Save password in keyring?", default=False):
        keyring.set_password("pyicloud", username, password)

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
            keyring.delete_password("pyicloud", username)
        os.remove(session_path)
        typer.echo("Logged out successfully")
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        keyring.errors.PasswordDeleteError,
    ):
        typer.echo("No session found")
