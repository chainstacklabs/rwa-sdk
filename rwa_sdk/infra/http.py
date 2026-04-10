"""HTTP client abstraction for injectable, testable HTTP I/O."""

import json
import urllib.error
import urllib.parse
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


_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _require_http_scheme(url: str) -> None:
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Disallowed URL scheme {scheme!r}: only http and https are permitted")


class DefaultHttpClient:
    """urllib-based HTTP client implementation."""

    def get_json(self, url: str, *, timeout: int = 15) -> dict[str, Any]:
        _require_http_scheme(url)
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
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
        _require_http_scheme(url)
        data = json.dumps(payload).encode()
        merged = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(url, data=data, headers=merged, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise HttpError(url, exc) from exc
