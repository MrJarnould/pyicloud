"""Details command for the HideMyEmail service."""

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Get alias details")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    alias_id: str = typer.Argument(..., help="ID of the email alias"),
):
    """Get details about a specific alias."""
    api = auth.get_api_instance()

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
