"""Centrifuge adapter — private credit pools, tranche tokens."""

import logging
from dataclasses import dataclass
from typing import ClassVar

from rwa_sdk.core.chain import Chain
from rwa_sdk.core.exceptions import RegistryError
from rwa_sdk.core.models import (
    Category,
    ComplianceCheck,
    ComplianceMethod,
    TokenInfo,
    YieldType,
)
from rwa_sdk.infra.abi import combined_abi, load_abi
from rwa_sdk.infra.evm import EVMChainService
from rwa_sdk.infra.http import DefaultHttpClient, HttpClient
from rwa_sdk.protocols.base import register

_log = logging.getLogger(__name__)

CENTRIFUGE_API = "https://api.centrifuge.io"


@dataclass(frozen=True)
class CentrifugeToken:
    token: str
    pool_id: str
    name: str
    category: Category


@dataclass(frozen=True)
class CentrifugeConfig:
    tokens: dict[str, CentrifugeToken]
    spoke: str | None = None
    vault_registry: str | None = None


@register
class CentrifugeAdapter:
    """Read-only adapter for Centrifuge private credit pools."""

    protocol = "centrifuge"

    config: ClassVar[dict[Chain, CentrifugeConfig]] = {
        Chain.ETHEREUM: CentrifugeConfig(
            tokens={
                "jtrsy": CentrifugeToken(
                    token="0x8c213ee79581ff4984583c6a801e5263418c4b86",
                    pool_id="281474976710662",
                    name="Janus Henderson Anemoy Treasury Fund",
                    category=Category.US_TREASURY,
                ),
            },
            spoke="0xEC3582fcDc34078a4B7a8c75a5a3AE46f48525aB",
            vault_registry="0xd9531AC47928c3386346f82d9A2478960bf2CA7B",
        ),
    }

    def __init__(
        self,
        chain: EVMChainService,
        http: HttpClient | None = None,
        api_url: str = CENTRIFUGE_API,
    ):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = CentrifugeAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError) as err:
            raise RegistryError(f"Centrifuge is not deployed on chain {self._chain_id}") from err
        self._http = http or DefaultHttpClient()
        self._api_url = api_url

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def jtrsy(self) -> TokenInfo:
        """Get JTRSY tranche token info."""
        return self._read_token("jtrsy")

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, value: int = 0
    ) -> ComplianceCheck:
        """Check ERC-1404 transfer restriction on a tranche token."""
        try:
            token_key = self._resolve_token_key(token_address)
        except ValueError:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)
        return self._check_transfer_restriction(from_addr, to_addr, value, token_key)

    def _check_transfer_restriction(
        self, from_addr: str, to_addr: str, value: int, token_key: str = "jtrsy"
    ) -> ComplianceCheck:
        token = self._config.tokens[token_key]
        contract = self._chain.get_contract(
            token.token, combined_abi("erc20", "centrifuge_tranche")
        )

        code = contract.functions.detectTransferRestriction(
            self._chain.checksum(from_addr),
            self._chain.checksum(to_addr),
            value,
        ).call()

        message = ""
        if code != 0:
            message = contract.functions.messageForTransferRestriction(code).call()

        return ComplianceCheck(
            can_transfer=(code == 0),
            restriction_code=code,
            restriction_message=message,
            method=ComplianceMethod.TRANSFER_RESTRICTION,
        )

    def _read_token(self, token_key: str) -> TokenInfo:
        token = self._config.tokens[token_key]

        contract = self._chain.get_contract(token.token, load_abi("erc20"))
        decimals = contract.functions.decimals().call()
        total_supply_raw = contract.functions.totalSupply().call()
        total_supply = total_supply_raw / (10**decimals)
        symbol = contract.functions.symbol().call()
        name = contract.functions.name().call()

        price = None
        tvl = None
        price_source = None

        api_data = self._fetch_pool_token_data(symbol)
        if api_data:
            price = api_data.get("price")
            price_source = "Centrifuge API"
            if price is not None:
                tvl = total_supply * price

        return TokenInfo(
            symbol=symbol,
            name=name,
            address=token.token,
            chain_id=self._chain_id,
            decimals=decimals,
            total_supply=total_supply,
            price=price,
            price_source=price_source,
            tvl=tvl,
            yield_type=YieldType.VAULT,
            protocol="centrifuge",
            category=token.category,
        )

    def _fetch_pool_token_data(self, symbol: str) -> dict | None:
        try:
            query = """
            query($symbol: String!) {
              tokens(where: { symbol: $symbol }, limit: 1) {
                items {
                  symbol
                  tokenPrice
                  totalIssuance
                }
              }
            }
            """
            result = self._graphql_query(query, {"symbol": symbol})
            items = result.get("data", {}).get("tokens", {}).get("items", [])
            if not items:
                return None
            token_price = items[0].get("tokenPrice")
            if token_price:
                return {"price": int(token_price) / 10**18}
            return None
        except Exception as exc:
            _log.warning("Centrifuge API unavailable for %r: %s", symbol, exc)
            return None

    def _graphql_query(self, query: str, variables: dict | None = None) -> dict:
        return self._http.post_json(
            self._api_url,
            {"query": query, "variables": variables or {}},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Origin": "https://app.centrifuge.io",
                "Referer": "https://app.centrifuge.io/",
            },
        )

    def _resolve_token_key(self, token_address: str) -> str:
        checksum = self._chain.checksum(token_address)
        for key, token in self._config.tokens.items():
            if self._chain.checksum(token.token) == checksum:
                return key
        raise ValueError(f"Token address {token_address!r} not found in Centrifuge registry")

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Centrifuge tokens on this chain."""
        return [self._read_token(key) for key in self._config.tokens]
