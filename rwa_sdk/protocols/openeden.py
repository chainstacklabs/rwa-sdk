"""OpenEden adapter — TBILL on Ethereum and Arbitrum."""

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
class OpenEdenToken:
    token: str
    oracle: str
    oracle_decimals: int
    oracle_max_age_seconds: int
    kyc_manager: str
    category: Category | None = None


@dataclass(frozen=True)
class OpenEdenConfig:
    tokens: dict[str, OpenEdenToken]


@register
class OpenEdenAdapter:
    """Read-only adapter for OpenEden tokenized US Treasury Bills.

    TBILL is a 6-decimal ERC-20 with accumulating NAV. Price is sourced from
    a Chainlink-compatible OpenEden oracle (``latestRoundData``, 8-decimal
    answer). Compliance is gated by a KYC Manager contract exposing two
    independent boolean checks per address — ``isKyc`` (allowlist) and
    ``isBanned`` (override block). A transfer is permitted only when both
    sender and receiver are KYC'd and neither is banned.
    """

    protocol = "openeden"

    config: ClassVar[dict[Chain, OpenEdenConfig]] = {
        Chain.ETHEREUM: OpenEdenConfig(
            tokens={
                "tbill": OpenEdenToken(
                    token="0xdd50C053C096CB04A3e3362E2b622529EC5f2e8a",
                    oracle="0xCe9a6626Eb99eaeA829D7fA613d5D0A2eaE45F40",
                    oracle_decimals=8,
                    oracle_max_age_seconds=86400,  # NAV publishes on US business days
                    kyc_manager="0x51Be497AcEd1a2C19f6151064301e356B020D947",
                    category=Category.US_TREASURY,
                ),
            },
        ),
        Chain.ARBITRUM: OpenEdenConfig(
            tokens={
                "tbill": OpenEdenToken(
                    token="0xF84D28A8D28292842dD73D1c5F99476A80b6666A",
                    oracle="0xc0952c8ba068c887B675B4182F3A65420D045F46",
                    oracle_decimals=8,
                    oracle_max_age_seconds=86400,
                    kyc_manager="0x0d7690bAa1008c8d3C5dae9D5033FF846738BAfB",
                    category=Category.US_TREASURY,
                ),
            },
        ),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = OpenEdenAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError) as err:
            raise RegistryError(f"OpenEden is not deployed on chain {self._chain_id}") from err

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def tbill(self) -> TokenInfo:
        """Get TBILL (OpenEden T-Bills) token info."""
        return self._read_token("tbill")

    def tbill_price(self) -> float:
        """Get current TBILL NAV-per-share from the OpenEden oracle."""
        token = self._config.tokens["tbill"]
        return self._read_oracle_price(
            token.oracle, token.oracle_decimals, token.oracle_max_age_seconds
        )

    def is_allowed(self, address: str, fund_key: str) -> bool:
        """Check whether an address may hold/receive an OpenEden fund.

        True iff the address is KYC'd and not banned.

        Args:
            address: Wallet to check.
            fund_key: Token key (e.g. ``"tbill"``). Case-insensitive.

        Raises:
            RegistryError: If ``fund_key`` is not an OpenEden token on this chain.
        """
        key = fund_key.lower()
        if key not in self._config.tokens:
            raise RegistryError(f"Unknown OpenEden fund key {fund_key!r} on chain {self._chain_id}")
        kc = self._kyc_contract(key)
        checksum = self._chain.checksum(address)
        return kc.functions.isKyc(checksum).call() and not kc.functions.isBanned(checksum).call()

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, _value: int = 0
    ) -> ComplianceCheck:
        """Check transfer eligibility via the OpenEden KYC Manager."""
        try:
            token_key = self._resolve_token_key(token_address)
        except ValueError:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)
        sender_block = self._check_party(from_addr, token_key)
        if sender_block:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message=f"sender {sender_block}",
                method=ComplianceMethod.KYC_REGISTRY,
                blocking_party="sender",
            )
        receiver_block = self._check_party(to_addr, token_key)
        if receiver_block:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message=f"receiver {receiver_block}",
                method=ComplianceMethod.KYC_REGISTRY,
                blocking_party="receiver",
            )
        return ComplianceCheck(can_transfer=True, method=ComplianceMethod.KYC_REGISTRY)

    def all_tokens(self) -> list[TokenInfo]:
        return [self._read_token(key) for key in self._config.tokens]

    def _check_party(self, address: str, token_key: str) -> str | None:
        kc = self._kyc_contract(token_key)
        checksum = self._chain.checksum(address)
        if kc.functions.isBanned(checksum).call():
            return "is banned by OpenEden"
        if not kc.functions.isKyc(checksum).call():
            return "is not KYC'd by OpenEden"
        return None

    def _kyc_contract(self, token_key: str):
        token = self._config.tokens[token_key]
        return self._chain.get_contract(token.kyc_manager, load_abi("openeden_kyc_manager"))

    def _read_token(self, key: str) -> TokenInfo:
        token = self._config.tokens[key]
        meta = read_token_metadata(self._chain, token.token)
        price = self._read_oracle_price(
            token.oracle, token.oracle_decimals, token.oracle_max_age_seconds
        )
        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source="OpenEden TBILL price oracle (Chainlink-compatible)",
            tvl=meta["total_supply"] * price,
            yield_type=YieldType.ACCUMULATING,
            protocol="openeden",
            category=token.category,
        )

    def _read_oracle_price(self, feed_address: str, decimals: int, max_age_seconds: int) -> float:
        contract = self._chain.get_contract(feed_address, load_abi("chainlink_aggregator"))
        result = contract.functions.latestRoundData().call()
        answer = result[1]
        updated_at = result[3]
        assert_price_fresh(updated_at, max_age_seconds)
        price = answer / (10**decimals)
        _log.debug(
            "OpenEden price fetched for %s: %.8f (updated_at=%d)", feed_address, price, updated_at
        )
        return price

    def _resolve_token_key(self, token_address: str) -> str:
        checksum = self._chain.checksum(token_address)
        for key, token in self._config.tokens.items():
            if self._chain.checksum(token.token) == checksum:
                return key
        raise ValueError(f"Token address {token_address!r} not found in OpenEden registry")
