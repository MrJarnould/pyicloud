"""Authentication commands for the PyiCloud CLI."""

import typer

from . import login, logout, status

app = typer.Typer(help="Authentication commands")
app.add_typer(login.app, name="login")
app.add_typer(logout.app, name="logout")
app.add_typer(status.app, name="status")
