"""Tests for the Hashnote adapter — USYC."""

from unittest.mock import MagicMock, patch

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError, RegistryError
from rwa_sdk.core.models import Category, ComplianceCheck, ComplianceMethod, YieldType
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.protocols.hashnote import HashnoteAdapter

USYC = "0x136471a34F6ef19fE571EFFC1CA711fdb8E49f2b"
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


class TestHashnoteAdapter:
    def test_satisfies_protocol_adapter(self, mock_chain):
        adapter = HashnoteAdapter(mock_chain)
        assert isinstance(adapter, ProtocolAdapter)
        assert adapter.protocol == "hashnote"
        assert adapter.chain_id == 1

    def test_init_raises_registry_error_on_unsupported_chain(self):
        chain = MagicMock()
        chain.chain_id = 137  # Polygon — USYC not deployed there
        with pytest.raises(RegistryError, match="not deployed on chain 137"):
            HashnoteAdapter(chain)

    def test_all_tokens_returns_one_token(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "USYC", "US Yield Coin", int(1.125 * 10**18), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            tokens = HashnoteAdapter(mock_chain).all_tokens()
        assert len(tokens) == 1
        assert tokens[0].protocol == "hashnote"
        assert tokens[0].yield_type == YieldType.ACCUMULATING

    def test_usyc_category_is_us_treasury(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "USYC", "US Yield Coin", int(1.125 * 10**18), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            token = HashnoteAdapter(mock_chain).usyc()
        assert token.category == Category.US_TREASURY

    def test_usyc_price_returns_float_at_18_decimal_oracle(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "USYC", "US Yield Coin", int(1.1257 * 10**18), FRESH_TS
        )
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            assert HashnoteAdapter(mock_chain).usyc_price() == pytest.approx(1.1257)

    def test_stale_oracle_raises(self, mock_chain):
        mock_chain.get_contract.return_value = _erc20_and_oracle_mock(
            "USYC", "US Yield Coin", int(1.125 * 10**18), STALE_TS
        )
        adapter = HashnoteAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            with pytest.raises(OracleStalenessError):
                adapter.usyc_price()

    def test_can_transfer_allowed_when_both_entitled(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = HashnoteAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.canCall.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(USYC, WALLET_A, WALLET_B)
        assert isinstance(result, ComplianceCheck)
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.KYC_REGISTRY
        assert result.blocking_party is None

    def test_can_transfer_sender_not_entitled(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = HashnoteAdapter(mock_chain)
        contract = MagicMock()
        # sender canCall=False; receiver branch never reached
        contract.functions.canCall.return_value.call.side_effect = [False, True]
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(USYC, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "sender"
        assert "sender" in result.restriction_message
        assert result.method == ComplianceMethod.KYC_REGISTRY

    def test_can_transfer_receiver_not_entitled(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = HashnoteAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.canCall.return_value.call.side_effect = [True, False]
        mock_chain.get_contract.return_value = contract
        result = adapter.can_transfer(USYC, WALLET_A, WALLET_B)
        assert result.can_transfer is False
        assert result.blocking_party == "receiver"
        assert "receiver" in result.restriction_message

    def test_can_transfer_unknown_token_returns_none(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = HashnoteAdapter(mock_chain)
        result = adapter.can_transfer(
            "0x000000000000000000000000000000000000dEaD", WALLET_A, WALLET_B
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_can_transfer_passes_transfer_selector(self, mock_chain):
        # Verify the ERC-20 transfer(address,uint256) selector is what gets sent
        # to Entitlements.canCall, not e.g. an empty selector.
        mock_chain.checksum.side_effect = lambda x: x
        adapter = HashnoteAdapter(mock_chain)
        contract = MagicMock()
        contract.functions.canCall.return_value.call.return_value = True
        mock_chain.get_contract.return_value = contract
        adapter.can_transfer(USYC, WALLET_A, WALLET_B)
        first_call = contract.functions.canCall.call_args_list[0]
        # signature is (user, target, functionSig)
        assert first_call.args[2] == bytes.fromhex("a9059cbb")

    def test_is_entitled_unknown_fund_raises(self, mock_chain):
        adapter = HashnoteAdapter(mock_chain)
        with pytest.raises(RegistryError, match="Unknown Hashnote fund"):
            adapter.is_entitled(WALLET_A, "USTB")
