"""HTTP client abstraction for injectable, testable HTTP I/O."""

import json
import urllib.error
import urllib.request
from typing import Any, Protocol, runtime_checkable

from rwa_sdk.core.exceptions import HttpError


@runtime_checkable
class HttpClient(Protocol):
    """Protocol for HTTP clients. Implement this to inject a custom HTTP client.

    Raises:
        HttpError: On any network failure, non-2xx response, or JSON decode error.
    """

    def get_json(self, url: str, *, timeout: int = 15) -> dict[str, Any]:
        """Perform a GET request and return the parsed JSON response."""
        ...

    def post_json(
        self, url: str, payload: dict[str, Any], *, timeout: int = 15
    ) -> dict[str, Any]:
        """Perform a POST request with a JSON body and return the parsed JSON response."""
        ...


class DefaultHttpClient:
    """Default urllib-based HTTP client.

    Raises:
        HttpError: Wraps urllib.error.URLError, urllib.error.HTTPError, and
            json.JSONDecodeError so callers only need to handle one exception type.
    """

    def get_json(self, url: str, *, timeout: int = 15) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise HttpError(url, exc) from exc

    def post_json(
        self, url: str, payload: dict[str, Any], *, timeout: int = 15
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise HttpError(url, exc) from exc
