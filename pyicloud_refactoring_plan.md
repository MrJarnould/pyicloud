# PyiCloud Refactoring Plan: Improving Authentication with SOLID Principles

## Project Overview

PyiCloud is a Python library that provides access to Apple's iCloud services. It allows users to authenticate with their Apple ID and interact with iCloud data including photos, contacts, calendars, device locations, and more. The library handles complex authentication flows including two-factor authentication (2FA), secure remote password (SRP) authentication, and token management.

The project is currently undergoing active maintenance as a fork of the original (now abandoned) PyPi repository, with plans for a major version update from 1.x to 2.x. This refactoring plan focuses specifically on improving the authentication implementation.

## Current Architecture

The current codebase has the following structure:

- `PyiCloudService` (in base.py, 703 lines): The main entry point that handles:
  - Authentication with Apple's servers
  - Two-factor authentication flows
  - Service discovery and instantiation
  - Password and token management

- `PyiCloudSession` (in session.py, 351 lines): A custom session object that:
  - Extends requests.Session
  - Handles cookie persistence
  - Manages session state
  - Translates HTTP errors to custom exceptions

This structure has led to large, monolithic classes with multiple responsibilities, making the code harder to maintain, test, and extend.

## Current Authentication Implementation

The authentication system in PyiCloud is distributed across several files with components working together to provide a complete authentication flow. Let's examine the current implementation in detail:

### Core Authentication Components

#### 1. `base.py` - Primary Authentication Logic

The `PyiCloudService` class in `base.py` contains the core authentication implementation:

```python
# Authentication orchestration
def authenticate(self, force_refresh=False, service=None)
def _authenticate(self)
def _setup_endpoints(self)

# SRP authentication
def _srp_authentication(self, headers)
class SrpPassword  # Nested helper class for password handling

# Token-based authentication
def _authenticate_with_token(self)
def _authenticate_with_credentials_service(self, service)
def _validate_token(self)
def _get_auth_headers(self, overrides=None)

# Two-factor authentication
@property
def requires_2fa(self)
@property
def requires_2sa(self)
@property
def is_trusted_session(self)
@property
def trusted_devices(self)
def send_verification_code(self, device)
def validate_verification_code(self, device, code)
def validate_2fa_code(self, code)
def trust_session(self)
```

This class orchestrates the entire authentication flow:
- It tries token reuse first
- Falls back to SRP authentication
- Handles 2FA/2SA requirements
- Manages session trust

#### 2. `session.py` - HTTP Layer and Session Persistence

The `PyiCloudSession` class extends `requests.Session` to provide:

```python
# Session state management
def _load_session_data(self)
def _save_session_data(self)
def _update_session_data(self, response)

# HTTP request handling
def request(self, method, url, ...)
def _request(self, method, url, ...)
def _handle_request_error(self, response, method, url, ...)

# Error handling
def _decode_json_response(self, response)
def _raise_error(self, code, reason)
```

This class:
- Persists cookies and session tokens between runs
- Intercepts HTTP errors and converts them to domain-specific exceptions
- Triggers re-authentication when needed
- Stores authentication headers and state

#### 3. `exceptions.py` - Authentication-specific Exceptions

```python
PyiCloudFailedLoginException      # Username/password invalid
PyiCloud2FARequiredException      # Two-factor auth required (HSA2)
PyiCloud2SARequiredException      # Two-step auth required (HSA1)
PyiCloudAPIResponseException      # Generic API errors
PyiCloudServiceNotActivatedException  # Service not set up
PyiCloudPasswordException         # Password missing/invalid
```

#### 4. `utils.py` - Keychain Integration

```python
def get_password(username, interactive)
def get_password_from_keyring(username)
def store_password_in_keyring(username, password)
def delete_password_in_keyring(username)
def password_exists_in_keyring(username)
```

### Authentication Workflow

The complete authentication flow is integrated across these components:

1. **Initialization** (in `base.py:PyiCloudService.__init__`):
   ```python
   # Set up endpoints based on region
   self._setup_endpoints()

   # Try getting password from keyring if not provided
   if self._password is None:
       self._password = get_password_from_keyring(apple_id)

   # Set up cookie directory with secure permissions
   _cookie_directory = self._setup_cookie_directory(cookie_directory)

   # Create session with cookie persistence
   self.session = PyiCloudSession(...)

   # Start authentication
   self.authenticate()
   ```

2. **Authentication Attempt** (in `base.py:authenticate`):
   ```python
   # Try token reuse first
   if self.session.data.get("session_token") and not force_refresh:
       try:
           self.data = self._validate_token()
           login_successful = True
       except PyiCloudAPIResponseException:
           # Token invalid, continue to full auth

   # Try service-specific authentication if applicable
   if not login_successful and service is not None:
       try:
           self._authenticate_with_credentials_service(service)
       except Exception:
           # Service auth failed, continue to full auth

   # Full authentication if other methods failed
   if not login_successful:
       self._authenticate()
   ```

3. **SRP Authentication** (in `base.py:_srp_authentication`):
   ```python
   # Create SRP user with secure parameters
   usr = srp.User(
       self.account_name,
       srp_password,
       hash_alg=srp.SHA256,
       ng_type=srp.NG_2048,
   )

   # Stage 1: Initial challenge
   uname, A = usr.start_authentication()
   response = self.session.post(f"{self.auth_endpoint}/signin/init", ...)

   # Stage 2: Complete authentication with proof
   m1 = usr.process_challenge(salt, b)
   m2 = usr.H_AMK
   self.session.post(f"{self.auth_endpoint}/signin/complete", ...)
   ```

4. **Token Exchange** (in `base.py:_authenticate_with_token`):
   ```python
   data = {
       "accountCountryCode": self.session.data.get("account_country"),
       "dsWebAuthToken": self.session.data.get("session_token"),
       "extended_login": True,
       "trustToken": self.session.data.get("trust_token", ""),
   }

   resp = self.session.post(f"{self.setup_endpoint}/accountLogin", ...)
   self.data = resp.json()
   ```

5. **HTTP Request Processing** (in `session.py:_request`):
   ```python
   # Make the request
   response = super().request(method=method, url=url, data=data, **kwargs)

   # Update and save session data after each request
   self._update_session_data(response)
   self._save_session_data()

   # Handle authentication errors
   if not response.ok:
       return self._handle_request_error(...)
   ```

6. **Session Data Persistence** (in `session.py:_save_session_data`):
   ```python
   # Save session data to JSON file
   with open(self.session_path, "w", encoding="utf-8") as outfile:
       dump(self._data, outfile)

   # Save cookies to LWP-format cookie jar
   self.cookies.save(ignore_discard=True, ignore_expires=True)
   ```

### Integration Points with Services

The authentication system integrates with service access through:

1. **Service URL Resolution**:
   ```python
   def get_webservice_url(self, ws_key):
       # Authentication must succeed first to populate self._webservices
       if self._webservices is None or self._webservices.get(ws_key) is None:
           raise PyiCloudServiceNotActivatedException
       return self._webservices[ws_key]["url"]
   ```

2. **Lazy Service Initialization**:
   ```python
   @property
   def devices(self):
       if not self._devices:
           service_root = self.get_webservice_url("findme")
           self._devices = FindMyiPhoneServiceManager(...)
       return self._devices
   ```

3. **Re-authentication Triggers**:
   The session detects authentication failures and can trigger re-authentication:
   ```python
   # In session.py
   def _handle_request_error(self, ...):
       if not has_retried and response.status_code in [421, 450, 500]:
           self._reauthenticate_find_my_iphone(response)
           return self._request(...)  # Retry with fresh authentication
   ```

### Security Features

The authentication system implements these security measures:

1. **SRP Protocol**: Zero-knowledge password proof via the SRP protocol
2. **Password Filtering**: Hides passwords in logs via `PyiCloudPasswordFilter`
3. **Secure Storage**: Stores cookies in directories with 0700 permissions
4. **Keyring Integration**: Can use system keyring for password storage
5. **Token Rotation**: Handles Apple's token expiration gracefully

### Current Implementation Issues

While the current implementation works, it has several issues:

1. **Code Organization**: Authentication logic is scattered across multiple files with no clear boundaries
2. **Tight Coupling**: PyiCloudService directly implements authentication rather than delegating to specialized components
3. **Mixed Responsibilities**: The same class handles authentication, service management, and session handling
4. **Limited Extensibility**: Adding new authentication methods requires modifying existing code
5. **Testing Challenges**: The monolithic design makes unit testing difficult
6. **Error Handling**: Exception handling is distributed, making error flows difficult to follow
7. **Session Management**: The session class extends requests.Session in ways that could violate LSP

## Background: SOLID Principles

This refactoring plan is guided by SOLID principles, which are five design principles for creating more maintainable software:

1. **Single Responsibility**: Each class should do only one thing
2. **Open-Closed**: Code should be open for extension but closed for modification
3. **Liskov Substitution**: Subtypes should be replaceable for their parent types
4. **Interface Segregation**: Prefer many specific interfaces over one general one
5. **Dependency Inversion**: Depend on abstractions, not concrete implementations

We're taking a pragmatic "SOLID light" approach that focuses on gradual, incremental improvements rather than a complete rewrite.

## Success Criteria

### 1. Code Structure and Organization

- **File Structure**:
  - Create a new file `pyicloud/authentication.py` to house authentication logic
  - Reduce `base.py` from 703 lines to under 500 lines (>200 line reduction)
  - Ensure `authentication.py` is under 400 lines
  - No new files should exceed 400 lines

- **Class Structure**:
  - Create a new `ICloudAuthentication` class with clearly defined responsibilities
  - Ensure all authentication-related methods are moved from `PyiCloudService` to this class
  - Maintain backward compatibility by delegating calls from `PyiCloudService`

- **Method Organization**:
  - Group related methods together (SRP, token, 2FA methods)
  - Ensure related functionality is co-located in the codebase
  - Public methods should be clearly distinguished from private implementation

- **Class Coupling**:
  - `PyiCloudService` should only depend on the public interface of `ICloudAuthentication`
  - `ICloudAuthentication` should not directly depend on `PyiCloudService` internals
  - Session management interaction should be well-defined and minimal

- **Naming and Documentation**:
  - All new methods and classes should have clear, descriptive names
  - All public methods should have docstrings explaining their purpose
  - Comments should explain complex authentication flows

### 2. Test Coverage and Quality

- **Test Preservation**:
  - All 18 existing authentication tests in `tests/test_base.py` must pass after refactoring
  - No regression in test coverage metrics
  - Existing fixtures in `conftest.py` should continue to work

- **New Tests**:
  - Add at least 5 new tests specifically for the `ICloudAuthentication` class
  - Tests should cover normal authentication flow, error cases, and 2FA scenarios
  - Tests should use pytest fixtures consistent with the existing pattern
  - Mock objects should be used to avoid actual network requests

- **Test Independence**:
  - Tests should not depend on external state (e.g. real Apple services)
  - Test authentication logic isolated from service management

### 3. Functionality Preservation

- **Authentication Flow**:
  - Token reuse, SRP authentication, and 2FA flows must work exactly as before
  - Error handling must maintain the same behavior
  - Security features like password filtering must be preserved

- **API Compatibility**:
  - All public authentication methods must remain available on `PyiCloudService`
  - No changes to method signatures of public methods
  - Command-line tool must continue to work without modification
  - Example scripts must run without changes

### 4. Performance

- **Overhead**:
  - No measurable performance degradation in authentication time
  - No significant increase in memory usage
  - Delegation overhead should be negligible

- **Resource Usage**:
  - Cookie and session storage efficiency should be maintained
  - No additional network requests compared to original implementation

### 5. Extensibility

- **New Authentication Methods**:
  - Structure should allow adding new authentication strategies without modifying existing code
  - 2FA handling should be extensible for future Apple authentication changes
  - Token management should be adaptable to different storage mechanisms

## Implementation Plan

### Phase 1: Single Responsibility - Extract Authentication Logic

**Current Status: Planning**

#### 1.1 Setup and Preparation

1. **Create new authentication module file**:
   - Create file: `/workspaces/pyicloud/pyicloud/authentication.py`
   - Add header docstring: "Authentication module for PyiCloud"
   - Add standard license header to match project convention

2. **Set up necessary imports in authentication.py**:
   ```python
   """Authentication module for PyiCloud."""

   import base64
   import hashlib
   import json
   import logging
   from typing import Any, Optional, Union

   import srp
   from requests.models import Response

   from pyicloud.const import ACCOUNT_NAME, CONTENT_TYPE_JSON
   from pyicloud.exceptions import (
       PyiCloud2FARequiredException,
       PyiCloudAPIResponseException,
       PyiCloudFailedLoginException,
       PyiCloudPasswordException,
       PyiCloudServiceNotActivatedException,
   )
   from pyicloud.session import PyiCloudSession

   LOGGER: logging.Logger = logging.getLogger(__name__)
   ```

3. **Create basic ICloudAuthentication class structure**:
   ```python
   class ICloudAuthentication:
       """
       Handles authentication with iCloud services.

       This class is responsible for:
       - SRP authentication with Apple ID
       - Token-based authentication
       - Two-factor authentication flows
       - Password management
       """

       def __init__(
           self,
           apple_id: str,
           password: Optional[str],
           session: PyiCloudSession,
           client_id: str,
           is_china_mainland: bool = False,
       ) -> None:
           """
           Initialize the authentication handler.

           Args:
               apple_id: Apple ID (email address) to authenticate with
               password: Password for the Apple ID (None to use keyring)
               session: PyiCloudSession for making HTTP requests
               client_id: Unique client identifier
               is_china_mainland: Whether to use China-specific endpoints
           """
           self.apple_id = apple_id
           self._password = password
           self.session = session
           self.client_id = client_id
           self.is_china_mainland = is_china_mainland
           self.data: dict[str, Any] = {}
           self._password_filter = None

           # Set up authentication endpoints
           self._setup_endpoints()

       def _setup_endpoints(self) -> None:
           """Set up the authentication endpoints."""
           # Implementation will be moved from PyiCloudService

       # Placeholder for other methods that will be implemented
   ```

4. **Set up test scaffolding**:
   - Create or modify fixtures in tests/conftest.py to support testing ICloudAuthentication
   - Create file: `/workspaces/pyicloud/tests/test_authentication.py` with basic structure:
   ```python
   """Test the ICloudAuthentication class."""

   from unittest.mock import MagicMock, patch

   import pytest

   from pyicloud.authentication import ICloudAuthentication
   from pyicloud.exceptions import PyiCloudFailedLoginException


   @pytest.fixture
   def auth_instance():
       """Create a test instance of ICloudAuthentication."""
       session = MagicMock()
       return ICloudAuthentication(
           apple_id="test@example.com",
           password="test_password",
           session=session,
           client_id="test_client_id",
           is_china_mainland=False,
       )


   def test_setup_endpoints(auth_instance):
       """Test the _setup_endpoints method."""
       # Verify the endpoints are set correctly
       assert auth_instance.auth_endpoint == "https://idmsa.apple.com/appleauth/auth"
       assert auth_instance.home_endpoint == "https://www.icloud.com"
       assert auth_instance.setup_endpoint == "https://setup.icloud.com/setup/ws/1"
   ```

#### 1.2 Move Authentication Classes

1. **Move SrpPassword class to authentication.py**:
   - Copy class definition from `base.py`
   - Ensure all imports are updated
   - Verify class functionality is identical:
   ```python
   class SrpPassword:
       """SRP password handler for secure authentication."""

       def __init__(self, password: str) -> None:
           """Initialize with a plaintext password."""
           self.password: str = password
           self.salt: bytes
           self.iterations: int
           self.key_length: int

       def set_encrypt_info(self, salt: bytes, iterations: int, key_length: int) -> None:
           """Set encryption parameters from server response."""
           self.salt: bytes = salt
           self.iterations: int = iterations
           self.key_length: int = key_length

       def encode(self) -> bytes:
           """
           Encode password for SRP authentication.

           First hashes the password with SHA-256, then applies PBKDF2
           with the server-provided parameters.
           """
           password_hash: bytes = hashlib.sha256(self.password.encode("utf-8")).digest()
           return hashlib.pbkdf2_hmac(
               "sha256",
               password_hash,
               self.salt,
               self.iterations,
               self.key_length,
           )
   ```

2. **Move PyiCloudPasswordFilter class to authentication.py**:
   - Copy class definition from `base.py`
   - Update imports
   - Verify logging functionality works correctly:
   ```python
   class PyiCloudPasswordFilter(logging.Filter):
       """
       Log filter that hides password information.

       Replaces instances of the password with asterisks in log messages.
       """

       def __init__(self, password: str) -> None:
           """Initialize with the password to hide."""
           super().__init__(password)

       def filter(self, record) -> bool:
           """Filter log records to hide the password."""
           message: str = record.getMessage()
           if self.name in message:
               record.msg = message.replace(self.name, "*" * 8)
               record.args = ()

           return True
   ```

3. **Update imports in base.py**:
   ```python
   from pyicloud.authentication import ICloudAuthentication, PyiCloudPasswordFilter, SrpPassword
   ```

4. **Write tests for moved classes**:
   - Add tests for SrpPassword in test_authentication.py
   - Add tests for PyiCloudPasswordFilter in test_authentication.py
   - Run tests to verify functionality: `python -m pytest tests/test_authentication.py -v`

#### 1.3 Create ICloudAuthentication Class Methods

1. **Implement constructor and setup methods**:
   - Move `_setup_endpoints()` from PyiCloudService
   - Add necessary instance variables
   - Add password handling functionality

2. **Add password property**:
   ```python
   @property
   def password(self) -> str:
       """
       Get the password, setting up password filtering for logs.

       Raises:
           PyiCloudPasswordException: If no password is available
       """
       if self._password is None:
           raise PyiCloudPasswordException()

       if self._password_filter is None:
           self._password_filter = PyiCloudPasswordFilter(self._password)
           LOGGER.addFilter(self._password_filter)

       return self._password
   ```

3. **Test basic functionality**:
   - Test constructor with different parameters
   - Test password property behavior
   - Test endpoint setup for different regions

#### 1.4 Move Core Authentication Methods

For each method, follow this process:
1. Copy method implementation from `base.py` to `authentication.py`
2. Update method to work within ICloudAuthentication class context
3. Add tests for the method
4. Verify the method works correctly
5. Update PyiCloudService to delegate to the ICloudAuthentication method

Move methods in this specific order:

1. **Move _get_auth_headers**:
   ```python
   def _get_auth_headers(
       self, overrides: Optional[dict[str, Any]] = None
   ) -> dict[str, Any]:
       """Get authentication headers for requests."""
       # Implementation from PyiCloudService
   ```

2. **Move _validate_token**:
   ```python
   def _validate_token(self) -> Any:
       """
       Check if the current session token is still valid.

       Returns:
           dict: The validation response data

       Raises:
           PyiCloudAPIResponseException: If validation fails
       """
       # Implementation from PyiCloudService
   ```

3. **Move _authenticate_with_token**:
   ```python
   def _authenticate_with_token(self) -> None:
       """
       Authenticate using existing session token.

       Raises:
           PyiCloudFailedLoginException: If no token is available or authentication fails
           PyiCloud2FARequiredException: If 2FA is required despite token
       """
       # Implementation from PyiCloudService
   ```

4. **Move _authenticate_with_credentials_service**:
   ```python
   def _authenticate_with_credentials_service(self, service: Optional[str]) -> None:
       """
       Authenticate to a specific service using credentials.

       Args:
           service: The service to authenticate to

       Raises:
           PyiCloudFailedLoginException: If authentication fails
       """
       # Implementation from PyiCloudService
   ```

5. **Move _srp_authentication**:
   ```python
   def _srp_authentication(self, headers: dict[str, Any]) -> None:
       """
       Perform SRP authentication.

       Args:
           headers: Headers to include in the authentication request

       Raises:
           PyiCloudFailedLoginException: If authentication fails
           PyiCloud2FARequiredException: If 2FA is required
       """
       # Implementation from PyiCloudService
   ```

6. **Move _authenticate**:
   ```python
   def _authenticate(self) -> None:
       """
       Perform full authentication flow.

       This method tries token authentication first, then falls back to SRP.

       Raises:
           PyiCloudFailedLoginException: If authentication fails
           PyiCloud2FARequiredException: If 2FA is required
       """
       # Implementation from PyiCloudService
   ```

7. **Move authenticate**:
   ```python
   def authenticate(self, force_refresh: bool = False, service: Optional[str] = None) -> None:
       """
       Authenticate with iCloud services.

       This method handles all authentication flows, including token reuse,
       service-specific authentication, and full SRP authentication.

       Args:
           force_refresh: Whether to force a fresh authentication
           service: Specific service to authenticate for
       """
       # Implementation from PyiCloudService
   ```

After moving each method:
1. Run the specific test for that method: `python -m pytest tests/test_authentication.py::test_METHOD_NAME -v`
2. Ensure the test passes before moving to the next method

#### 1.5 Move Two-Factor Authentication Methods

Move the 2FA-related properties and methods in this order:

1. **Move is_trusted_session property**:
   ```python
   @property
   def is_trusted_session(self) -> bool:
       """Returns True if the session is trusted."""
       # Implementation from PyiCloudService
   ```

2. **Move requires_2fa property**:
   ```python
   @property
   def requires_2fa(self) -> bool:
       """Returns True if two-factor authentication is required."""
       # Implementation from PyiCloudService
   ```

3. **Move requires_2sa property**:
   ```python
   @property
   def requires_2sa(self) -> bool:
       """Returns True if two-step authentication is required."""
       # Implementation from PyiCloudService
   ```

4. **Move trusted_devices property**:
   ```python
   @property
   def trusted_devices(self) -> list[dict[str, Any]]:
       """Returns devices trusted for two-step authentication."""
       # Implementation from PyiCloudService
   ```

5. **Move send_verification_code method**:
   ```python
   def send_verification_code(self, device: dict[str, Any]) -> bool:
       """
       Request a verification code sent to a trusted device.

       Args:
           device: The device to send the code to

       Returns:
           bool: True if the code was sent successfully
       """
       # Implementation from PyiCloudService
   ```

6. **Move validate_verification_code method**:
   ```python
   def validate_verification_code(self, device: dict[str, Any], code: str) -> bool:
       """
       Validate a verification code received on a trusted device.

       Args:
           device: The device the code was sent to
           code: The verification code

       Returns:
           bool: True if the code was valid
       """
       # Implementation from PyiCloudService
   ```

7. **Move validate_2fa_code method**:
   ```python
   def validate_2fa_code(self, code: str) -> bool:
       """
       Validate a 2FA code.

       Args:
           code: The 2FA code

       Returns:
           bool: True if the code was valid
       """
       # Implementation from PyiCloudService
   ```

8. **Move trust_session method**:
   ```python
   def trust_session(self) -> bool:
       """
       Request session trust to avoid future 2FA prompts.

       Returns:
           bool: True if the session was successfully trusted
       """
       # Implementation from PyiCloudService
   ```

After moving each method:
1. Add a test for the method in test_authentication.py
2. Run the specific test: `python -m pytest tests/test_authentication.py::test_METHOD_NAME -v`
3. Ensure the test passes before moving to the next method

#### 1.6 Update PyiCloudService

1. **Add ICloudAuthentication instance to PyiCloudService**:
   ```python
   def __init__(self, apple_id, password=None, cookie_directory=None, verify=True,
                client_id=None, with_family=True, china_mainland=False):
       # Existing initialization code

       # Create authentication handler
       self.auth = ICloudAuthentication(
           apple_id=apple_id,
           password=self._password,
           session=self.session,
           client_id=self._client_id,
           is_china_mainland=self._is_china_mainland
       )

       # Authenticate
       self.authenticate()
   ```

2. **Update authenticate method to delegate**:
   ```python
   def authenticate(self, force_refresh=False, service=None):
       """Authenticate using the authentication handler."""
       self.auth.authenticate(force_refresh, service)
       self.data = self.auth.data
       self._update_state()
   ```

3. **Update all authentication-related properties and methods to delegate**:
   ```python
   @property
   def requires_2fa(self):
       """Returns True if two-factor authentication is required."""
       return self.auth.requires_2fa

   @property
   def requires_2sa(self):
       """Returns True if two-step authentication is required."""
       return self.auth.requires_2sa

   @property
   def is_trusted_session(self):
       """Returns True if the session is trusted."""
       return self.auth.is_trusted_session

   @property
   def trusted_devices(self):
       """Returns devices trusted for two-step authentication."""
       return self.auth.trusted_devices

   def send_verification_code(self, device):
       """Request a verification code sent to a trusted device."""
       return self.auth.send_verification_code(device)

   def validate_verification_code(self, device, code):
       """Validate a verification code received on a trusted device."""
       return self.auth.validate_verification_code(device, code)

   def validate_2fa_code(self, code):
       """Validate a 2FA code."""
       return self.auth.validate_2fa_code(code)

   def trust_session(self):
       """Request session trust to avoid future 2FA prompts."""
       return self.auth.trust_session()

   @property
   def password(self):
       """Get the password, setting up password filtering for logs."""
       return self.auth.password

   @property
   def password_filter(self):
       """Get the password filter."""
       return self.auth._password_filter
   ```

4. **Run all tests against the updated PyiCloudService**:
   - `python -m pytest tests/test_base.py -v`
   - Fix any issues before proceeding

#### 1.7 Update PyiCloudSession

1. **Update _reauthenticate_find_my_iphone method**:
   ```python
   def _reauthenticate_find_my_iphone(self, response: Response) -> None:
       self.logger.debug("Re-authenticating Find My iPhone service")
       try:
           service: Optional[str] = None if response.status_code == 450 else "find"
           # Changed from self.service.authenticate to:
           self.service.auth.authenticate(True, service)
       except PyiCloudAPIResponseException:
           self.logger.debug("Re-authentication failed")
   ```

2. **Run tests for session**:
   - `python -m pytest tests/test_base.py::test_request_success -v`
   - `python -m pytest tests/test_base.py::test_request_failure -v`
   - Fix any issues before proceeding

3. **Test the entire authentication flow**:
   - Run all tests: `python -m pytest`
   - Fix any issues that arise

**Acceptance Criteria for Phase 1**:
- [ ] New authentication.py file created with all authentication code
- [ ] PyiCloudService delegates all authentication calls to ICloudAuthentication
- [ ] All existing tests pass
- [ ] Line count of base.py reduced by at least 200 lines
- [ ] ICloudAuthentication class has less than 400 lines
- [ ] No new bugs introduced
- [ ] Examples still work (run examples.py with test account)

**Verification Methods**:
- Count lines in files: `wc -l pyicloud/base.py pyicloud/authentication.py`
- Run all tests: `python -m pytest`
- Manually test authentication with examples.py
- Code review for clean separation of concerns

### Phase 2: Open-Closed - Separate Authentication Strategies

**Current Status: Future Work**

#### 2.1 Refactor Authentication Methods

1. Create separate methods for different authentication strategies:
   ```python
   def try_token_authentication(self):
       """Try to authenticate with existing token"""
       # Implementation from _authenticate_with_token

   def try_srp_authentication(self):
       """Try to authenticate with SRP"""
       # Implementation from _srp_authentication

   def try_service_specific_authentication(self, service):
       """Try service-specific authentication"""
       # Implementation from _authenticate_with_credentials_service
   ```

2. Refactor authenticate() method to use these strategies:
   ```python
   def authenticate(self, force_refresh=False, service=None):
       """Try authentication methods in sequence"""
       if not force_refresh and self.try_token_authentication():
           return True

       if service and self.try_service_specific_authentication(service):
           return True

       return self.try_srp_authentication()
   ```

#### 2.2 Organize 2FA Methods

1. Group 2FA methods in the code
2. Add helper methods for common 2FA operations
3. Improve documentation of 2FA workflow

**Acceptance Criteria for Phase 2**:
- Authentication strategies are clearly separated
- authenticate() method uses these strategies in a clean, readable way
- Code structure makes it easy to add new authentication methods
- All tests continue to pass
- No functionality changes from user perspective

**Verification Methods**:
- Code review to ensure clear separation
- Run tests to verify functionality
- Verify ease of adding a new authentication method

**Remaining Coupling**:
- Authentication strategies still share state within ICloudAuthentication
- This is acceptable as the strategies are closely related and benefit from shared context

**Performance Implications**:
- No significant impact expected
- Potentially improved readability may lead to better performance optimizations in the future

### Phase 3: Liskov Substitution & Dependency Inversion - Improve Session Management

**Current Status: Future Work**

#### 3.1 Create Abstract Interfaces

1. Create AbstractSessionStorage interface:
   ```python
   class AbstractSessionStorage:
       """Interface for storing session data"""

       def save(self, session_data):
           """Save session data"""
           raise NotImplementedError

       def load(self):
           """Load session data"""
           raise NotImplementedError
   ```

2. Create FileSessionStorage implementation

#### 3.2 Begin Session Class Refactoring

1. Create ICloudHttpClient that wraps requests.Session
2. Move cookie handling to this class
3. Begin transitioning functionality from PyiCloudSession

**Acceptance Criteria for Phase 3**:
- Clear interfaces for session storage
- Session management follows Liskov Substitution Principle
- No unexpected behavior changes
- All tests continue to pass

**Verification Methods**:
- Run tests with both original and new implementations
- Verify correct behavior with different storage implementations

**Remaining Coupling**:
- Some coupling between HTTP client and authentication will remain
- This represents the natural relationship between these components

**Performance Implications**:
- Potential for slightly increased overhead from abstraction
- Opportunity to optimize session storage for different environments

### Phase 4: Interface Segregation - Improve API Organization

**Current Status: Future Work**

#### 4.1 Organize Public API Methods

1. Reorganize PyiCloudService methods into logical groups
2. Create helper methods with clear names
3. Improve documentation to indicate purposes

**Acceptance Criteria for Phase 4**:
- Methods are organized in a logical, coherent way
- API is easier to understand and use
- Documentation clearly explains method purposes and relationships

**Verification Methods**:
- Review API structure for clarity
- Test typical usage patterns
- Gather feedback on API usability

**Remaining Coupling**:
- Service methods will still be exposed through a single class
- This maintains compatibility while improving organization

**Performance Implications**:
- No significant impact expected
- Improved organization may lead to better performance monitoring and optimization

## Potential Challenges and Mitigations

### Unexpected Dependencies

**Challenge**: Authentication logic may have unexpected dependencies on other parts of the system.
**Mitigation**: Start with thorough code analysis and carefully test each moved component.

### Session Management Complexity

**Challenge**: Session handling is deeply integrated with authentication.
**Mitigation**: Move authentication first, then carefully refactor session management in a later phase.

### Backward Compatibility

**Challenge**: Despite targeting a major version update, we still want to minimize unnecessary breaking changes.
**Mitigation**: Maintain method signatures where possible and clearly document any necessary API changes.

### Testing Difficulties

**Challenge**: Authentication requires mocking Apple's services.
**Mitigation**: Create robust mocks and tests before making significant changes.

## Stakeholder Impact

### Library Users

- Improved code organization will make the library easier to understand
- Future authentication enhancements will be easier to implement
- No immediate impact on existing functionality

### Contributors

- Clearer code structure will make contributions easier
- Better separation of concerns will allow parallel work on different components
- Documentation improvements will reduce onboarding time

## Implementation Timeline

While we're not setting specific time estimates, we'll follow this sequence:

1. Complete Phase 1 fully before starting Phase 2
2. Test and validate after each sub-step
3. Get code review after each major component move
4. Document progress and learnings at the end of each phase

## Conclusion

This refactoring plan provides a pragmatic approach to improving the PyiCloud authentication implementation following SOLID principles. By breaking the work into manageable phases with clear acceptance criteria, we can make steady progress toward a more maintainable, extensible codebase without the risks of a complete rewrite.

Each phase builds on the previous one, allowing us to learn and adjust our approach as we go. The end result will be a cleaner architecture that better separates concerns and makes future enhancements easier to implement.