"""Tests for the OpenEden adapter — TBILL on Ethereum and Arbitrum."""

from unittest.mock import MagicMock, patch

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError, RegistryError
from rwa_sdk.core.models import Category, ComplianceCheck, ComplianceMethod, YieldType
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.protocols.openeden import OpenEdenAdapter

TBILL_ETH = "0xdd50C053C096CB04A3e3362E2b622529EC5f2e8a"
TBILL_ARB = "0xF84D28A8D28292842dD73D1c5F99476A80b6666A"
WALLET_A = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
WALLET_B = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"

FIXED_NOW = 1_750_000_000
FRESH_TS = FIXED_NOW - 30
STALE_TS = FIXED_NOW - 90_000  # 25h, beyond the 24h heartbeat


def _erc20_and_oracle_mock(symbol: str, name: str, price_raw: int, ts: int) -> MagicMock:
    contract = MagicMock()
    contract.functions.decimals.return_value.call.return_value = 6
    contract.functions.totalSupply.return_value.call.return_value = 1_000_000 * 10**6
    contract.functions.symbol.return_value.call.return_value = symbol
    contract.functions.name.return_value.call.return_value = name
    contract.functions.latestRoundData.return_value.call.return_value = (0, price_raw, 0, ts, 0)
    return contract


def _arbitrum_chain() -> MagicMock:
    chain = MagicMock()
    chain.chain_id = 42161
    return chain


class TestOpenEdenAdapter:
    def test_satisfies_protocol_adapter(self, mock_chain):
        adapter = OpenEdenAdapter(mock_chain)
        assert isinstance(adapter, ProtocolAdapter)
        assert adapter.protocol == "openeden"
        assert adapter.chain_id == 1

    def test_loads_on_arbitrum(self):
        adapter = OpenEdenAdapter(_arbitrum_chain())
        assert adapter.chain_id == 42161

    def test_init_raises_registry_error_on_unsupported_chain(self):
        chain = MagicMock()
        chain.chain_id = 137  # Polygon — OpenEden not deployed
        with pytest.raises(RegistryError, match="not deployed on chain 137"):
            OpenEdenAdapter(chain)

    def test_ethereum_and_arbitrum_use_distinct_token_addresses(self):
        eth_token = OpenEdenAdapter.config[
            list(OpenEdenAdapter.config)[0]  # Chain.ETHEREUM
        ].tokens["tbill"].token
        arb_token = OpenEdenAdapter.config[
            list(OpenEdenAdapter.config)[1]  # Chain.ARBITRUM
        ].tokens["tbill"].token
        assert eth_token.lower() != arb_token.lower()

    def test_all_tokens_returns_one_token(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "TBILL", "OpenEden T-Bills", int(1.14 * 10**8), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            tokens = OpenEdenAdapter(mock_chain).all_tokens()
        assert len(tokens) == 1
        assert tokens[0].protocol == "openeden"
        assert tokens[0].yield_type == YieldType.ACCUMULATING
        assert tokens[0].category == Category.US_TREASURY

    def test_tbill_price_returns_float_at_8_decimal_oracle(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "TBILL", "OpenEden T-Bills", int(1.14464040 * 10**8), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            assert OpenEdenAdapter(mock_chain).tbill_price() == pytest.approx(1.1446404)

    def test_stale_oracle_raises(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "TBILL", "OpenEden T-Bills", int(1.14 * 10**8), STALE_TS
        )
        adapter = OpenEdenAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            with pytest.raises(OracleStalenessError):
                adapter.tbill_price()

    def test_can_transfer_allowed_when_both_kyc_and_unbanned(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.isBanned.return_value.call.return_value = False
        contract.functions.isKyc.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(TBILL_ETH, WALLET_A, WALLET_B)
        assert isinstance(result, ComplianceCheck)
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.KYC_REGISTRY
        assert result.blocking_party is None

    def test_can_transfer_sender_not_kycd(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.isBanned.return_value.call.return_value = False
        # sender isKyc=False (first call), receiver branch never reached
        contract.functions.isKyc.return_value.call.side_effect = [False, True]
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(TBILL_ETH, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "sender"
        assert "sender" in result.restriction_message
        assert "KYC" in result.restriction_message
        assert result.method == ComplianceMethod.KYC_REGISTRY

    def test_can_transfer_receiver_not_kycd(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.isBanned.return_value.call.return_value = False
        contract.functions.isKyc.return_value.call.side_effect = [True, False]
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(TBILL_ETH, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "receiver"
        assert "receiver" in result.restriction_message

    def test_can_transfer_sender_banned_overrides_kyc(self, mock_chain):
        # Banned-but-KYC'd sender must surface the ban, not silently pass on KYC.
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        contract = MagicMock()
        # sender isBanned=True (first call), receiver branch never reached
        contract.functions.isBanned.return_value.call.side_effect = [True, False]
        contract.functions.isKyc.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(TBILL_ETH, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "sender"
        assert "banned" in result.restriction_message

    def test_can_transfer_receiver_banned(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.isBanned.return_value.call.side_effect = [False, True]
        contract.functions.isKyc.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(TBILL_ETH, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "receiver"
        assert "banned" in result.restriction_message

    def test_can_transfer_unknown_token_returns_none(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        result = adapter.can_transfer(
            "0x000000000000000000000000000000000000dEaD", WALLET_A, WALLET_B
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_can_transfer_resolves_arbitrum_token_address(self):
        # On Arbitrum, the Ethereum TBILL address must NOT resolve — adapters
        # are per-chain instances and the address registry is partitioned.
        chain = _arbitrum_chain()
        chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(chain)
        contract = MagicMock()
        contract.functions.isBanned.return_value.call.return_value = False
        contract.functions.isKyc.return_value.call.return_value = True
        chain.get_contract.return_value = contract
        # Arbitrum TBILL resolves: passes through KYC checks
        ok = adapter.can_transfer(TBILL_ARB, WALLET_A, WALLET_B)
        assert ok.method == ComplianceMethod.KYC_REGISTRY
        # Ethereum TBILL address on the Arbitrum instance is "unknown"
        eth_on_arb = adapter.can_transfer(TBILL_ETH, WALLET_A, WALLET_B)
        assert eth_on_arb.method == ComplianceMethod.NONE

    def test_is_allowed_unknown_fund_raises(self, mock_chain):
        adapter = OpenEdenAdapter(mock_chain)
        with pytest.raises(RegistryError, match="Unknown OpenEden fund"):
            adapter.is_allowed(WALLET_A, "usdo")

    def test_is_allowed_banned_returns_false(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OpenEdenAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.isKyc.return_value.call.return_value = True
        contract.functions.isBanned.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        assert adapter.is_allowed(WALLET_A, "tbill") is False
