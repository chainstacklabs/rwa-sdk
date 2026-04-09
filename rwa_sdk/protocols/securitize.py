"""Securitize adapter — BlackRock BUIDL."""

import logging
from dataclasses import dataclass
from typing import ClassVar

from rwa_sdk.core.chain import Chain
from rwa_sdk.core.exceptions import RegistryError
from rwa_sdk.core.models import ComplianceCheck, ComplianceMethod, TokenInfo, YieldType
from rwa_sdk.infra.abi import combined_abi
from rwa_sdk.infra.evm import EVMChainService
from rwa_sdk.protocols.base import register

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecuritizeToken:
    token: str
    name: str
    category: str


@dataclass(frozen=True)
class SecuritizeConfig:
    tokens: dict[str, SecuritizeToken]


@register
class SecuritizeAdapter:
    """Read-only adapter for Securitize DS Protocol tokens (BlackRock BUIDL)."""

    protocol = "securitize"

    config: ClassVar[dict[Chain, SecuritizeConfig]] = {
        Chain.ETHEREUM: SecuritizeConfig(tokens={
            "buidl": SecuritizeToken(token="0x7712c34205737192402172409a8F7ccef8aA2AEc", name="BlackRock BUIDL", category="us-treasury"),
            "buidl_i": SecuritizeToken(token="0x6a9DA2D710BB9B700acde7Cb81F10F1fF8C89041", name="BlackRock BUIDL-I", category="us-treasury"),
        }),
        Chain.ARBITRUM: SecuritizeConfig(tokens={
            "buidl": SecuritizeToken(token="0xA6525Ae43eDCd03dC08E775774dCAbd3bb925872", name="BlackRock BUIDL", category="us-treasury"),
        }),
        Chain.AVALANCHE: SecuritizeConfig(tokens={
            "buidl": SecuritizeToken(token="0x53FC82f14F009009b440a706e31c9021E1196A2F", name="BlackRock BUIDL", category="us-treasury"),
        }),
        Chain.POLYGON: SecuritizeConfig(tokens={
            "buidl": SecuritizeToken(token="0x2893Ef551B6dD69F661Ac00F11D93E5Dc5Dc0e99", name="BlackRock BUIDL", category="us-treasury"),
        }),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = SecuritizeAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError):
            raise RegistryError(f"Securitize is not deployed on chain {self._chain_id}")

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def buidl(self) -> TokenInfo:
        return self._read_token("buidl")

    def buidl_i(self) -> TokenInfo:
        return self._read_token("buidl_i")

    def wallet_count(self, token_key: str = "buidl") -> int:
        return self._get_contract(token_key).functions.walletCount().call()

    def get_wallet_at(self, index: int, token_key: str = "buidl") -> str:
        return self._get_contract(token_key).functions.getWalletAt(index).call()

    def can_transfer(self, token_address: str, from_addr: str, to_addr: str, value: int = 0) -> ComplianceCheck:
        token_key = self._resolve_token_key(token_address)
        return self._pre_transfer_check(from_addr, to_addr, value, token_key)

    def _pre_transfer_check(self, from_addr: str, to_addr: str, value: int, token_key: str = "buidl") -> ComplianceCheck:
        contract = self._get_contract(token_key)
        code, reason = contract.functions.preTransferCheck(
            self._chain.checksum(from_addr),
            self._chain.checksum(to_addr),
            value,
        ).call()
        _log.debug("BUIDL preTransferCheck: code=%d reason=%s", code, reason)
        return ComplianceCheck(can_transfer=(code == 0), restriction_code=code, restriction_message=reason, method=ComplianceMethod.PRE_TRANSFER_CHECK)

    def get_ds_service(self, service_id: int, token_key: str = "buidl") -> str:
        return self._get_contract(token_key).functions.getDSService(service_id).call()

    def _read_token(self, token_key: str) -> TokenInfo:
        token = self._config.tokens[token_key]
        contract = self._get_contract(token_key)
        decimals = contract.functions.decimals().call()
        total_supply_raw = contract.functions.totalSupply().call()
        total_supply = total_supply_raw / (10**decimals)
        return TokenInfo(
            symbol=contract.functions.symbol().call(),
            name=contract.functions.name().call(),
            address=token.token,
            chain_id=self._chain_id,
            decimals=decimals,
            total_supply=total_supply,
            price=1.0,
            price_source="constant NAV ($1.00, yield via dividend mint)",
            tvl=total_supply,
            yield_type=YieldType.DIVIDEND_MINT,
            protocol="securitize",
            category=token.category,
        )

    def _get_contract(self, token_key: str):
        token = self._config.tokens[token_key]
        return self._chain.get_contract(token.token, combined_abi("erc20", "securitize_token"))

    def _resolve_token_key(self, token_address: str) -> str:
        checksum = self._chain.checksum(token_address)
        for key, token in self._config.tokens.items():
            if self._chain.checksum(token.token) == checksum:
                return key
        raise ValueError(f"Token address {token_address!r} not found in Securitize registry")

    def all_tokens(self) -> list[TokenInfo]:
        return [self._read_token(key) for key in self._config.tokens]
