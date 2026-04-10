"""Tests for core/http.py."""

import urllib.error
from typing import Any
from unittest.mock import patch

import pytest

from rwa_sdk.core.exceptions import HttpError
from rwa_sdk.infra.http import DefaultHttpClient


class StubHttpClient:
    """Minimal stub satisfying the HttpClient Protocol for testing."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def get_json(self, _url: str, *, timeout: int = 15) -> dict[str, Any]:
        return self._response

    def post_json(
        self,
        _url: str,
        _payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        return self._response


def test_network_error_raises_http_error():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        with pytest.raises(HttpError) as exc_info:
            DefaultHttpClient().get_json("http://example.com/api")
    assert "http://example.com/api" in exc_info.value.url
    assert isinstance(exc_info.value.cause, urllib.error.URLError)


@pytest.mark.parametrize("scheme", ["file", "ftp", "data", "gopher"])
def test_get_json_rejects_non_http_schemes(scheme: str):
    with pytest.raises(ValueError, match="scheme"):
        DefaultHttpClient().get_json(f"{scheme}:///etc/passwd")


@pytest.mark.parametrize("scheme", ["file", "ftp", "data"])
def test_post_json_rejects_non_http_schemes(scheme: str):
    with pytest.raises(ValueError, match="scheme"):
        DefaultHttpClient().post_json(f"{scheme}:///etc/passwd", {})


@pytest.mark.parametrize("url", ["http://example.com/api", "https://example.com/api"])
def test_http_and_https_schemes_are_accepted(url: str):
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = mock_open.return_value.__enter__.return_value
        mock_resp.read.return_value = b'{"ok": true}'
        result = DefaultHttpClient().get_json(url)
    assert result == {"ok": True}
