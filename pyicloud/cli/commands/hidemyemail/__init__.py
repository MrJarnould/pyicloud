"""HideMyEmail service commands for the PyiCloud CLI."""

import typer

from . import delete, details, generate, list_aliases, reserve, update

app = typer.Typer(help="HideMyEmail service commands")
app.add_typer(list_aliases.app, name="list")
app.add_typer(generate.app, name="generate")
app.add_typer(reserve.app, name="reserve")
app.add_typer(details.app, name="details")
app.add_typer(update.app, name="update")
app.add_typer(delete.app, name="delete")
