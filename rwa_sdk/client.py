"""Top-level RWA client — unified entry point."""

from web3 import Web3

from rwa_sdk.core.models import TokenInfo
from rwa_sdk.core.provider import create_provider
from rwa_sdk.protocols.backed import BackedAdapter
from rwa_sdk.protocols.centrifuge import CentrifugeAdapter
from rwa_sdk.protocols.maple import MapleAdapter
from rwa_sdk.protocols.ondo import OndoAdapter
from rwa_sdk.protocols.securitize import SecuritizeAdapter


class RWA:
    """Read-only SDK for querying RWA tokens across EVM chains.

    Usage:
        rwa = RWA(rpc_url="https://nd-xxx.chainstack.com/xxx")
        token = rwa.ondo.usdy()
        print(token.price, token.tvl)
    """

    def __init__(self, rpc_url: str | None = None, chain_id: int = 1):
        self._w3 = create_provider(rpc_url)
        self._chain_id = chain_id
        self.ondo = OndoAdapter(self._w3, chain_id)
        self.backed = BackedAdapter(self._w3, chain_id)
        self.securitize = SecuritizeAdapter(self._w3, chain_id)
        self.maple = MapleAdapter(self._w3, chain_id)
        self.centrifuge = CentrifugeAdapter(self._w3, chain_id)

    @property
    def w3(self) -> Web3:
        """Access the underlying Web3 instance."""
        return self._w3

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all supported tokens across all protocols."""
        tokens = []
        tokens.extend(self.ondo.all_tokens())
        tokens.extend(self.backed.all_tokens())
        tokens.extend(self.securitize.all_tokens())
        tokens.extend(self.maple.all_tokens())
        tokens.extend(self.centrifuge.all_tokens())
        return tokens
