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
        self, _token_address: str, _from_addr: str, _to_addr: str, _value: int = 0
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


