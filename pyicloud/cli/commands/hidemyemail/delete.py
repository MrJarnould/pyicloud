"""Delete command for the HideMyEmail service."""

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Delete an email alias")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    alias_id: str = typer.Argument(..., help="ID of the email alias to delete"),
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

    api = auth.get_api_instance()

    try:
        api.hidemyemail.delete(alias_id)
        console.print(f"Deleted alias [bold]{alias_id}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)
