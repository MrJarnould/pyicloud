def _authenticate(
    username: str,
    password: Optional[str],
    china_mainland: bool,
    parser: argparse.ArgumentParser,
    command_line: argparse.Namespace,
    failures: int = 0,
) -> Optional[PyiCloudService]:
    api = None
    try:
        api = PyiCloudService(username, password, china_mainland=china_mainland)
        if (
            not utils.password_exists_in_keyring(username)
            and command_line.interactive
            and confirm("Save password in keyring?")
            and password
        ):
            utils.store_password_in_keyring(username, password)

        if api.requires_2fa:
            _handle_2fa(api)

        elif api.requires_2sa:
            _handle_2sa(api)
        return api
    except PyiCloudFailedLoginException as err:
        # If they have a stored password; we just used it and
        # it did not work; let's delete it if there is one.
        if not password:
            parser.error("No password supplied")

        if utils.password_exists_in_keyring(username):
            utils.delete_password_in_keyring(username)

        message: str = f"Bad username or password for {username}"

        failures += 1
        if failures >= 3:
            raise RuntimeError(message) from err

        print(message, file=sys.stderr)