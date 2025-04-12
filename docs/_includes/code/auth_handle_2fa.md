def _handle_2fa(api):
    """Handle two-factor authentication if needed."""
    console.print("\nTwo-factor authentication required.")
    code = typer.prompt("Enter the verification code")
    result = api.validate_2fa_code(code)
    if not result:
        console.print("[bold red]Failed to verify verification code[/bold red]")
        raise typer.Exit(1)

    if not api.is_trusted_session:
        console.print("Session is not trusted. Requesting trust...")
        result = api.trust_session()
        console.print(f"Session trust result: {result}")