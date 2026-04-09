"""Tests for all five modernised protocol adapters."""

import time
from unittest.mock import MagicMock

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError
from rwa_sdk.core.models import ComplianceCheck, ComplianceMethod
from rwa_sdk.protocols.backed import BackedAdapter
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.protocols.centrifuge import CentrifugeAdapter
from rwa_sdk.protocols.maple import MapleAdapter
from rwa_sdk.protocols.ondo import OndoAdapter
from rwa_sdk.protocols.securitize import SecuritizeAdapter


@pytest.fixture
def w3() -> MagicMock:
    # Not spec'd to Web3: eth.contract is a nested attribute chain that
    # spec'd mocks restrict, making return_value assignments fail.
    return MagicMock()


# ---------------------------------------------------------------------------
# ProtocolAdapter conformance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls,expected_protocol", [
    (BackedAdapter, "backed"),
    (SecuritizeAdapter, "securitize"),
    (OndoAdapter, "ondo"),
    (MapleAdapter, "maple"),
    (CentrifugeAdapter, "centrifuge"),
])
def test_satisfies_protocol_adapter(w3, cls, expected_protocol):
    adapter = cls(w3)
    assert isinstance(adapter, ProtocolAdapter)
    assert adapter.protocol == expected_protocol
    assert adapter.chain_id == 1


# ---------------------------------------------------------------------------
# Backed
# ---------------------------------------------------------------------------

class TestBackedAdapter:
    def test_can_transfer_not_sanctioned(self, w3):
        adapter = BackedAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.return_value = False
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # vitalik.eth
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert isinstance(result, ComplianceCheck)
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.SANCTIONS

    def test_can_transfer_sender_sanctioned(self, w3):
        adapter = BackedAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.isSanctioned.return_value.call.side_effect = [True, False]
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert "sender" in result.restriction_message

    def test_all_tokens_returns_list(self, w3):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 1000 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "bIB01"
        mock_contract.functions.name.return_value.call.return_value = "Backed IB01"
        mock_contract.functions.latestRoundData.return_value.call.return_value = (0, 100 * 10**8, 0, int(time.time()) - 30, 0)
        w3.eth.contract.return_value = mock_contract

        tokens = BackedAdapter(w3).all_tokens()
        assert len(tokens) == 3
        assert all(t.protocol == "backed" for t in tokens)

    def test_chainlink_stale_raises(self, w3):
        feed = "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5"
        mock_contract = MagicMock()
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            0, 100 * 10**8, 0, int(time.time()) - 7200, 0
        )
        w3.eth.contract.return_value = mock_contract

        adapter = BackedAdapter(w3)
        with pytest.raises(OracleStalenessError):
            adapter._read_chainlink_price(feed, 8)

    def test_chainlink_fresh_returns_price(self, w3):
        feed = "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5"
        answer = 150 * 10**8
        decimals = 8
        mock_contract = MagicMock()
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            0, answer, 0, int(time.time()) - 30, 0
        )
        w3.eth.contract.return_value = mock_contract

        adapter = BackedAdapter(w3)
        price = adapter._read_chainlink_price(feed, decimals)
        assert price == answer / 10**decimals


# ---------------------------------------------------------------------------
# Securitize
# ---------------------------------------------------------------------------

class TestSecuritizeAdapter:
    def test_can_transfer_allowed(self, w3):
        adapter = SecuritizeAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.preTransferCheck.return_value.call.return_value = (0, "")
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            "0x7712c34205737192402172409a8F7ccef8aA2AEc",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            1000,
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.PRE_TRANSFER_CHECK

    def test_can_transfer_blocked(self, w3):
        adapter = SecuritizeAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.preTransferCheck.return_value.call.return_value = (1, "not registered")
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            "0x7712c34205737192402172409a8F7ccef8aA2AEc",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            1000,
        )
        assert result.can_transfer is False
        assert result.restriction_code == 1
        assert result.restriction_message == "not registered"

    def test_all_tokens_returns_list(self, w3):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 6
        mock_contract.functions.totalSupply.return_value.call.return_value = 1_000_000 * 10**6
        mock_contract.functions.symbol.return_value.call.return_value = "BUIDL"
        mock_contract.functions.name.return_value.call.return_value = "BlackRock BUIDL"
        w3.eth.contract.return_value = mock_contract

        tokens = SecuritizeAdapter(w3).all_tokens()
        assert len(tokens) == 2
        assert all(t.protocol == "securitize" for t in tokens)


# ---------------------------------------------------------------------------
# Ondo
# ---------------------------------------------------------------------------

class TestOndoAdapter:
    def test_can_transfer_usdy_dispatches_by_address(self, w3):
        adapter = OndoAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.isBlocked.return_value.call.return_value = False
        w3.eth.contract.return_value = mock_contract

        usdy_addr = "0x96F6eF951840721AdBF46Ac996b59E0235CB985C"
        result = adapter.can_transfer(usdy_addr, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B")
        assert isinstance(result, ComplianceCheck)
        assert result.method == ComplianceMethod.BLOCKLIST

    def test_can_transfer_ousg_dispatches_by_address(self, w3):
        adapter = OndoAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.getKYCStatus.return_value.call.return_value = True
        w3.eth.contract.return_value = mock_contract

        ousg_addr = "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92"
        result = adapter.can_transfer(ousg_addr, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B")
        assert result.method == ComplianceMethod.KYC_REGISTRY

    def test_can_transfer_usdy_blocked(self, w3):
        adapter = OndoAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.isBlocked.return_value.call.side_effect = [True, False]
        w3.eth.contract.return_value = mock_contract

        usdy_addr = "0x96F6eF951840721AdBF46Ac996b59E0235CB985C"
        result = adapter.can_transfer(usdy_addr, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B")
        assert result.can_transfer is False
        assert "sender" in result.restriction_message

    def test_all_tokens_returns_list(self, w3):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 1000 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "USDY"
        mock_contract.functions.name.return_value.call.return_value = "USDY"
        mock_contract.functions.getPrice.return_value.call.return_value = 1_02 * 10**16  # $1.02
        mock_contract.functions.getAssetPrice.return_value.call.return_value = 110 * 10**18  # $110
        w3.eth.contract.return_value = mock_contract

        tokens = OndoAdapter(w3).all_tokens()
        # Ethereum mainnet: usdy, ousg, rusdy, rousg
        assert len(tokens) == 4
        assert all(t.protocol == "ondo" for t in tokens)


# ---------------------------------------------------------------------------
# Maple
# ---------------------------------------------------------------------------

class TestMapleAdapter:
    SYRUP_USDC_POOL = "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"
    SYRUP_USDT_POOL = "0x356B8d89c1e1239Cbbb9dE4815c39A1474d5BA7D"

    def test_can_transfer_bitmap_both_permitted(self, w3):
        adapter = MapleAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.hasPermission.return_value.call.return_value = True
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            self.SYRUP_USDC_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.BITMAP

    def test_can_transfer_bitmap_sender_blocked(self, w3):
        adapter = MapleAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.hasPermission.return_value.call.side_effect = [False, True]
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            self.SYRUP_USDC_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert result.restriction_code == 1
        assert "sender" in result.restriction_message
        assert result.method == ComplianceMethod.BITMAP

    def test_can_transfer_bitmap_receiver_blocked(self, w3):
        adapter = MapleAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.hasPermission.return_value.call.side_effect = [True, False]
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            self.SYRUP_USDC_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is False
        assert result.restriction_code == 1
        assert "receiver" in result.restriction_message
        assert result.method == ComplianceMethod.BITMAP

    def test_can_transfer_none_when_no_pool_manager(self, w3):
        """syrup_usdt has no pool_manager entry — falls back to NONE."""
        adapter = MapleAdapter(w3)
        result = adapter.can_transfer(
            self.SYRUP_USDT_POOL,
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_can_transfer_none_for_unknown_token(self, w3):
        adapter = MapleAdapter(w3)
        result = adapter.can_transfer(
            "0x000000000000000000000000000000000000dEaD",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.NONE

    def test_all_tokens_returns_list(self, w3):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 6
        mock_contract.functions.totalSupply.return_value.call.return_value = 1_000_000 * 10**6
        mock_contract.functions.totalAssets.return_value.call.return_value = 1_000_000 * 10**6
        mock_contract.functions.convertToAssets.return_value.call.return_value = 1 * 10**6
        mock_contract.functions.symbol.return_value.call.return_value = "syrupUSDC"
        mock_contract.functions.name.return_value.call.return_value = "Maple syrupUSDC"
        w3.eth.contract.return_value = mock_contract

        tokens = MapleAdapter(w3).all_tokens()
        assert len(tokens) == 2
        assert all(t.protocol == "maple" for t in tokens)


# ---------------------------------------------------------------------------
# Centrifuge
# ---------------------------------------------------------------------------

class TestCentrifugeAdapter:
    def test_injectable_http_client(self, w3):
        stub_http = MagicMock()
        adapter = CentrifugeAdapter(w3, http=stub_http)
        assert adapter._http is stub_http

    def test_can_transfer_restriction_allowed(self, w3):
        adapter = CentrifugeAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.detectTransferRestriction.return_value.call.return_value = 0
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            "0x8c213ee79581ff4984583c6a801e5263418c4b86",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            100,
        )
        assert result.can_transfer is True
        assert result.method == ComplianceMethod.TRANSFER_RESTRICTION

    def test_can_transfer_restriction_blocked(self, w3):
        adapter = CentrifugeAdapter(w3)
        mock_contract = MagicMock()
        mock_contract.functions.detectTransferRestriction.return_value.call.return_value = 1
        mock_contract.functions.messageForTransferRestriction.return_value.call.return_value = "not member"
        w3.eth.contract.return_value = mock_contract

        result = adapter.can_transfer(
            "0x8c213ee79581ff4984583c6a801e5263418c4b86",
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            100,
        )
        assert result.can_transfer is False
        assert result.restriction_message == "not member"

    def test_graphql_uses_injected_http(self, w3):
        stub_http = MagicMock()
        stub_http.post_json.return_value = {"data": {"tokens": {"items": []}}}
        adapter = CentrifugeAdapter(w3, http=stub_http)
        adapter._fetch_pool_token_data("JTRSY")
        stub_http.post_json.assert_called_once()

    def test_injectable_api_url(self, w3):
        stub_http = MagicMock()
        stub_http.post_json.return_value = {"data": {"tokens": {"items": []}}}
        adapter = CentrifugeAdapter(w3, http=stub_http, api_url="https://staging.centrifuge.io")
        adapter._fetch_pool_token_data("JTRSY")
        url_used = stub_http.post_json.call_args[0][0]
        assert url_used == "https://staging.centrifuge.io"

    def test_all_tokens_returns_list(self, w3):
        mock_contract = MagicMock()
        mock_contract.functions.decimals.return_value.call.return_value = 18
        mock_contract.functions.totalSupply.return_value.call.return_value = 500 * 10**18
        mock_contract.functions.symbol.return_value.call.return_value = "JTRSY"
        mock_contract.functions.name.return_value.call.return_value = "Janus Henderson Anemoy Treasury Fund"
        w3.eth.contract.return_value = mock_contract

        stub_http = MagicMock()
        stub_http.post_json.return_value = {"data": {"tokens": {"items": []}}}
        tokens = CentrifugeAdapter(w3, http=stub_http).all_tokens()
        assert len(tokens) == 1
        assert tokens[0].protocol == "centrifuge"
