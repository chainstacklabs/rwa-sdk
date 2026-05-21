"""Tests for the Superstate adapter — USTB + USCC."""

from unittest.mock import MagicMock, patch

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError, RegistryError
from rwa_sdk.core.models import Category, ComplianceCheck, ComplianceMethod, YieldType
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.protocols.superstate import SuperstateAdapter

USTB = "0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e"
USCC = "0x14d60E7FDC0D71d8611742720E4C50E7a974020c"
WALLET_A = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
WALLET_B = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"

FIXED_NOW = 1_750_000_000
FRESH_TS = FIXED_NOW - 30
STALE_TS = FIXED_NOW - 90_000  # 25h, beyond the 24h heartbeat


def _erc20_and_chainlink_mock(symbol: str, name: str, price_raw: int, ts: int) -> MagicMock:
    contract = MagicMock()
    contract.functions.decimals.return_value.call.return_value = 6
    contract.functions.totalSupply.return_value.call.return_value = 1_000_000 * 10**6
    contract.functions.symbol.return_value.call.return_value = symbol
    contract.functions.name.return_value.call.return_value = name
    contract.functions.latestRoundData.return_value.call.return_value = (0, price_raw, 0, ts, 0)
    return contract


class TestSuperstateAdapter:
    def test_satisfies_protocol_adapter(self, mock_chain):
        adapter = SuperstateAdapter(mock_chain)
        assert isinstance(adapter, ProtocolAdapter)
        assert adapter.protocol == "superstate"
        assert adapter.chain_id == 1

    def test_init_raises_registry_error_on_unsupported_chain(self):
        chain = MagicMock()
        chain.chain_id = 137  # Polygon — Superstate not deployed
        with pytest.raises(RegistryError, match="not deployed on chain 137"):
            SuperstateAdapter(chain)

    def test_all_tokens_returns_two_tokens(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_chainlink_mock(
            "USTB", "Superstate", int(11.0 * 10**6), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            tokens = SuperstateAdapter(mock_chain).all_tokens()
        assert len(tokens) == 2
        assert all(t.protocol == "superstate" for t in tokens)
        assert all(t.yield_type == YieldType.ACCUMULATING for t in tokens)

    def test_ustb_category_is_us_treasury(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_chainlink_mock(
            "USTB", "Superstate USTB", int(11.0 * 10**6), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            token = SuperstateAdapter(mock_chain).ustb()
        assert token.category == Category.US_TREASURY

    def test_uscc_category_is_none(self, mock_chain):
        # USCC (crypto-basis carry) has no fitting Category enum value today.
        mock_chain.get_contract.return_value = _erc20_and_chainlink_mock(
            "USCC", "Superstate USCC", int(11.5 * 10**6), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            token = SuperstateAdapter(mock_chain).uscc()
        assert token.category is None

    def test_ustb_price_returns_float(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_chainlink_mock(
            "USTB", "Superstate USTB", int(11.0885 * 10**6), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            assert SuperstateAdapter(mock_chain).ustb_price() == pytest.approx(11.0885)

    def test_uscc_price_returns_float(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_chainlink_mock(
            "USCC", "Superstate USCC", int(11.59 * 10**6), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            assert SuperstateAdapter(mock_chain).uscc_price() == pytest.approx(11.59)

    def test_stale_oracle_raises(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_chainlink_mock(
            "USTB", "Superstate USTB", int(11.0 * 10**6), STALE_TS
        )
        adapter = SuperstateAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            with pytest.raises(OracleStalenessError):
                adapter.ustb_price()

    def test_can_transfer_allowed(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = SuperstateAdapter(mock_chain)
        contract = MagicMock()
        is_allowed_fn = contract.functions.isAddressAllowedForPrivateInstrument
        is_allowed_fn.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(USTB, WALLET_A, WALLET_B)
        assert isinstance(result, ComplianceCheck)
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.KYC_REGISTRY
        assert result.blocking_party is None

    def test_can_transfer_sender_blocked(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = SuperstateAdapter(mock_chain)
        contract = MagicMock()
        # sender = False, receiver = True (but never queried after sender fails)
        contract.functions.isAddressAllowedForPrivateInstrument.return_value.call.side_effect = [
            False,
            True,
        ]
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(USTB, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "sender"
        assert "sender" in result.restriction_message
        assert result.method == ComplianceMethod.KYC_REGISTRY

    def test_can_transfer_receiver_blocked(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = SuperstateAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.isAddressAllowedForPrivateInstrument.return_value.call.side_effect = [
            True,
            False,
        ]
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(USTB, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "receiver"
        assert "receiver" in result.restriction_message

    def test_can_transfer_unknown_token_returns_none(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = SuperstateAdapter(mock_chain)
        result = adapter.can_transfer(
            "0x000000000000000000000000000000000000dEaD", WALLET_A, WALLET_B
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_can_transfer_dispatches_per_token(self, mock_chain):
        # USTB and USCC have distinct fund_symbol values — verify the right one is sent.
        mock_chain.checksum.side_effect = lambda x: x
        adapter = SuperstateAdapter(mock_chain)
        contract = MagicMock()
        is_allowed_fn = contract.functions.isAddressAllowedForPrivateInstrument
        is_allowed_fn.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        adapter.can_transfer(USCC, WALLET_A, WALLET_B)
        first_call = contract.functions.isAddressAllowedForPrivateInstrument.call_args_list[0]
        # signature is (address, fund_symbol)
        assert first_call.args[1] == "USCC"

    def test_is_allowed_unknown_fund_raises(self, mock_chain):
        adapter = SuperstateAdapter(mock_chain)
        with pytest.raises(RegistryError, match="Unknown Superstate fund"):
            adapter.is_allowed(WALLET_A, "MUSD")
