"""Logout command for the PyiCloud CLI."""

import json
import os

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Logout from iCloud")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    remove_all: bool = typer.Option(
        False, help="Remove all sessions and configuration files"
    ),
):
    """Remove saved credentials."""
    try:
        # Extract username from session file
        username = None
        if os.path.exists(auth.session_path):
            try:
                with open(auth.session_path, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
                    username = session_data.get("username")
            except (json.JSONDecodeError, KeyError):
                pass

            # Remove the session file
            os.remove(auth.session_path)

        # Remove user-specific files
        auth.remove_session_files(username)

        # Remove config file if requested
        if remove_all and os.path.exists(auth.config_path):
            os.remove(auth.config_path)
            console.print("Removed all configuration files")

        console.print("[green]Logged out successfully[/green]")
    except OSError as exc:
        console.print(
            f"[bold red]Error:[/bold red] Could not completely remove session data: {exc}"
        )
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] {exc}")
        console.print("No active session found or already logged out")
