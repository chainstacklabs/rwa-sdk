"""Tests for core/http.py."""

from typing import Any

from rwa_sdk.core.http import DefaultHttpClient, HttpClient


class StubHttpClient:
    """Minimal stub satisfying the HttpClient Protocol for testing."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def get_json(self, _url: str, *, timeout: int = 15) -> dict[str, Any]:
        return self._response

    def post_json(
        self, _url: str, _payload: dict[str, Any], *, timeout: int = 15
    ) -> dict[str, Any]:
        return self._response


def test_stub_satisfies_protocol():
    """A custom class satisfies HttpClient without inheriting from it."""
    assert isinstance(StubHttpClient({"ok": True}), HttpClient)


def test_default_client_satisfies_protocol():
    assert isinstance(DefaultHttpClient(), HttpClient)
