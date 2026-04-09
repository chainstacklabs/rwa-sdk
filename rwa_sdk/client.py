"""Top-level RWAChain client — unified entry point."""

import logging

from rwa_sdk.core.chain import chain_name as _chain_name
from rwa_sdk.core.models import ComplianceCheck, TokenInfo
from rwa_sdk.infra.evm import DefaultEVMChainService
from rwa_sdk.infra.provider import create_rpc_provider
from rwa_sdk.infra.validation import checksum_address
from rwa_sdk.protocols import Adapters
from rwa_sdk.protocols.base import ProtocolAdapter
from rwa_sdk.standards import erc20

_log = logging.getLogger(__name__)


class RWAChain:
    """Read-only SDK for querying RWAChain tokens across EVM chains.

    Usage:
        rwa = RWAChain(rpc_url="https://nd-xxx.chainstack.com/xxx")
        tokens = rwa.all_tokens()
        balance = rwa.balance_of("USDY", "0xYourWallet")

        # Multi-chain: one instance per chain RPC
        eth = RWAChain(rpc_url="https://eth-rpc...")
        arb = RWAChain(rpc_url="https://arb-rpc...")
        all_tokens = eth.all_tokens() + arb.all_tokens()
    """

    def __init__(
        self,
        rpc_url: str,
        adapters: list[ProtocolAdapter] | None = None,
    ):
        w3 = create_rpc_provider(rpc_url)
        self._chain = DefaultEVMChainService(w3)
        if adapters is not None:
            for a in adapters:
                if not isinstance(a, ProtocolAdapter):
                    raise TypeError(
                        f"{a!r} does not satisfy ProtocolAdapter — "
                        "must implement protocol, chain_id, all_tokens(), and can_transfer()"
                    )
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
    def chain_id(self) -> int:
        """EVM chain ID for the connected network (e.g. 1 for Ethereum, 42161 for Arbitrum)."""
        return self._chain.chain_id

    @property
    def chain_name(self) -> str:
        """Human-readable name for the connected chain."""
        return _chain_name(self._chain.chain_id)

    @property
    def loaded_protocols(self) -> list[str]:
        """Protocol names successfully loaded for this chain."""
        return [adapter.protocol for adapter in self._adapters]

    def register_adapter(self, adapter: ProtocolAdapter) -> None:
        """Register a custom protocol adapter."""
        if not isinstance(adapter, ProtocolAdapter):
            raise TypeError(
                f"{adapter!r} does not satisfy ProtocolAdapter — "
                "must implement protocol, chain_id, all_tokens(), and can_transfer()"
            )
        self._adapters.append(adapter)

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all supported tokens across all registered adapters."""
        tokens: list[TokenInfo] = []
        for adapter in self._adapters:
            try:
                tokens.extend(adapter.all_tokens())
            except Exception as e:
                _log.warning("Skipping adapter %r: %s", adapter.protocol, e)
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
        """
        checksum_address(wallet, "wallet")
        token = self._resolve_token(symbol)
        return erc20.read_balance(self._chain, token.address, wallet)

    def can_transfer(
        self, symbol: str, from_addr: str, to_addr: str, value: int = 0
    ) -> ComplianceCheck:
        """Check whether a transfer is permitted for a token, identified by symbol.

        Args:
            symbol: Token symbol, e.g. "USDY". Case-insensitive.
            from_addr: Sender address.
            to_addr: Receiver address.
            value: Transfer amount in raw units (optional, defaults to 0).

        Returns:
            ComplianceCheck with can_transfer and restriction details.

        Raises:
            ValueError: If the symbol is not found.
        """
        token = self._resolve_token(symbol)
        adapter = self._adapter_for_protocol(token.protocol)
        return adapter.can_transfer(token.address, from_addr, to_addr, value)

    def _resolve_token(self, symbol: str) -> TokenInfo:
        upper = symbol.upper()
        for token in self.all_tokens():
            if token.symbol.upper() == upper:
                return token
        raise ValueError(f"Unknown token symbol: {symbol!r}")

    def _adapter_for_protocol(self, protocol: str) -> ProtocolAdapter:
        for adapter in self._adapters:
            if adapter.protocol == protocol:
                return adapter
        raise ValueError(f"No adapter registered for protocol: {protocol!r}")
