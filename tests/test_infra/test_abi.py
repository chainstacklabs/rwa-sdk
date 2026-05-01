"""Tests for infra.abi — ABI loader and cache safety."""

from rwa_sdk.infra.abi import combined_abi, load_abi


def test_load_abi_returns_independent_lists():
    """Mutating one returned list must not poison subsequent calls."""
    first = load_abi("erc20")
    first.append({"poisoned": True})
    second = load_abi("erc20")
    assert all("poisoned" not in entry for entry in second)


def test_combined_abi_returns_independent_lists():
    first = combined_abi("erc20", "erc4626")
    first.clear()
    second = combined_abi("erc20", "erc4626")
    assert len(second) > 0


def test_load_abi_returns_expected_methods():
    abi = load_abi("erc20")
    names = {entry.get("name") for entry in abi if entry.get("type") == "function"}
    assert {"name", "symbol", "decimals", "totalSupply", "balanceOf"} <= names


def test_combined_abi_merges_in_order():
    erc20 = load_abi("erc20")
    erc4626 = load_abi("erc4626")
    merged = combined_abi("erc20", "erc4626")
    assert len(merged) == len(erc20) + len(erc4626)
