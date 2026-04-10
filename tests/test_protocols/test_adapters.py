"""Tests for all five modernised protocol adapters."""

from unittest.mock import MagicMock, patch

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError
from rwa_sdk.core.models import Category, ComplianceCheck, ComplianceMethod
from rwa_sdk.protocols.backed import BackedAdapter
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.protocols.centrifuge import CentrifugeAdapter
from rwa_sdk.protocols.maple import MapleAdapter
from rwa_sdk.protocols.ondo import OndoAdapter
from rwa_sdk.protocols.securitize import SecuritizeAdapter


@pytest.mark.parametrize(
    "cls,expected_protocol",
    [
        (BackedAdapter, "backed"),
        (SecuritizeAdapter, "securitize"),
        (OndoAdapter, "ondo"),
        (MapleAdapter, "maple"),
        (CentrifugeAdapter, "centrifuge"),
    ],
)
def test_satisfies_protocol_adapter(mock_chain, cls, expected_protocol):
    adapter = cls(mock_chain)
    assert isinstance(adapter, ProtocolAdapter)
    assert adapter.protocol == expected_protocol
    assert adapter.chain_id == 1


class TestBackedAdapter:
    def test_can_transfer_not_sanctioned(self, mock_chain):
        adapter = BackedAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.return_value = False
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert isinstance(result, ComplianceCheck)
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.SANCTIONS

    def test_can_transfer_sender_sanctioned(self, mock_chain):
        adapter = BackedAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.side_effect = [True, False]
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert "sender" in result.restriction_message

    def test_can_transfer_sender_sanctioned_sets_blocking_party(self, mock_chain):
        adapter = BackedAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.side_effect = [True, False]
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.blocking_party == "sender"

    def test_can_transfer_receiver_sanctioned_sets_blocking_party(self, mock_chain):
        adapter = BackedAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.side_effect = [False, True]
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.blocking_party == "receiver"

    def test_can_transfer_clean_has_no_blocking_party(self, mock_chain):
        adapter = BackedAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.return_value = False
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.blocking_party is None

    def test_token_category_is_enum(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        FRESH_TS = FIXED_NOW - 30
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 1000 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "bIB01"
        mock_contract.functions.name.return_value.call.return_value = "Backed IB01"
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            0,
            100 * 10**8,
            0,
            FRESH_TS,
            0,
        )
        mock_chain.get_contract.return_value = mock_contract
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            token = BackedAdapter(mock_chain).bib01()
        assert token.category == Category.BOND_ETF

    def test_all_tokens_returns_list(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        FRESH_TS = FIXED_NOW - 30
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 1000 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "bIB01"
        mock_contract.functions.name.return_value.call.return_value = "Backed IB01"
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            0,
            100 * 10**8,
            0,
            FRESH_TS,
            0,
        )
        mock_chain.get_contract.return_value = mock_contract
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            tokens = BackedAdapter(mock_chain).all_tokens()
        assert len(tokens) == 3
        assert all(t.protocol == "backed" for t in tokens)

    def test_chainlink_stale_raises(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        STALE_TS = FIXED_NOW - 7200
        mock_contract = MagicMock()
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            0,
            100 * 10**8,
            0,
            STALE_TS,
            0,
        )
        mock_chain.get_contract.return_value = mock_contract
        adapter = BackedAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            with pytest.raises(OracleStalenessError) as exc_info:
                adapter._read_chainlink_price("0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5", 8)
        assert exc_info.value.max_age_seconds == 3600

    def test_chainlink_fresh_returns_price(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        FRESH_TS = FIXED_NOW - 30
        answer = 150 * 10**8
        mock_contract = MagicMock()
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            0,
            answer,
            0,
            FRESH_TS,
            0,
        )
        mock_chain.get_contract.return_value = mock_contract
        adapter = BackedAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            price = adapter._read_chainlink_price("0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5", 8)
        assert price == answer / 10**8


class TestSecuritizeAdapter:
    def test_can_transfer_allowed(self, mock_chain):
        adapter = SecuritizeAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.preTransferCheck.return_value.call.return_value = (0, "")
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0x7712c34205737192402172409a8F7ccef8aA2AEc",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            1000,
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.PRE_TRANSFER_CHECK

    def test_can_transfer_blocked(self, mock_chain):
        adapter = SecuritizeAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.preTransferCheck.return_value.call.return_value = (
            1,
            "not registered",
        )
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0x7712c34205737192402172409a8F7ccef8aA2AEc",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            1000,
        )
        assert result.can_transfer is False
        assert result.restriction_code == 1

    def test_list_wallets(self, mock_chain):
        adapter = SecuritizeAdapter(mock_chain)
        mock_contract = MagicMock()
        wallets = [
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        ]
        mock_contract.functions.walletCount.return_value.call.return_value = len(wallets)
        mock_contract.functions.getWalletAt.side_effect = lambda i: MagicMock(
            call=MagicMock(return_value=wallets[i - 1])
        )
        mock_chain.get_contract.return_value = mock_contract

        result = adapter.list_wallets()

        assert result == wallets

    def test_all_tokens_returns_list(self, mock_chain):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 6
        mock_contract.functions.totalSupply.return_value.call.return_value = 1_000_000 * 10**6
        mock_contract.functions.symbol.return_value.call.return_value = "BUIDL"
        mock_contract.functions.name.return_value.call.return_value = "BlackRock BUIDL"
        mock_chain.get_contract.return_value = mock_contract
        tokens = SecuritizeAdapter(mock_chain).all_tokens()
        assert len(tokens) == 2
        assert all(t.protocol == "securitize" for t in tokens)


class TestOndoAdapter:
    def test_can_transfer_usdy_dispatches_by_address(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OndoAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isBlocked.return_value.call.return_value = False
        mock_chain.get_contract.return_value = mock_contract
        usdy_addr = "0x96F6eF951840721AdBF46Ac996b59E0235CB985C"
        result = adapter.can_transfer(
            usdy_addr,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert isinstance(result, ComplianceCheck)
        assert result.method == ComplianceMethod.BLOCKLIST

    def test_can_transfer_ousg_dispatches_by_address(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OndoAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.getKYCStatus.return_value.call.return_value = True
        mock_chain.get_contract.return_value = mock_contract
        ousg_addr = "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92"
        result = adapter.can_transfer(
            ousg_addr,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.method == ComplianceMethod.KYC_REGISTRY

    def test_can_transfer_usdy_blocked(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = OndoAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.isBlocked.return_value.call.side_effect = [True, False]
        mock_chain.get_contract.return_value = mock_contract
        usdy_addr = "0x96F6eF951840721AdBF46Ac996b59E0235CB985C"
        result = adapter.can_transfer(
            usdy_addr,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert "sender" in result.restriction_message

    def test_all_tokens_returns_list(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        FRESH_TS = FIXED_NOW - 30
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 1000 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "USDY"
        mock_contract.functions.name.return_value.call.return_value = "USDY"
        mock_contract.functions.getPriceData.return_value.call.return_value = (
            1_02 * 10**16,
            FRESH_TS,
        )
        mock_contract.functions.getAssetPrice.return_value.call.return_value = 110 * 10**18
        mock_chain.get_contract.return_value = mock_contract
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            tokens = OndoAdapter(mock_chain).all_tokens()
        assert len(tokens) == 4
        assert all(t.protocol == "ondo" for t in tokens)

    def test_usdy_stale_raises(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        mock_contract = MagicMock()
        mock_contract.functions.getPriceData.return_value.call.return_value = (
            1_02 * 10**16,
            FIXED_NOW - 7200,
        )
        mock_chain.get_contract.return_value = mock_contract
        adapter = OndoAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            with pytest.raises(OracleStalenessError) as exc_info:
                adapter._read_usdy_price("0x96F6eF951840721AdBF46Ac996b59E0235CB985C")
        assert exc_info.value.max_age_seconds == 3600

    def test_usdy_fresh_returns_price(self, mock_chain):
        FIXED_NOW = 1_750_000_000
        price_raw = 1_02 * 10**16
        mock_contract = MagicMock()
        mock_contract.functions.getPriceData.return_value.call.return_value = (
            price_raw,
            FIXED_NOW - 30,
        )
        mock_chain.get_contract.return_value = mock_contract
        adapter = OndoAdapter(mock_chain)
        with patch("rwa_sdk.core.oracle.time") as mock_time:
            mock_time.time.return_value = float(FIXED_NOW)
            price = adapter._read_usdy_price("0x96F6eF951840721AdBF46Ac996b59E0235CB985C")
        assert price == price_raw / 10**18


class TestMapleAdapter:
    SYRUP_USDC_POOL = "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"
    SYRUP_USDT_POOL = "0x356B8d89c1e1239Cbbb9dE4815c39A1474d5BA7D"

    def test_can_transfer_bitmap_both_permitted(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = MapleAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.hasPermission.return_value.call.return_value = True
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            self.SYRUP_USDC_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.BITMAP

    def test_can_transfer_bitmap_sender_blocked(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = MapleAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.hasPermission.return_value.call.side_effect = [False, True]
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            self.SYRUP_USDC_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert "sender" in result.restriction_message
        assert result.method == ComplianceMethod.BITMAP

    def test_can_transfer_bitmap_receiver_blocked(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = MapleAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.hasPermission.return_value.call.side_effect = [True, False]
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            self.SYRUP_USDC_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert "receiver" in result.restriction_message
        assert result.method == ComplianceMethod.BITMAP

    def test_can_transfer_none_when_no_pool_manager(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = MapleAdapter(mock_chain)
        result = adapter.can_transfer(
            self.SYRUP_USDT_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_can_transfer_none_for_unknown_token(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = MapleAdapter(mock_chain)
        result = adapter.can_transfer(
            "0x000000000000000000000000000000000000dEaD",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_list_pools_returns_configured_keys(self, mock_chain):
        adapter = MapleAdapter(mock_chain)
        pools = adapter.list_pools()
        assert pools == ["syrup_usdc", "syrup_usdt"]

    def test_all_tokens_returns_list(self, mock_chain):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 6
        mock_contract.functions.totalSupply.return_value.call.return_value = 1_000_000 * 10**6
        mock_contract.functions.totalAssets.return_value.call.return_value = 1_000_000 * 10**6
        mock_contract.functions.convertToAssets.return_value.call.return_value = 1 * 10**6
        mock_contract.functions.symbol.return_value.call.return_value = "syrupUSDC"
        mock_contract.functions.name.return_value.call.return_value = "Maple syrupUSDC"
        mock_chain.get_contract.return_value = mock_contract
        tokens = MapleAdapter(mock_chain).all_tokens()
        assert len(tokens) == 2
        assert all(t.protocol == "maple" for t in tokens)


class TestCentrifugeAdapter:
    def test_can_transfer_restriction_allowed(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = CentrifugeAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.detectTransferRestriction.return_value.call.return_value = 0
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0x8c213ee79581ff4984583c6a801e5263418c4b86",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            100,
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.TRANSFER_RESTRICTION

    def test_can_transfer_restriction_blocked(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = CentrifugeAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.detectTransferRestriction.return_value.call.return_value = 1
        mock_contract.functions.messageForTransferRestriction.return_value.call.return_value = (
            "not member"
        )
        mock_chain.get_contract.return_value = mock_contract
        result = adapter.can_transfer(
            "0x8c213ee79581ff4984583c6a801e5263418c4b86",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            100,
        )
        assert result.can_transfer is False
        assert result.restriction_message == "not member"

    def test_can_transfer_rpc_failure_raises(self, mock_chain):
        mock_chain.checksum.side_effect = lambda x: x
        adapter = CentrifugeAdapter(mock_chain)
        mock_contract = MagicMock()
        mock_contract.functions.detectTransferRestriction.return_value.call.side_effect = (
            RuntimeError("connection refused")
        )
        mock_chain.get_contract.return_value = mock_contract
        with pytest.raises(RuntimeError, match="connection refused"):
            adapter.can_transfer(
                "0x8c213ee79581ff4984583c6a801e5263418c4b86",
                "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
                "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
                100,
            )

    def test_graphql_uses_injected_http(self, mock_chain):
        stub_http = MagicMock()
        stub_http.post_json.return_value = {"data": {"tokens": {"items": []}}}
        adapter = CentrifugeAdapter(mock_chain, http=stub_http)
        adapter._fetch_pool_token_data("JTRSY")
        stub_http.post_json.assert_called_once()

    def test_injectable_api_url(self, mock_chain):
        stub_http = MagicMock()
        stub_http.post_json.return_value = {"data": {"tokens": {"items": []}}}
        adapter = CentrifugeAdapter(
            mock_chain, http=stub_http, api_url="https://staging.centrifuge.io"
        )
        adapter._fetch_pool_token_data("JTRSY")
        assert stub_http.post_json.call_args[0][0] == "https://staging.centrifuge.io"

    def test_all_tokens_returns_list(self, mock_chain):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 500 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "JTRSY"
        mock_contract.functions.name.return_value.call.return_value = (
            "Janus Henderson Anemoy Treasury Fund"
        )
        mock_chain.get_contract.return_value = mock_contract
        stub_http = MagicMock()
        stub_http.post_json.return_value = {"data": {"tokens": {"items": []}}}
        tokens = CentrifugeAdapter(mock_chain, http=stub_http).all_tokens()
        assert len(tokens) == 1
        assert tokens[0].protocol == "centrifuge"

    def test_api_unavailable_returns_token_with_null_price(self, mock_chain):
        """API failure must produce price=None, not crash."""
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 500 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "JTRSY"
        mock_contract.functions.name.return_value.call.return_value = (
            "Janus Henderson Anemoy Treasury Fund"
        )
        mock_chain.get_contract.return_value = mock_contract
        stub_http = MagicMock()
        stub_http.post_json.side_effect = RuntimeError("connection refused")
        token = CentrifugeAdapter(mock_chain, http=stub_http).jtrsy()
        assert token.price is None
        assert token.tvl is None


class TestOndoComplianceRouting:
    """Regression tests for rOUSG/rUSDY compliance routing."""

    def _make_chain(self):
        chain = MagicMock()
        chain.chain_id = 1
        chain.checksum.side_effect = lambda x: x.lower()
        return chain

    def test_rousg_uses_kyc_not_blocklist(self):
        chain = self._make_chain()
        adapter = OndoAdapter(chain)
        kyc_contract = MagicMock()
        kyc_contract.functions.getKYCStatus.return_value.call.return_value = True
        chain.get_contract.return_value = kyc_contract

        rousg_addr = "0x54043c656f0fad0652d9ae2603cdf347c5578d00"  # rOUSG on Ethereum (lowercased)
        result = adapter.can_transfer(rousg_addr, "0xsender", "0xreceiver")
        assert result.method == ComplianceMethod.KYC_REGISTRY

    def test_rusdy_uses_blocklist_not_kyc(self):
        chain = self._make_chain()
        adapter = OndoAdapter(chain)
        blocklist_contract = MagicMock()
        blocklist_contract.functions.isBlocked.return_value.call.return_value = False
        chain.get_contract.return_value = blocklist_contract

        rusdy_addr = "0xaf37c1167910ebc994e266949387d2c7c326b879"  # rUSDY on Ethereum (lowercased)
        result = adapter.can_transfer(rusdy_addr, "0xsender", "0xreceiver")
        assert result.method == ComplianceMethod.BLOCKLIST


class TestAdaptersNamespace:
    """Regression test: _as_list() must not crash on chains with missing adapters."""

    def test_as_list_skips_unsupported_adapters(self):
        from rwa_sdk.protocols import Adapters

        chain = MagicMock()
        chain.chain_id = 42161  # Arbitrum — only Securitize is deployed

        ns = Adapters(chain)
        # Must not raise AttributeError; returns only the adapters that loaded
        adapters = ns._as_list()
        protocols = {a.protocol for a in adapters}
        assert "securitize" in protocols
        assert "ondo" not in protocols
        assert "maple" not in protocols
        assert "centrifuge" not in protocols
        assert "backed" not in protocols


class TestCategoryExport:
    def test_category_importable_from_top_level(self):
        from rwa_sdk import Category

        assert Category.US_TREASURY is not None
        assert Category.PRIVATE_CREDIT is not None
