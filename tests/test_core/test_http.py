"""Tests for core/http.py."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

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
    stub = StubHttpClient({"ok": True})
    assert isinstance(stub, HttpClient)


def test_default_client_satisfies_protocol():
    assert isinstance(DefaultHttpClient(), HttpClient)


def test_default_client_get_json():
    fake_response = {"result": "data"}
    fake_body = json.dumps(fake_response).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = DefaultHttpClient()
        result = client.get_json("http://example.com/api")

    assert result == fake_response


def test_default_client_post_json():
    fake_response = {"status": "ok"}
    fake_body = json.dumps(fake_response).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = DefaultHttpClient()
        result = client.post_json("http://example.com/api", {"query": "test"})

    assert result == fake_response
