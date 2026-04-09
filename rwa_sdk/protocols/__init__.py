"""RWA protocol adapters."""

from rwa_sdk.infra.evm import EVMChainService
from rwa_sdk.protocols.backed import BackedAdapter
from rwa_sdk.protocols.base import ProtocolAdapter, _REGISTRY
from rwa_sdk.protocols.centrifuge import CentrifugeAdapter
from rwa_sdk.protocols.maple import MapleAdapter
from rwa_sdk.protocols.ondo import OndoAdapter
from rwa_sdk.protocols.securitize import SecuritizeAdapter


class Adapters:
    """Typed namespace providing direct access to each protocol adapter."""

    ondo: OndoAdapter
    backed: BackedAdapter
    securitize: SecuritizeAdapter
    maple: MapleAdapter
    centrifuge: CentrifugeAdapter

    def __init__(self, chain: EVMChainService) -> None:
        for name, cls in _REGISTRY.items():
            setattr(self, name, cls(chain))

    def _as_list(self) -> list[ProtocolAdapter]:
        return [getattr(self, name) for name in _REGISTRY]


__all__ = ["Adapters", "ProtocolAdapter"]
