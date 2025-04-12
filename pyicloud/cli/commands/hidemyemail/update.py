"""Update command for the HideMyEmail service."""

from typing import Optional

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Update email alias metadata")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    alias_id: str = typer.Argument(..., help="ID of the email alias"),
    label: Optional[str] = typer.Option(None, help="New label for the alias"),
    note: Optional[str] = typer.Option(None, help="New note for the alias"),
):
    """Update an email alias metadata."""
    api = auth.get_api_instance()

    try:
        if not label and not note:
            console.print("[yellow]Warning:[/yellow] No updates specified")
            return

        # Get current values if only updating one field
        if not label or not note:
            details = api.hidemyemail[alias_id]
            if not label:
                label = details.get("label", "")
            if not note:
                note = details.get("note", "")

        api.hidemyemail.update_metadata(alias_id, label, note)
        console.print(f"Updated alias [bold]{alias_id}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)
