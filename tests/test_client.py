"""Tests for the refactored RWA client."""

from unittest.mock import MagicMock, patch

import pytest

from rwa_sdk.client import RWA
from rwa_sdk.core.models import TokenInfo, YieldType
from rwa_sdk.protocols.base import ProtocolAdapter


def _make_token(symbol: str, address: str, protocol: str) -> TokenInfo:
    return TokenInfo(
        symbol=symbol,
        name=symbol,
        address=address,
        decimals=18,
        total_supply=1000.0,
        yield_type=YieldType.ACCUMULATING,
        protocol=protocol,
    )


@pytest.fixture
def rwa():
    """RWA instance with all adapters mocked to avoid real RPC calls."""
    with (
        patch("rwa_sdk.client.OndoAdapter") as MockOndo,
        patch("rwa_sdk.client.BackedAdapter") as MockBacked,
        patch("rwa_sdk.client.SecuritizeAdapter") as MockSecuritize,
        patch("rwa_sdk.client.MapleAdapter") as MockMaple,
        patch("rwa_sdk.client.CentrifugeAdapter") as MockCentrifuge,
        patch("rwa_sdk.client.create_provider"),
    ):
        MockOndo.return_value.protocol = "ondo"
        MockBacked.return_value.protocol = "backed"
        MockSecuritize.return_value.protocol = "securitize"
        MockMaple.return_value.protocol = "maple"
        MockCentrifuge.return_value.protocol = "centrifuge"

        for mock in (MockOndo, MockBacked, MockSecuritize, MockMaple, MockCentrifuge):
            mock.return_value.all_tokens.return_value = []

        yield RWA()


class TestBackwardsCompatProperties:
    def test_ondo_property_returns_adapter(self, rwa):
        adapter = rwa.ondo
        assert adapter.protocol == "ondo"

    def test_backed_property_returns_adapter(self, rwa):
        assert rwa.backed.protocol == "backed"

    def test_securitize_property_returns_adapter(self, rwa):
        assert rwa.securitize.protocol == "securitize"

    def test_maple_property_returns_adapter(self, rwa):
        assert rwa.maple.protocol == "maple"

    def test_centrifuge_property_returns_adapter(self, rwa):
        assert rwa.centrifuge.protocol == "centrifuge"


class TestAllTokens:
    def test_all_tokens_aggregates_all_adapters(self, rwa):
        usdy = _make_token("USDY", "0xAAA", "ondo")
        bib01 = _make_token("bIB01", "0xBBB", "backed")

        rwa.ondo.all_tokens.return_value = [usdy]
        rwa.backed.all_tokens.return_value = [bib01]

        tokens = rwa.all_tokens()
        assert len(tokens) == 2
        symbols = {t.symbol for t in tokens}
        assert symbols == {"USDY", "bIB01"}

    def test_all_tokens_returns_empty_when_adapters_have_none(self, rwa):
        assert rwa.all_tokens() == []


class TestRegisterAdapter:
    def test_register_adapter_adds_to_internal_list(self, rwa):
        stub = MagicMock(spec=ProtocolAdapter)
        stub.protocol = "custom"
        stub.all_tokens.return_value = []

        initial_count = len(rwa._adapters)
        rwa.register_adapter(stub)
        assert len(rwa._adapters) == initial_count + 1

    def test_register_adapter_accessible_via_all_tokens(self, rwa):
        custom_token = _make_token("CUSTOM", "0xCCC", "custom")
        stub = MagicMock(spec=ProtocolAdapter)
        stub.protocol = "custom"
        stub.all_tokens.return_value = [custom_token]

        rwa.register_adapter(stub)
        tokens = rwa.all_tokens()
        assert any(t.symbol == "CUSTOM" for t in tokens)

    def test_registered_adapter_accessible_as_property_via_lookup(self, rwa):
        stub = MagicMock(spec=ProtocolAdapter)
        stub.protocol = "custom"
        stub.all_tokens.return_value = []

        rwa.register_adapter(stub)
        assert rwa._adapter_by_protocol("custom") is stub


class TestBalanceOf:
    def test_balance_of_resolves_symbol_and_delegates_to_erc20(self, rwa):
        usdy = _make_token("USDY", "0x96F6eF951840721AdBF46Ac996b59E0235CB985C", "ondo")
        rwa.ondo.all_tokens.return_value = [usdy]

        with patch("rwa_sdk.client.erc20.read_balance", return_value=42.5) as mock_read:
            result = rwa.balance_of("USDY", "0xWallet")

        mock_read.assert_called_once_with(
            rwa._w3,
            "0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
            "0xWallet",
        )
        assert result == 42.5

    def test_balance_of_is_case_insensitive(self, rwa):
        usdy = _make_token("USDY", "0x96F6eF951840721AdBF46Ac996b59E0235CB985C", "ondo")
        rwa.ondo.all_tokens.return_value = [usdy]

        with patch("rwa_sdk.client.erc20.read_balance", return_value=1.0):
            result = rwa.balance_of("usdy", "0xWallet")

        assert result == 1.0

    def test_balance_of_raises_for_unknown_symbol(self, rwa):
        with pytest.raises(ValueError, match="Unknown token symbol"):
            rwa.balance_of("UNKNOWN", "0xWallet")
