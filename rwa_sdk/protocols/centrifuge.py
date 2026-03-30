"""Centrifuge adapter — private credit pools, tranche tokens."""

import json
import urllib.request

from web3 import Web3

from rwa_sdk.core.abi import combined_abi, load_abi
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.registry import CENTRIFUGE, ETHEREUM

CENTRIFUGE_API = "https://api.centrifuge.io"

_TOKENS = {
    "jtrsy": {
        "name": "Janus Henderson Anemoy Treasury Fund",
        "category": "us-treasury",
        "pool_id": "281474976710662",
    },
}


class CentrifugeAdapter:
    """Read-only adapter for Centrifuge private credit pools."""

    def __init__(self, w3: Web3, chain_id: int = ETHEREUM):
        self._w3 = w3
        self._chain_id = chain_id
        self._addresses = CENTRIFUGE.get(chain_id, {})

    def jtrsy(self) -> TokenInfo:
        """Get JTRSY tranche token info.

        Uses on-chain ERC-20 reads for supply + GraphQL API for price/NAV
        (price is pushed from hub chain per epoch, API is the reliable source).
        """
        return self._read_token("jtrsy")

    def pool_data(self, pool_id: str = "281474976710662") -> dict:
        """Fetch pool data from Centrifuge GraphQL API."""
        query = """
        query($poolId: String!) {
          pools(where: { id: $poolId }) {
            items {
              id
              name
              currency
              tokens {
                items {
                  symbol
                  totalIssuance
                  tokenPrice
                }
              }
            }
          }
        }
        """
        return self._graphql_query(query, {"poolId": pool_id})

    def check_transfer_restriction(
        self, from_addr: str, to_addr: str, value: int, token_key: str = "jtrsy"
    ) -> ComplianceCheck:
        """Check ERC-1404 transfer restriction on a tranche token."""
        addrs = self._addresses[token_key]
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["token"]),
            abi=combined_abi("erc20", "centrifuge_tranche"),
        )

        try:
            code = contract.functions.detectTransferRestriction(
                Web3.to_checksum_address(from_addr),
                Web3.to_checksum_address(to_addr),
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
        except Exception as e:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=255,
                restriction_message=f"Check failed: {e}",
                method=ComplianceMethod.TRANSFER_RESTRICTION,
            )

    def _read_token(self, token_key: str) -> TokenInfo:
        addrs = self._addresses[token_key]
        meta = _TOKENS[token_key]

        # On-chain ERC-20 reads
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["token"]),
            abi=load_abi("erc20"),
        )
        decimals = contract.functions.decimals().call()
        total_supply_raw = contract.functions.totalSupply().call()
        total_supply = total_supply_raw / (10**decimals)
        symbol = contract.functions.symbol().call()
        name = contract.functions.name().call()

        # Price from API (more reliable than on-chain for Centrifuge)
        price = None
        tvl = None
        price_source = None

        api_data = self._fetch_pool_token_data(symbol)
        if api_data:
            price = api_data.get("price")
            price_source = "Centrifuge API"
            if price:
                tvl = total_supply * price

        return TokenInfo(
            symbol=symbol,
            name=name,
            address=addrs["token"],
            chain_id=self._chain_id,
            decimals=decimals,
            total_supply=total_supply,
            price=price,
            price_source=price_source,
            tvl=tvl,
            yield_type=YieldType.VAULT,
            protocol="centrifuge",
            category=meta["category"],
        )

    def _fetch_pool_token_data(self, symbol: str) -> dict | None:
        """Fetch token price/issuance from GraphQL API."""
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
        except Exception:
            return None

    def _graphql_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query against the Centrifuge API."""
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(
            CENTRIFUGE_API,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "rwa-sdk/0.1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Centrifuge tokens on this chain."""
        tokens = []
        for key in _TOKENS:
            if key in self._addresses:
                tokens.append(self._read_token(key))
        return tokens
