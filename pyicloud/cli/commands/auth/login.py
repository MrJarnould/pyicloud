"""Login command for the PyiCloud CLI."""

from typing import Optional

import typer
from rich.console import Console

from pyicloud.cli.utils import auth

app = typer.Typer(help="Login to iCloud")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    username: Optional[str] = typer.Option(None, help="Apple ID (email)"),
    password: Optional[str] = typer.Option(None, help="iCloud password"),
    china_mainland: Optional[bool] = typer.Option(
        None, help="Set if your Apple ID is based in China mainland"
    ),
    save_config: bool = typer.Option(
        False, help="Save username and region settings to config file"
    ),
):
    """Login to iCloud."""
    api = auth.get_api_instance(username, password, china_mainland)

    # Save to config if requested
    if save_config and username:
        config = auth.load_config()
        config["username"] = username
        if china_mainland is not None:
            config["china_mainland"] = china_mainland
        auth.save_config(config)

    console.print(f"Successfully logged in as [bold]{api.account_name}[/bold]")
