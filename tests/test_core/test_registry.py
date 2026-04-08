"""Tests for core.registry."""

import pytest

from rwa_sdk.core.registry import BACKED, CENTRIFUGE, ETHEREUM, MAPLE, get_addresses


@pytest.mark.parametrize("protocol", ["backed", "centrifuge", "maple"])
def test_tokens_shared_split(protocol: str) -> None:
    addrs = get_addresses(protocol)
    assert "tokens" in addrs, f"{protocol} missing 'tokens' key"
    assert "shared" in addrs, f"{protocol} missing 'shared' key"
    assert isinstance(addrs["tokens"], dict)
    assert isinstance(addrs["shared"], dict)


def test_backed_sanctions_list_in_shared() -> None:
    shared = get_addresses("backed")["shared"]
    assert "sanctions_list" in shared


def test_centrifuge_infra_in_shared() -> None:
    shared = get_addresses("centrifuge")["shared"]
    assert "spoke" in shared
    assert "vault_registry" in shared


def test_maple_globals_in_shared() -> None:
    shared = get_addresses("maple")["shared"]
    assert "globals" in shared


def test_unknown_protocol_returns_empty() -> None:
    assert get_addresses("unknown") == {}


def test_unknown_chain_returns_empty() -> None:
    assert get_addresses("backed", chain_id=999) == {}
