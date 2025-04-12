"""Reserve command for the HideMyEmail service."""

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Reserve an email alias")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    email: str = typer.Argument(..., help="Email address to reserve"),
    label: str = typer.Argument(..., help="Label for the email alias"),
):
    """Reserve an email alias with a custom label."""
    api = auth.get_api_instance()

    try:
        result = api.hidemyemail.reserve(email, label)
        anonymous_id = result.get("anonymousId", "Unknown")
        console.print(
            f"Reserved email [bold]{email}[/bold] with ID: [bold]{anonymous_id}[/bold]"
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(1)
