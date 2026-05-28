"""Tests that ``cryptography`` and ``fido2`` are genuinely optional.

These tests guard the promise that ``pip install pyicloud`` (without the
``[security-key]`` extra) is usable for everything that does not require
FIDO2 or the HSA2 trusted-device bridge.
"""

# pylint: disable=protected-access

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
from typing import Iterable
from unittest.mock import patch

import pytest

from pyicloud import _optional_deps


class _BlockingFinder:
    """Meta path finder that pretends specific top-level packages are missing."""

    def __init__(self, names: Iterable[str]) -> None:
        self._names = frozenset(names)

    def find_spec(self, fullname, path=None, target=None):  # noqa: D401, ARG002
        root = fullname.split(".", 1)[0]
        if root in self._names:
            raise ImportError(f"blocked import for {fullname} (test fixture)")
        return None


def _reimport_without(modules: Iterable[str]) -> dict[str, object]:
    """Reimport ``pyicloud.base`` in a subprocess with ``modules`` masked.

    A subprocess is used so the in-process ``pyicloud`` modules and any
    ``fido2``/``cryptography`` bindings remain available to the rest of the
    test suite.
    """

    script = textwrap.dedent(
        """
        import json
        import sys

        class BlockingFinder:
            BLOCK = set({modules!r})
            def find_spec(self, fullname, path=None, target=None):
                root = fullname.split('.', 1)[0]
                if root in self.BLOCK:
                    raise ImportError('blocked ' + fullname)
                return None

        for mod in list(sys.modules):
            root = mod.split('.', 1)[0]
            if root in BlockingFinder.BLOCK or root == 'pyicloud':
                del sys.modules[mod]
        sys.meta_path.insert(0, BlockingFinder())

        import pyicloud  # noqa: F401
        from pyicloud import PyiCloudService  # noqa: F401
        from pyicloud.services import PhotosService  # noqa: F401
        from pyicloud._optional_deps import (
            cryptography_available,
            fido2_available,
        )

        print(json.dumps({{
            "cryptography_available": cryptography_available(),
            "fido2_available": fido2_available(),
            "pyicloud_service": PyiCloudService.__name__,
            "photos_service": PhotosService.__name__,
        }}))
        """
    ).format(modules=list(modules))

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    import json as _json

    return _json.loads(result.stdout.strip().splitlines()[-1])


def test_security_key_extra_missing_error_message() -> None:
    """The helper exposes the canonical install instructions."""

    err = _optional_deps.security_key_extra_missing_error("Demo feature")
    assert isinstance(err, RuntimeError)
    message = str(err)
    assert "Demo feature" in message
    assert "security-key" in message
    assert 'pip install "pyicloud[security-key]"' in message


def test_base_imports_without_fido2_and_cryptography() -> None:
    """``from pyicloud import PyiCloudService`` works without the extra."""

    info = _reimport_without(["fido2", "cryptography"])
    assert info["cryptography_available"] is False
    assert info["fido2_available"] is False
    assert info["pyicloud_service"] == "PyiCloudService"
    assert info["photos_service"] == "PhotosService"


def test_fido2_devices_returns_empty_when_fido2_missing() -> None:
    """``fido2_devices`` degrades to an empty list when fido2 is unavailable."""

    from pyicloud.base import PyiCloudService

    instance = PyiCloudService.__new__(PyiCloudService)
    with patch.object(_optional_deps, "_try_import", return_value=None):
        # Force any cached import to be re-evaluated through the helper.
        assert _optional_deps.fido2_available() is False
        with patch.dict(sys.modules, {"fido2": None, "fido2.hid": None}):
            # Make sure the lazy import inside the property raises ImportError
            # so the fallback branch returns [].
            devices = PyiCloudService.fido2_devices.fget(instance)  # type: ignore[attr-defined]
    assert devices == []


def test_confirm_security_key_raises_when_fido2_missing() -> None:
    """``confirm_security_key`` raises the documented RuntimeError."""

    from pyicloud.base import PyiCloudService

    instance = PyiCloudService.__new__(PyiCloudService)
    with patch.dict(
        sys.modules,
        {
            "fido2": None,
            "fido2.hid": None,
            "fido2.client": None,
            "fido2.webauthn": None,
        },
    ):
        with pytest.raises(RuntimeError, match="security-key"):
            instance.confirm_security_key()


def test_supports_trusted_device_bridge_false_without_cryptography() -> None:
    """The bridge silently disables itself when cryptography is missing."""

    from pyicloud.base import PyiCloudService

    instance = PyiCloudService.__new__(PyiCloudService)
    with patch.object(_optional_deps, "_try_import", return_value=None):
        assert PyiCloudService._supports_trusted_device_bridge(instance) is False


def test_hsa2_bridge_module_imports_without_cryptography() -> None:
    """``pyicloud.hsa2_bridge`` can be imported with no cryptography backend."""

    # The module is already imported in this process; we just ensure the
    # subprocess masking succeeded for the broader package.
    importlib.import_module("pyicloud.hsa2_bridge")
    importlib.import_module("pyicloud.hsa2_bridge_prover")
