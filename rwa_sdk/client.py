"""Top-level RWA client — unified entry point."""

from web3 import Web3

from rwa_sdk.core.models import TokenInfo
from rwa_sdk.core.provider import create_provider
from rwa_sdk.protocols.backed import BackedAdapter
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.protocols.centrifuge import CentrifugeAdapter
from rwa_sdk.protocols.maple import MapleAdapter
from rwa_sdk.protocols.ondo import OndoAdapter
from rwa_sdk.protocols.securitize import SecuritizeAdapter
from rwa_sdk.standards import erc20


class RWA:
    """Read-only SDK for querying RWA tokens across EVM chains.

    Usage:
        rwa = RWA(rpc_url="https://nd-xxx.chainstack.com/xxx")
        token = rwa.ondo.all_tokens()[0]
        print(token.price, token.tvl)
        balance = rwa.balance_of("USDY", "0xYourWallet")
    """

    def __init__(self, rpc_url: str | None = None, chain_id: int = 1):
        self._w3 = create_provider(rpc_url)
        self._chain_id = chain_id
        self._adapters: list[ProtocolAdapter] = [
            OndoAdapter(self._w3, chain_id),
            BackedAdapter(self._w3, chain_id),
            SecuritizeAdapter(self._w3, chain_id),
            MapleAdapter(self._w3, chain_id),
            CentrifugeAdapter(self._w3, chain_id),
        ]

    # ------------------------------------------------------------------
    # Backwards-compatible named accessors
    # ------------------------------------------------------------------

    @property
    def ondo(self) -> ProtocolAdapter:
        return self._adapter_by_protocol("ondo")

    @property
    def backed(self) -> ProtocolAdapter:
        return self._adapter_by_protocol("backed")

    @property
    def securitize(self) -> ProtocolAdapter:
        return self._adapter_by_protocol("securitize")

    @property
    def maple(self) -> ProtocolAdapter:
        return self._adapter_by_protocol("maple")

    @property
    def centrifuge(self) -> ProtocolAdapter:
        return self._adapter_by_protocol("centrifuge")

    @property
    def w3(self) -> Web3:
        """Access the underlying Web3 instance."""
        return self._w3

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all supported tokens across all registered adapters."""
        tokens: list[TokenInfo] = []
        for adapter in self._adapters:
            tokens.extend(adapter.all_tokens())
        return tokens

    def register_adapter(self, adapter: ProtocolAdapter) -> None:
        """Register a custom protocol adapter."""
        if not isinstance(adapter, ProtocolAdapter):
            raise TypeError(f"Expected ProtocolAdapter, got {type(adapter).__name__!r}")
        self._adapters.append(adapter)

    def balance_of(self, symbol: str, wallet: str) -> float:
        """Get token balance for a wallet, identified by symbol.

        Args:
            symbol: Token symbol, e.g. "USDY". Case-insensitive.
            wallet: Wallet address to query.

        Returns:
            Human-readable float balance (raw amount divided by 10^decimals).

        Raises:
            ValueError: If the symbol is not found across registered adapters.

        Note:
            Each call resolves the token address by querying all adapters. For
            protocols with on-chain or HTTP lookups in all_tokens(), this incurs
            one network round-trip per adapter per call.
        """
        address = self._resolve_token_address(symbol)
        return erc20.read_balance(self._w3, address, wallet)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _adapter_by_protocol(self, protocol: str) -> ProtocolAdapter:
        for adapter in self._adapters:
            if adapter.protocol == protocol:
                return adapter
        raise ValueError(f"No adapter registered for protocol: {protocol!r}")

    def _resolve_token_address(self, symbol: str) -> str:
        upper = symbol.upper()
        for token in self.all_tokens():
            if token.symbol.upper() == upper:
                return token.address
        raise ValueError(f"Unknown token symbol: {symbol!r}")
