"""HTTP client abstraction for injectable, testable HTTP I/O."""

import json
import urllib.error
import urllib.request
from typing import Any, Protocol, runtime_checkable

from rwa_sdk.core.exceptions import HttpError


@runtime_checkable
class HttpClient(Protocol):
    """Protocol for injectable HTTP clients."""

    def get_json(self, url: str, *, timeout: int = 15) -> dict[str, Any]:
        """Perform a GET request and return parsed JSON."""
        ...

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        """Perform a POST request with a JSON body and return parsed JSON."""
        ...


class DefaultHttpClient:
    """urllib-based HTTP client implementation."""

    def get_json(self, url: str, *, timeout: int = 15) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise HttpError(url, exc) from exc

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode()
        merged = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(url, data=data, headers=merged, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise HttpError(url, exc) from exc
