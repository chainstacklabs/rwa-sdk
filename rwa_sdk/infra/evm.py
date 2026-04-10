"""EVM chain service — contract factory and address utilities."""

from typing import Protocol, runtime_checkable

from web3 import Web3
from web3.contract import Contract


@runtime_checkable
class EVMChainService(Protocol):
    """Structural interface for EVM chain I/O.

    Adapters depend on this Protocol, not on Web3 directly.
    """

    @property
    def chain_id(self) -> int: ...

    def get_contract(self, address: str, abi: list) -> Contract: ...

    def checksum(self, address: str) -> str: ...


class DefaultEVMChainService:
    """Production implementation backed by a web3.py Web3 instance."""

    def __init__(self, w3: Web3) -> None:
        self._w3 = w3
        self._chain_id: int = w3.eth.chain_id

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def get_contract(self, address: str, abi: list) -> Contract:
        """Instantiate a contract with a checksummed address."""
        return self._w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi,
        )

    def checksum(self, address: str) -> str:
        """Return EIP-55 checksummed address."""
        return Web3.to_checksum_address(address)
