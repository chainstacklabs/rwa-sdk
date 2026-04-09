"""Address validation utilities."""

from web3 import Web3


def checksum_address(addr: str, param: str = "address") -> str:
    """Validate and return EIP-55 checksummed address.

    Raises:
        ValueError: If addr is not a valid EVM address. The error message includes
            the param name for easier debugging.
    """
    try:
        return Web3.to_checksum_address(addr)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid EVM address for {param!r}: {addr!r}")
