"""List command for the HideMyEmail service."""

import typer
from rich.console import Console
from rich.table import Table

from pyicloud.cli.utils import auth

app = typer.Typer(help="List email aliases")
console = Console()


@app.callback(invoke_without_command=True)
def main():
    """List all email aliases."""
    api = auth.get_api_instance()

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
