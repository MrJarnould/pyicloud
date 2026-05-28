"""Lazy access to optional dependencies.

`cryptography` and `fido2` are only required for security-key (FIDO2/WebAuthn)
authentication and Apple's HSA2 trusted-device bridge flow. They are gated
behind the ``security-key`` extra so that the base package remains installable
in environments where compiled wheels are unavailable (for example, a-Shell on
iOS, where building ``cryptography`` from source requires Rust).

The helpers in this module import those packages on demand and raise a clear,
actionable error when they are missing.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Optional

_INSTALL_HINT: str = 'Install with: pip install "pyicloud[security-key]"'


def security_key_extra_missing_error(feature: str) -> RuntimeError:
    """Return a RuntimeError describing how to enable the security-key extra."""

    return RuntimeError(
        f"{feature} requires the optional 'security-key' extra "
        f"(packages: cryptography, fido2). {_INSTALL_HINT}"
    )


def _try_import(name: str) -> Optional[ModuleType]:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def cryptography_available() -> bool:
    """Return True when the ``cryptography`` package is importable."""

    return _try_import("cryptography") is not None


def fido2_available() -> bool:
    """Return True when the ``fido2`` package is importable."""

    return _try_import("fido2") is not None


def require_cryptography(feature: str) -> None:
    """Raise RuntimeError with install instructions if cryptography is missing."""

    if not cryptography_available():
        raise security_key_extra_missing_error(feature)


def require_fido2(feature: str) -> None:
    """Raise RuntimeError with install instructions if fido2 is missing."""

    if not fido2_available():
        raise security_key_extra_missing_error(feature)
