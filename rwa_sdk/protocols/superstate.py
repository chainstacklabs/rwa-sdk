"""Superstate adapter — USTB, USCC."""

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
class SuperstateToken:
    token: str
    fund_symbol: str  # AllowlistV3 lookup key, e.g. "USTB" or "USCC"
    chainlink_feed: str
    feed_decimals: int
    feed_max_age_seconds: int
    category: Category | None = None


@dataclass(frozen=True)
class SuperstateConfig:
    tokens: dict[str, SuperstateToken]
    allowlist: str


@register
class SuperstateAdapter:
    """Read-only adapter for Superstate tokenized funds."""

    protocol = "superstate"

    config: ClassVar[dict[Chain, SuperstateConfig]] = {
        Chain.ETHEREUM: SuperstateConfig(
            tokens={
                "ustb": SuperstateToken(
                    token="0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e",
                    fund_symbol="USTB",
                    chainlink_feed="0x289B5036cd942e619E1Ee48670F98d214E745AAC",
                    feed_decimals=6,
                    feed_max_age_seconds=86400,  # NAV-per-share publishes ~daily
                    category=Category.US_TREASURY,
                ),
                "uscc": SuperstateToken(
                    token="0x14d60E7FDC0D71d8611742720E4C50E7a974020c",
                    fund_symbol="USCC",
                    chainlink_feed="0xAfFd8F5578E8590665de561bdE9E7BAdb99300d9",
                    feed_decimals=6,
                    feed_max_age_seconds=86400,
                    # No existing Category fits crypto-basis carry; leave None.
                    category=None,
                ),
            },
            allowlist="0x02f1fA8B196d21c7b733eb2700b825611d8A38E5",
        ),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = SuperstateAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError) as err:
            raise RegistryError(f"Superstate is not deployed on chain {self._chain_id}") from err

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def ustb(self) -> TokenInfo:
        """Get USTB (Short Duration US Government Securities Fund) token info."""
        return self._read_token("ustb")

    def ustb_price(self) -> float:
        """Get current USTB NAV-per-share from the Chainlink oracle."""
        token = self._config.tokens["ustb"]
        return self._read_chainlink_price(
            token.chainlink_feed, token.feed_decimals, token.feed_max_age_seconds
        )

    def uscc(self) -> TokenInfo:
        """Get USCC (Crypto Carry Fund) token info."""
        return self._read_token("uscc")

    def uscc_price(self) -> float:
        """Get current USCC NAV-per-share from the Chainlink oracle."""
        token = self._config.tokens["uscc"]
        return self._read_chainlink_price(
            token.chainlink_feed, token.feed_decimals, token.feed_max_age_seconds
        )

    def is_allowed(self, address: str, fund_key: str) -> bool:
        """Check whether an address is allow-listed for a Superstate fund.

        Args:
            address: Wallet to check.
            fund_key: Token key (e.g. "ustb" or "uscc"). Case-insensitive.

        Raises:
            RegistryError: If ``fund_key`` is not a Superstate token on this chain.
        """
        key = fund_key.lower()
        if key not in self._config.tokens:
            raise RegistryError(
                f"Unknown Superstate fund key {fund_key!r} on chain {self._chain_id}"
            )
        fund_symbol = self._config.tokens[key].fund_symbol
        contract = self._chain.get_contract(
            self._config.allowlist, load_abi("superstate_allowlist")
        )
        return contract.functions.isAddressAllowedForPrivateInstrument(
            self._chain.checksum(address), fund_symbol
        ).call()

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, _value: int = 0
    ) -> ComplianceCheck:
        """Check transfer eligibility via the Superstate AllowlistV3."""
        try:
            token_key = self._resolve_token_key(token_address)
        except ValueError:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)
        if not self.is_allowed(from_addr, token_key):
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="sender is not on the Superstate allowlist",
                method=ComplianceMethod.KYC_REGISTRY,
                blocking_party="sender",
            )
        if not self.is_allowed(to_addr, token_key):
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="receiver is not on the Superstate allowlist",
                method=ComplianceMethod.KYC_REGISTRY,
                blocking_party="receiver",
            )
        return ComplianceCheck(can_transfer=True, method=ComplianceMethod.KYC_REGISTRY)

    def all_tokens(self) -> list[TokenInfo]:
        return [self._read_token(key) for key in self._config.tokens]

    def _read_token(self, key: str) -> TokenInfo:
        token = self._config.tokens[key]
        meta = read_token_metadata(self._chain, token.token)
        price = self._read_chainlink_price(
            token.chainlink_feed, token.feed_decimals, token.feed_max_age_seconds
        )
        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source="Chainlink latestRoundData()",
            tvl=meta["total_supply"] * price,
            yield_type=YieldType.ACCUMULATING,
            protocol="superstate",
            category=token.category,
        )

    def _read_chainlink_price(
        self, feed_address: str, decimals: int, max_age_seconds: int
    ) -> float:
        contract = self._chain.get_contract(feed_address, load_abi("chainlink_aggregator"))
        result = contract.functions.latestRoundData().call()
        answer = result[1]
        updated_at = result[3]
        assert_price_fresh(updated_at, max_age_seconds)
        price = answer / (10**decimals)
        _log.debug(
            "Superstate price fetched for %s: %.6f (updated_at=%d)", feed_address, price, updated_at
        )
        return price

    def _resolve_token_key(self, token_address: str) -> str:
        checksum = self._chain.checksum(token_address)
        for key, token in self._config.tokens.items():
            if self._chain.checksum(token.token) == checksum:
                return key
        raise ValueError(f"Token address {token_address!r} not found in Superstate registry")
