#!/usr/bin/env python
"""Modern CLI for pyicloud."""

import typer
from rich.console import Console

from pyicloud.cli.commands import auth, hidemyemail

app = typer.Typer(help="Modern Command Line Interface for PyiCloud")
console = Console()

# Add command groups
app.add_typer(auth.app, name="auth")
app.add_typer(hidemyemail.app, name="hidemyemail")


@app.callback()
def callback():
    """Modern CLI for interacting with Apple iCloud services."""
    pass


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
