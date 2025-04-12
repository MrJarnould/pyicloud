"""Status command for the PyiCloud CLI."""

import json
import os

import typer
from rich.console import Console

from pyicloud import PyiCloudService
from pyicloud.cli.utils import auth

app = typer.Typer(help="Check authentication status")
console = Console()


@app.callback(invoke_without_command=True)
def main():
    """Check authentication status."""
    try:
        if not os.path.exists(auth.session_path):
            console.print("[yellow]Not logged in[/yellow]")
            return

        with open(auth.session_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
            username = session_data.get("username")

        if not username:
            console.print("[yellow]Session exists but no username found[/yellow]")
            return

        # Check if we can access the API without password (using session tokens)
        try:
            api = PyiCloudService(username)
            if (
                api.data
                and api.data.get("dsInfo")
                and api.data.get("dsInfo").get("dsid")
            ):
                console.print(
                    f"[green]Logged in as:[/green] [bold]{api.account_name}[/bold]"
                )
            else:
                console.print(
                    "[yellow]Session exists but requires re-authentication[/yellow]"
                )
        except Exception:
            console.print("[yellow]Session exists but authentication failed[/yellow]")
            console.print("Please log in again")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Could not check status: {exc}")
