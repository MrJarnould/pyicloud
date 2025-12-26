"""
Low-level CloudKit client for the Reminders container.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from pydantic import ValidationError

from .models.cloudkit import (
    CKQueryObject,
    CKQueryRequest,
    CKQueryResponse,
    CKZoneChangesResponse,
    CKZoneIDReq,
)

LOGGER = logging.getLogger(__name__)


class RemindersAuthError(Exception):
    """Auth/PCS/cookie issues (401/403)."""


class RemindersApiError(Exception):
    """Catch-all API error."""

    def __init__(self, message: str, payload: Optional[object] = None):
        super().__init__(message)
        self.payload = payload


class _CloudKitClient:
    """
    Minimal HTTP transport for CloudKit.
    """

    def __init__(self, base_url: str, session, base_params: Dict[str, object]):
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._params = self._normalize_params(base_params or {})

    @staticmethod
    def _normalize_params(params: Dict[str, object]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for k, v in params.items():
            if isinstance(v, bool):
                out[k] = "true" if v else "false"
            else:
                out[k] = str(v)
        return out

    def _build_url(self, path: str) -> str:
        from urllib.parse import urlencode

        q = urlencode(self._params)
        return f"{self._base_url}{path}" + (f"?{q}" if q else "")

    def post(self, path: str, payload: Dict) -> Dict:
        url = self._build_url(path)
        LOGGER.debug("POST to %s", url)
        resp = self._session.post(url, json=payload)
        code = getattr(resp, "status_code", 0)

        if code in (401, 403):
            raise RemindersAuthError(f"HTTP {code}: unauthorized")
        if code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = getattr(resp, "text", None)
            raise RemindersApiError(f"HTTP {code}", payload=body)

        try:
            return resp.json()
        except Exception:
            raise RemindersApiError(
                "Invalid JSON response", payload=getattr(resp, "text", None)
            )


class CloudKitRemindersClient:
    """
    Raw CloudKit service for the Reminders container.
    """

    def __init__(self, base_url: str, session, base_params: Dict[str, object]):
        self._http = _CloudKitClient(base_url, session, base_params)

    def query(
        self,
        *,
        query: CKQueryObject,
        zone_id: CKZoneIDReq,
        desired_keys: Optional[List[str]] = None,
        results_limit: Optional[int] = None,
        continuation: Optional[str] = None,
    ) -> CKQueryResponse:
        payload = CKQueryRequest(
            query=query,
            zoneID=zone_id,
            desiredKeys=desired_keys,
            resultsLimit=results_limit,
            continuationMarker=continuation,
        ).model_dump(exclude_none=True)

        data = self._http.post("/records/query", payload)
        try:
            return CKQueryResponse.model_validate(data)
        except ValidationError as e:
            raise RemindersApiError(
                "Query response validation failed", payload=data
            ) from e

    def changes(
        self,
        *,
        zone_id: CKZoneIDReq,
        results_limit: Optional[int] = None,
        desired_keys: Optional[List[str]] = None,
    ) -> CKZoneChangesResponse:
        """Fetch changes (sync) for a zone."""

        payload = {
            "zones": [
                {
                    "zoneID": zone_id.model_dump(exclude_none=True),
                    "desiredKeys": desired_keys,
                    # "syncToken": ... TODO: Add sync token support if needed
                }
            ],
            "resultsLimit": results_limit,
        }

        # Clean payload
        if results_limit is None:
            del payload["resultsLimit"]

        data = self._http.post("/changes/zone", payload)
        try:
            return CKZoneChangesResponse.model_validate(data)
        except ValidationError as e:
            raise RemindersApiError(
                "Changes response validation failed", payload=data
            ) from e
