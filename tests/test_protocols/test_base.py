"""Tests for protocols/base.py."""

from rwa_sdk.core.models import ComplianceCheck, ComplianceMethod, TokenInfo
from rwa_sdk.protocols.base import ProtocolAdapter


class _ConformingAdapter:
    """Minimal stub that satisfies ProtocolAdapter structurally."""

    @property
    def protocol(self) -> str:
        return "stub"

    @property
    def chain_id(self) -> int:
        return 1

    def all_tokens(self) -> list[TokenInfo]:
        return []

    def can_transfer(
        self, _token_address: str, _from_addr: str, _to_addr: str
    ) -> ComplianceCheck:
        return ComplianceCheck(
            can_transfer=True,
            restriction_code=0,
            restriction_message="",
            method=ComplianceMethod.NONE,
        )


class _NonConformingAdapter:
    """Missing all required methods — should NOT satisfy the Protocol."""
    pass


def test_conforming_adapter_satisfies_protocol():
    adapter = _ConformingAdapter()
    assert isinstance(adapter, ProtocolAdapter)


def test_non_conforming_adapter_fails_protocol():
    adapter = _NonConformingAdapter()
    assert not isinstance(adapter, ProtocolAdapter)


def test_protocol_is_exported_from_protocols_package():
    from rwa_sdk.protocols import ProtocolAdapter as PA
    assert PA is ProtocolAdapter


def test_adapter_all_tokens_returns_list():
    adapter = _ConformingAdapter()
    result = adapter.all_tokens()
    assert isinstance(result, list)


def test_adapter_can_transfer_returns_compliance_check():
    adapter = _ConformingAdapter()
    result = adapter.can_transfer("0xABC", "0xSENDER", "0xRECEIVER")
    assert isinstance(result, ComplianceCheck)
    assert result.can_transfer is True
