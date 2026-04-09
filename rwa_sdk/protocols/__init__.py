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
        from rwa_sdk.core.exceptions import RegistryError
        for name, cls in _REGISTRY.items():
            try:
                setattr(self, name, cls(chain))
            except RegistryError:
                pass

    def __getattr__(self, name: str):
        if name in _REGISTRY:
            raise AttributeError(
                f"Adapter '{name}' is not available on this chain — "
                f"it may not be deployed here."
            )
        raise AttributeError(name)

    def _as_list(self) -> list[ProtocolAdapter]:
        return [getattr(self, name) for name in _REGISTRY if name in self.__dict__]


__all__ = ["Adapters", "ProtocolAdapter"]
