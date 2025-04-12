def get_api_instance(
    username: Optional[str] = None,
    password: Optional[str] = None,
    china_mainland: bool = False,
    max_retries: int = 3,
):
    """Get authenticated PyiCloudService instance."""
    # Try to load from session file first
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            saved_username = json.load(f).get("username")
            username = username or saved_username
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if not username:
        username = typer.prompt("iCloud username (email)")

    # Retry mechanism
    failure_count = 0
    while failure_count < max_retries:
        if not password:
            # Try to get from keyring
            password = get_password_from_keyring(username)
            if not password:
                password = typer.prompt("iCloud password", hide_input=True)

        # Create API instance
        try:
            api = PyiCloudService(username, password, china_mainland=china_mainland)

            # Handle authentication challenges
            if api.requires_2fa:
                _handle_2fa(api)
            elif api.requires_2sa:
                _handle_2sa(api)

            # Save credentials if successful
            _save_credentials(username, password)

            return api

        except PyiCloudFailedLoginException as exc:
            failure_count += 1
            # If stored password didn't work, delete it
            if password_exists_in_keyring(username):
                delete_password_in_keyring(username)

            password = None  # Reset password to force re-prompting

            if failure_count >= max_retries:
                console.print(
                    f"[bold red]Error:[/bold red] Invalid username or password for {username}"
                )
                raise typer.Exit(1) from exc
            else:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] Login failed. Attempts remaining: {max_retries - failure_count}"
                )

        except PyiCloudServiceNotActivatedException as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            console.print(
                "Please log in to https://icloud.com/ to set up your iCloud account"
            )
            raise typer.Exit(1) from exc

        except PyiCloudAPIResponseException as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(1) from exc

    # Should never reach here due to max_retries check
    console.print("[bold red]Error:[/bold red] Failed to authenticate")
    raise typer.Exit(1)