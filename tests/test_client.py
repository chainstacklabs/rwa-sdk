"""Tests for the RWAChain client."""

from unittest.mock import MagicMock, patch

import pytest

from rwa_sdk.client import RWAChain
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


def _make_adapter_mock(protocol_name: str) -> MagicMock:
    m = MagicMock()
    m.protocol = protocol_name
    m.all_tokens.return_value = []
    return m


@pytest.fixture
def rwa():
    """RWAChain instance with all adapters mocked to avoid real RPC calls."""
    instances = {name: _make_adapter_mock(name) for name in ("ondo", "backed", "securitize", "maple", "centrifuge")}
    mock_registry = {name: MagicMock(return_value=inst) for name, inst in instances.items()}

    with (
        patch("rwa_sdk.protocols._REGISTRY", mock_registry),
        patch("rwa_sdk.client.create_rpc_provider") as mock_provider,
    ):
        mock_provider.return_value.eth.chain_id = 1
        yield RWAChain()


class TestAdaptersNamespace:
    def test_adapters_ondo(self, rwa):
        assert rwa.adapters.ondo.protocol == "ondo"

    def test_adapters_backed(self, rwa):
        assert rwa.adapters.backed.protocol == "backed"

    def test_adapters_securitize(self, rwa):
        assert rwa.adapters.securitize.protocol == "securitize"

    def test_adapters_maple(self, rwa):
        assert rwa.adapters.maple.protocol == "maple"

    def test_adapters_centrifuge(self, rwa):
        assert rwa.adapters.centrifuge.protocol == "centrifuge"

    def test_adapters_raises_when_custom_adapters_injected(self):
        with patch("rwa_sdk.client.create_rpc_provider") as mock_provider:
            mock_provider.return_value.eth.chain_id = 1
            rwa = RWAChain(rpc_url="http://fake", adapters=[])
        with pytest.raises(RuntimeError, match="not available"):
            _ = rwa.adapters

    def test_adapter_by_protocol_raises_for_unknown_protocol(self, rwa):
        with pytest.raises(ValueError, match="No adapter registered for protocol"):
            rwa._adapter_by_protocol("nonexistent")


class TestAllTokens:
    def test_all_tokens_aggregates_all_adapters(self, rwa):
        usdy = _make_token("USDY", "0xAAA", "ondo")
        bib01 = _make_token("bIB01", "0xBBB", "backed")

        rwa.adapters.ondo.all_tokens.return_value = [usdy]
        rwa.adapters.backed.all_tokens.return_value = [bib01]

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

    def test_registered_adapter_accessible_via_lookup(self, rwa):
        stub = MagicMock(spec=ProtocolAdapter)
        stub.protocol = "custom"
        stub.all_tokens.return_value = []

        rwa.register_adapter(stub)
        assert rwa._adapter_by_protocol("custom") is stub


class TestInjectableAdapters:
    def test_injected_adapters_replace_defaults(self):
        mock_adapter = MagicMock(spec=ProtocolAdapter)
        mock_adapter.protocol = "custom"
        mock_adapter.all_tokens.return_value = []

        with patch("rwa_sdk.client.create_rpc_provider") as mock_provider:
            mock_provider.return_value.eth.chain_id = 1
            rwa = RWAChain(rpc_url="http://fake", adapters=[mock_adapter])

        assert len(rwa._adapters) == 1
        assert rwa._adapters[0].protocol == "custom"

    def test_default_adapters_instantiated_when_none_passed(self):
        instances = {name: _make_adapter_mock(name) for name in ("ondo", "backed", "securitize", "maple", "centrifuge")}
        mock_registry = {name: MagicMock(return_value=inst) for name, inst in instances.items()}

        with (
            patch("rwa_sdk.protocols._REGISTRY", mock_registry),
            patch("rwa_sdk.client.create_rpc_provider") as mock_provider,
        ):
            mock_provider.return_value.eth.chain_id = 1
            rwa = RWAChain(rpc_url="http://fake")

        assert len(rwa._adapters) == 5

    def test_empty_adapters_list_is_accepted(self):
        with patch("rwa_sdk.client.create_rpc_provider") as mock_provider:
            mock_provider.return_value.eth.chain_id = 1
            rwa = RWAChain(rpc_url="http://fake", adapters=[])

        assert rwa._adapters == []


class TestBalanceOf:
    def test_balance_of_resolves_symbol_and_delegates_to_erc20(self, rwa):
        usdy = _make_token("USDY", "0x96F6eF951840721AdBF46Ac996b59E0235CB985C", "ondo")
        rwa.adapters.ondo.all_tokens.return_value = [usdy]

        with patch("rwa_sdk.client.erc20.read_balance", return_value=42.5) as mock_read:
            result = rwa.balance_of("USDY", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")

        mock_read.assert_called_once_with(
            rwa._chain,
            "0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        )
        assert result == 42.5

    def test_balance_of_is_case_insensitive(self, rwa):
        usdy = _make_token("USDY", "0x96F6eF951840721AdBF46Ac996b59E0235CB985C", "ondo")
        rwa.adapters.ondo.all_tokens.return_value = [usdy]
        with patch("rwa_sdk.client.erc20.read_balance", return_value=1.0):
            result = rwa.balance_of("usdy", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        assert result == 1.0

    def test_balance_of_raises_for_unknown_symbol(self, rwa):
        with pytest.raises(ValueError, match="Unknown token symbol"):
            rwa.balance_of("UNKNOWN", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")

    def test_balance_of_raises_for_invalid_wallet_address(self, rwa):
        with pytest.raises(ValueError, match="Invalid EVM address"):
            rwa.balance_of("USDY", "not-an-address")


