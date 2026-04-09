"""Backed Finance adapter — bIB01, bCSPX, bNVDA."""

import logging
from dataclasses import dataclass
from typing import ClassVar

from rwa_sdk.core.chain import Chain
from rwa_sdk.core.exceptions import RegistryError
from rwa_sdk.core.models import Category, ComplianceCheck, ComplianceMethod, TokenInfo, YieldType
from rwa_sdk.core.oracle import assert_price_fresh
from rwa_sdk.infra.abi import load_abi
from rwa_sdk.infra.evm import EVMChainService
from rwa_sdk.protocols.base import register
from rwa_sdk.standards.erc20 import read_token_metadata

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackedToken:
    token: str
    category: Category
    chainlink_feed: str | None = None
    feed_decimals: int | None = None
    feed_max_age_seconds: int = 3600


@dataclass(frozen=True)
class BackedConfig:
    tokens: dict[str, BackedToken]
    sanctions_list: str | None = None


@register
class BackedAdapter:
    """Read-only adapter for Backed Finance tokenized securities."""

    protocol = "backed"

    config: ClassVar[dict[Chain, BackedConfig]] = {
        Chain.ETHEREUM: BackedConfig(
            tokens={
                "bib01": BackedToken(
                    token="0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
                    category=Category.BOND_ETF,
                    chainlink_feed="0x32d1463EB53b73C095625719Afa544D5426354cB",
                    feed_decimals=8,
                    feed_max_age_seconds=86400,  # IB01/USD feed has a 24h heartbeat
                ),
                "bcspx": BackedToken(
                    token="0x1e2c4fb7ede391d116e6b41cd0608260e8801d59",
                    category=Category.EQUITY_ETF,
                ),
                "bnvda": BackedToken(
                    token="0xa34c5e0abe843e10461e2c9586ea03e55dbcc495",
                    category=Category.EQUITY,
                ),
            },
            sanctions_list="0x40C57923924B5c5c5455c48D93317139ADDaC8fb",
        ),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = BackedAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError):
            raise RegistryError(f"Backed is not deployed on chain {self._chain_id}")

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def bib01(self) -> TokenInfo:
        """Get bIB01 (Treasury Bond 0-1yr ETF) token info."""
        return self._read_token("bib01")

    def bcspx(self) -> TokenInfo:
        """Get bCSPX (S&P 500 ETF) token info."""
        return self._read_token("bcspx")

    def bnvda(self) -> TokenInfo:
        """Get bNVDA (NVIDIA stock) token info."""
        return self._read_token("bnvda")

    def _read_token(self, token_key: str) -> TokenInfo:
        token = self._config.tokens[token_key]
        meta = read_token_metadata(self._chain, token.token)
        price = None
        price_source = None
        if token.chainlink_feed and token.feed_decimals is not None:
            price = self._read_chainlink_price(token.chainlink_feed, token.feed_decimals, token.feed_max_age_seconds)
            price_source = "Chainlink latestRoundData()"
        else:
            _log.debug("No Chainlink feed configured for %s, price unavailable", token_key)
        tvl = meta["total_supply"] * price if price else None
        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source=price_source,
            tvl=tvl,
            yield_type=YieldType.ACCUMULATING,
            protocol="backed",
            category=token.category,
        )

    def _read_chainlink_price(self, feed_address: str, decimals: int, max_age_seconds: int = 3600) -> float:
        contract = self._chain.get_contract(feed_address, load_abi("chainlink_aggregator"))
        result = contract.functions.latestRoundData().call()
        answer = result[1]
        updated_at = result[3]
        assert_price_fresh(updated_at, max_age_seconds)
        price = answer / (10**decimals)
        _log.debug("Chainlink price fetched for %s: %.6f (updated_at=%d)", feed_address, price, updated_at)
        return price

    def _is_sanctioned(self, address: str) -> bool:
        if not self._config.sanctions_list:
            return False
        contract = self._chain.get_contract(self._config.sanctions_list, load_abi("chainalysis_sanctions"))
        return contract.functions.isSanctioned(self._chain.checksum(address)).call()

    def can_transfer(
        self, _token_address: str, from_addr: str, to_addr: str, _value: int = 0
    ) -> ComplianceCheck:
        from_sanctioned = self._is_sanctioned(from_addr)
        to_sanctioned = self._is_sanctioned(to_addr)
        if from_sanctioned or to_sanctioned:
            who = "sender" if from_sanctioned else "receiver"
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message=f"{who} is sanctioned",
                method=ComplianceMethod.SANCTIONS,
                blocking_party=who,
            )
        return ComplianceCheck(can_transfer=True, method=ComplianceMethod.SANCTIONS)

    def all_tokens(self) -> list[TokenInfo]:
        return [self._read_token(key) for key in self._config.tokens]
