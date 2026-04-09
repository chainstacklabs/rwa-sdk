"""Protocol definition for RWA protocol adapters."""

from typing import Protocol, runtime_checkable

from rwa_sdk.core.models import ComplianceCheck, TokenInfo

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Register an adapter class in the global adapter registry."""
    _REGISTRY[cls.protocol] = cls  # type: ignore[attr-defined]
    return cls


@runtime_checkable
class ProtocolAdapter(Protocol):
    """Structural protocol all adapters must satisfy.

    Adapters do not need to inherit from this class. Any class that implements
    the required methods and properties satisfies the protocol at runtime.
    """

    @property
    def protocol(self) -> str:
        """Short protocol identifier, e.g. 'ondo', 'backed'."""
        ...

    @property
    def chain_id(self) -> int:
        """EVM chain ID this adapter is configured for."""
        ...

    def all_tokens(self) -> list[TokenInfo]:
        """Return normalised TokenInfo for every token this adapter supports."""
        ...

    def can_transfer(
        self,
        token_address: str,
        from_addr: str,
        to_addr: str,
        value: int = 0,
    ) -> ComplianceCheck:
        """Check whether a transfer is permitted under this protocol's compliance model."""
        ...
