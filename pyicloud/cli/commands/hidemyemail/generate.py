"""Generate command for the HideMyEmail service."""

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Generate a new email alias")
console = Console()


@app.callback(invoke_without_command=True)
def main():
    """Generate a new email alias."""
    api = auth.get_api_instance()

    try:
        new_email = api.hidemyemail.generate()
        console.print(f"Generated new email: [bold]{new_email}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)
