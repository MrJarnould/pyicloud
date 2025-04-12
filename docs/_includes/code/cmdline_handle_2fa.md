def _handle_2fa(api: PyiCloudService) -> None:
    print("\nTwo-step authentication required.", "\nPlease enter validation code")

    code: str = input("(string) --> ")
    if not api.validate_2fa_code(code):
        print("Failed to verify verification code")
        sys.exit(1)

    print("")