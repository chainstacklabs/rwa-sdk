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


def _make_adapter_mock(protocol_name: str, chain_id: int = 1) -> MagicMock:
    m = MagicMock(spec=ProtocolAdapter)
    m.protocol = protocol_name
    m.chain_id = chain_id
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
        yield RWAChain(rpc_url="http://fake")


class TestAdaptersNamespace:
    @pytest.mark.parametrize("name", ["ondo", "backed", "securitize", "maple", "centrifuge"])
    def test_all_adapters_wired(self, rwa, name):
        assert getattr(rwa.adapters, name).protocol == name

    def test_adapters_raises_when_custom_adapters_injected(self):
        with patch("rwa_sdk.client.create_rpc_provider") as mock_provider:
            mock_provider.return_value.eth.chain_id = 1
            rwa = RWAChain(rpc_url="http://fake", adapters=[])
        with pytest.raises(RuntimeError, match="not available"):
            _ = rwa.adapters

class TestChainId:
    def test_chain_id_returns_chain_id(self, rwa):
        assert rwa.chain_id == 1


class TestLoadedProtocols:
    def test_loaded_protocols_returns_protocol_names(self, rwa):
        assert set(rwa.loaded_protocols) == {"ondo", "backed", "securitize", "maple", "centrifuge"}

    def test_loaded_protocols_reflects_injected_adapters(self):
        adapter_a = _make_adapter_mock("proto_a")
        adapter_b = _make_adapter_mock("proto_b")
        with patch("rwa_sdk.client.create_rpc_provider") as mock_provider:
            mock_provider.return_value.eth.chain_id = 42161
            rwa = RWAChain(rpc_url="http://fake", adapters=[adapter_a, adapter_b])
        assert rwa.loaded_protocols == ["proto_a", "proto_b"]


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

    def test_all_tokens_returns_partial_results_when_one_adapter_raises(self, rwa):
        usdy = _make_token("USDY", "0xAAA", "ondo")
        rwa.adapters.ondo.all_tokens.return_value = [usdy]
        rwa.adapters.backed.all_tokens.side_effect = RuntimeError("oracle down")

        import logging
        with patch("rwa_sdk.client._log") as mock_log:
            tokens = rwa.all_tokens()

        assert len(tokens) == 1
        assert tokens[0].symbol == "USDY"
        mock_log.warning.assert_called_once()


class TestRegisterAdapter:
    def test_register_adapter_accessible_via_all_tokens(self, rwa):
        custom_token = _make_token("CUSTOM", "0xCCC", "custom")
        stub = MagicMock(spec=ProtocolAdapter)
        stub.protocol = "custom"
        stub.all_tokens.return_value = [custom_token]

        rwa.register_adapter(stub)
        tokens = rwa.all_tokens()
        assert any(t.symbol == "CUSTOM" for t in tokens)

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


class TestCanTransfer:
    def test_delegates_to_correct_adapter(self, rwa):
        usdy = _make_token("USDY", "0x96F6eF951840721AdBF46Ac996b59E0235CB985C", "ondo")
        rwa.adapters.ondo.all_tokens.return_value = [usdy]
        from rwa_sdk.core.models import ComplianceCheck, ComplianceMethod
        rwa.adapters.ondo.can_transfer.return_value = ComplianceCheck(
            can_transfer=True, method=ComplianceMethod.BLOCKLIST
        )

        result = rwa.can_transfer(
            "USDY",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )

        rwa.adapters.ondo.can_transfer.assert_called_once_with(
            "0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            0,
        )
        assert result.can_transfer is True

    def test_is_case_insensitive(self, rwa):
        usdy = _make_token("USDY", "0x96F6eF951840721AdBF46Ac996b59E0235CB985C", "ondo")
        rwa.adapters.ondo.all_tokens.return_value = [usdy]
        from rwa_sdk.core.models import ComplianceCheck, ComplianceMethod
        rwa.adapters.ondo.can_transfer.return_value = ComplianceCheck(
            can_transfer=True, method=ComplianceMethod.BLOCKLIST
        )
        result = rwa.can_transfer("usdy", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B")
        assert result.can_transfer is True

    def test_raises_for_unknown_symbol(self, rwa):
        with pytest.raises(ValueError, match="Unknown token symbol"):
            rwa.can_transfer("UNKNOWN", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B")


