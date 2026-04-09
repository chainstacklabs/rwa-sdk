"""Top-level RWA client — unified entry point."""

from rwa_sdk.core.chain import chain_name as _chain_name
from rwa_sdk.core.models import TokenInfo
from rwa_sdk.infra.evm import DefaultEVMChainService, EVMChainService
from rwa_sdk.infra.provider import create_rpc_provider
from rwa_sdk.infra.validation import checksum_address
from rwa_sdk.protocols import Adapters
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.standards import erc20


class RWA:
    """Read-only SDK for querying RWA tokens across EVM chains.

    Usage:
        rwa = RWA(rpc_url="https://nd-xxx.chainstack.com/xxx")
        tokens = rwa.all_tokens()
        balance = rwa.balance_of("USDY", "0xYourWallet")

        # Multi-chain: one instance per chain RPC
        eth = RWA(rpc_url="https://eth-rpc...")
        arb = RWA(rpc_url="https://arb-rpc...")
        all_tokens = eth.all_tokens() + arb.all_tokens()
    """

    def __init__(
        self,
        rpc_url: str | None = None,
        adapters: list[ProtocolAdapter] | None = None,
    ):
        w3 = create_rpc_provider(rpc_url)
        self._chain = DefaultEVMChainService(w3)
        if adapters is not None:
            self._adapters: list[ProtocolAdapter] = list(adapters)
            self._ns: Adapters | None = None
        else:
            self._ns = Adapters(self._chain)
            self._adapters = self._ns._as_list()

    @property
    def adapters(self) -> Adapters:
        """Typed namespace for direct access to each protocol adapter."""
        if self._ns is None:
            raise RuntimeError("adapters namespace is not available when custom adapters are injected")
        return self._ns

    @property
    def chain_name(self) -> str:
        """Human-readable name for the connected chain."""
        return _chain_name(self._chain.chain_id)

    @property
    def chain(self) -> EVMChainService:
        """Access the underlying EVM chain service."""
        return self._chain

    def register_adapter(self, adapter: ProtocolAdapter) -> None:
        """Register a custom protocol adapter."""
        self._adapters.append(adapter)

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all supported tokens across all registered adapters."""
        tokens: list[TokenInfo] = []
        for adapter in self._adapters:
            tokens.extend(adapter.all_tokens())
        return tokens

    def balance_of(self, symbol: str, wallet: str) -> float:
        """Get token balance for a wallet, identified by symbol.

        Args:
            symbol: Token symbol, e.g. "USDY". Case-insensitive.
            wallet: Wallet address to query.

        Returns:
            Human-readable float balance (raw amount divided by 10^decimals).

        Raises:
            ValueError: If the symbol is not found or wallet address is invalid.

        Note:
            Each call resolves the token address by querying all adapters. For
            protocols with on-chain or HTTP lookups in all_tokens(), this incurs
            one network round-trip per adapter per call.
        """
        checksum_address(wallet, "wallet")
        address = self._resolve_token_address(symbol)
        return erc20.read_balance(self._chain, address, wallet)

    # --- Internal helpers ---

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
