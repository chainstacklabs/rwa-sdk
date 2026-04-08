"""Tests for core/http.py."""

import urllib.error
from typing import Any
from unittest.mock import patch

import pytest

from rwa_sdk.core.exceptions import HttpError
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


def test_network_error_raises_http_error():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        with pytest.raises(HttpError) as exc_info:
            DefaultHttpClient().get_json("http://example.com/api")
    assert "http://example.com/api" in exc_info.value.url
    assert isinstance(exc_info.value.cause, urllib.error.URLError)
