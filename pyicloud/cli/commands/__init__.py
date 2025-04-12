"""Command modules for the PyiCloud CLI."""

# Import all command modules here for easy access
# This makes them available for import from pyicloud.cli.commands
from pyicloud.cli.commands import auth, hidemyemail

# Explicitly define what's exported
__all__ = ["auth", "hidemyemail"]
