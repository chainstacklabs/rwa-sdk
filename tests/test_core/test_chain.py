"""Tests for core.chain."""

from rwa_sdk.core.chain import Chain, chain_name


class TestChain:
    def test_chain_is_int(self):
        assert Chain.ETHEREUM == 1
        assert Chain.ARBITRUM == 42161

    def test_chain_label(self):
        assert Chain.ETHEREUM.label == "Ethereum"
        assert Chain.ARBITRUM.label == "Arbitrum"
        assert Chain.BASE.label == "Base"

    def test_chain_from_int(self):
        assert Chain(1) is Chain.ETHEREUM
        assert Chain(8453) is Chain.BASE

    def test_chain_name_known(self):
        assert chain_name(1) == "Ethereum"
        assert chain_name(42161) == "Arbitrum"

    def test_chain_name_unknown(self):
        assert chain_name(999) == "Chain 999"
