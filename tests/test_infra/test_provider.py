"""Tests for infra.provider."""

import pytest

from rwa_sdk.infra.provider import create_rpc_provider


@pytest.mark.parametrize("bad_url", ["", "   ", "\t", "\n", "  \t\n  "])
def test_create_rpc_provider_rejects_blank_urls(bad_url: str):
    with pytest.raises(ValueError, match="rpc_url"):
        create_rpc_provider(bad_url)


def test_create_rpc_provider_returns_web3_for_valid_url():
    from web3 import Web3

    w3 = create_rpc_provider("https://example.com/rpc")
    assert isinstance(w3, Web3)
