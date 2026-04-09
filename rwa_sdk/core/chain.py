"""EVM chain identifiers and display names."""

from enum import IntEnum


class Chain(IntEnum):
    """Supported EVM chains."""

    ETHEREUM = 1
    ARBITRUM = 42161
    POLYGON = 137
    AVALANCHE = 43114
    BASE = 8453

    @property
    def label(self) -> str:
        """Human-readable chain name, e.g. 'Ethereum'."""
        return self.name.title()


def chain_name(chain_id: int) -> str:
    """Return a human-readable chain name, or 'Chain {id}' for unknown chains."""
    try:
        return Chain(chain_id).label
    except ValueError:
        return f"Chain {chain_id}"
