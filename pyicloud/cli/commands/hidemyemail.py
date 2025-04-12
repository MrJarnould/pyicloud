"""HideMyEmail service commands for the PyiCloud CLI."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .auth import get_api_instance

app = typer.Typer(help="HideMyEmail service commands")
console = Console()


@app.command("list")
def list_aliases():
    """List all email aliases."""
    api = get_api_instance()

    try:
        aliases = list(api.hidemyemail)

        if not aliases:
            console.print("No aliases found")
            return

        table = Table("Email Address", "Label", "ID")

        for alias in aliases:
            table.add_row(
                alias.get("hme", ""),
                alias.get("label", ""),
                alias.get("anonymousId", ""),
            )

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)


@app.command("generate")
def generate_alias():
    """Generate a new email alias."""
    api = get_api_instance()

    try:
        new_email = api.hidemyemail.generate()
        console.print(f"Generated new email: [bold]{new_email}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)


@app.command("reserve")
def reserve_alias(email: str, label: str):
    """Reserve an email alias with a custom label."""
    api = get_api_instance()

    try:
        result = api.hidemyemail.reserve(email, label)
        anonymous_id = result.get("anonymousId", "Unknown")
        console.print(
            f"Reserved email [bold]{email}[/bold] with ID: [bold]{anonymous_id}[/bold]"
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)


@app.command("details")
def get_alias_details(alias_id: str):
    """Get details about a specific alias."""
    api = get_api_instance()

    try:
        details = api.hidemyemail[alias_id]

        console.print("[bold]Alias Details:[/bold]")
        console.print(f"Email: [bold]{details.get('hme', '')}[/bold]")
        console.print(f"Label: {details.get('label', '')}")
        console.print(f"Note: {details.get('note', '')}")
        console.print(f"Created: {details.get('timeCreated', '')}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)


@app.command("update")
def update_alias(
    alias_id: str,
    label: Optional[str] = None,
    note: Optional[str] = None,
):
    """Update an email alias metadata."""
    api = get_api_instance()

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


@app.command("delete")
def delete_alias(
    alias_id: str,
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete without confirmation"
    ),
):
    """Delete an email alias."""
    if not force:
        confirmed = typer.confirm(f"Are you sure you want to delete alias {alias_id}?")
        if not confirmed:
            console.print("Deletion cancelled")
            return

    api = get_api_instance()

    try:
        api.hidemyemail.delete(alias_id)
        console.print(f"Deleted alias [bold]{alias_id}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)
