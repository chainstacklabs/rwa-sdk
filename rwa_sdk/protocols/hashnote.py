"""Hashnote adapter — USYC."""

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

# ERC-20 ``transfer(address,uint256)`` selector — passed to Hashnote's
# Entitlements (a Solmate RolesAuthority) to check whether a wallet is
# permitted to call ``transfer`` on the USYC contract.
_TRANSFER_SELECTOR = bytes.fromhex("a9059cbb")


@dataclass(frozen=True)
class HashnoteToken:
    token: str
    oracle: str
    oracle_decimals: int
    oracle_max_age_seconds: int
    entitlements: str
    category: Category | None = None


@dataclass(frozen=True)
class HashnoteConfig:
    tokens: dict[str, HashnoteToken]


@register
class HashnoteAdapter:
    """Read-only adapter for Hashnote tokenized funds.

    Hashnote's compliance is enforced by an Entitlements contract — a Solmate
    ``RolesAuthority`` that gates calls to USYC's ``transfer`` via
    ``canCall(user, target, functionSig)``. Functionally an allowlist of
    KYC'd holders, so transfer eligibility is surfaced as
    ``ComplianceMethod.KYC_REGISTRY``; the underlying mechanism differs from
    Superstate/Ondo's per-fund registries and is a candidate for a more
    specific enum value in a future schema sweep.
    """

    protocol = "hashnote"

    config: ClassVar[dict[Chain, HashnoteConfig]] = {
        Chain.ETHEREUM: HashnoteConfig(
            tokens={
                "usyc": HashnoteToken(
                    token="0x136471a34F6ef19fE571EFFC1CA711fdb8E49f2b",
                    # Hashnote's USYC oracle exposes the Chainlink aggregator
                    # interface (latestRoundData with 18-decimal answer);
                    # NAV is pushed once per business day.
                    oracle="0x74f2199AEb743f68f05943e5715A33EaF2b61f53",
                    oracle_decimals=18,
                    oracle_max_age_seconds=86400,
                    entitlements="0x902D906b8d988092213bE799B18Bd2cbd64F808C",
                    category=Category.US_TREASURY,
                ),
            },
        ),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = HashnoteAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError) as err:
            raise RegistryError(f"Hashnote is not deployed on chain {self._chain_id}") from err

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def usyc(self) -> TokenInfo:
        """Get USYC (US Yield Coin) token info."""
        return self._read_token("usyc")

    def usyc_price(self) -> float:
        """Get current USYC NAV-per-share from the Hashnote oracle."""
        token = self._config.tokens["usyc"]
        return self._read_oracle_price(
            token.oracle, token.oracle_decimals, token.oracle_max_age_seconds
        )

    def is_entitled(self, address: str, fund_key: str) -> bool:
        """Check whether an address is authorised by Hashnote Entitlements to transfer a fund.

        Args:
            address: Wallet to check.
            fund_key: Token key (e.g. ``"usyc"``). Case-insensitive.

        Raises:
            RegistryError: If ``fund_key`` is not a Hashnote token on this chain.
        """
        key = fund_key.lower()
        if key not in self._config.tokens:
            raise RegistryError(f"Unknown Hashnote fund key {fund_key!r} on chain {self._chain_id}")
        token = self._config.tokens[key]
        contract = self._chain.get_contract(token.entitlements, load_abi("hashnote_entitlements"))
        return contract.functions.canCall(
            self._chain.checksum(address),
            self._chain.checksum(token.token),
            _TRANSFER_SELECTOR,
        ).call()

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, _value: int = 0
    ) -> ComplianceCheck:
        """Check transfer eligibility via the Hashnote Entitlements authority."""
        try:
            token_key = self._resolve_token_key(token_address)
        except ValueError:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)
        if not self.is_entitled(from_addr, token_key):
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="sender is not entitled by Hashnote to transfer",
                method=ComplianceMethod.KYC_REGISTRY,
                blocking_party="sender",
            )
        if not self.is_entitled(to_addr, token_key):
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="receiver is not entitled by Hashnote to transfer",
                method=ComplianceMethod.KYC_REGISTRY,
                blocking_party="receiver",
            )
        return ComplianceCheck(can_transfer=True, method=ComplianceMethod.KYC_REGISTRY)

    def all_tokens(self) -> list[TokenInfo]:
        return [self._read_token(key) for key in self._config.tokens]

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
            price_source="Hashnote USYC oracle (Chainlink-compatible)",
            tvl=meta["total_supply"] * price,
            yield_type=YieldType.ACCUMULATING,
            protocol="hashnote",
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
            "Hashnote price fetched for %s: %.6f (updated_at=%d)", feed_address, price, updated_at
        )
        return price

    def _resolve_token_key(self, token_address: str) -> str:
        checksum = self._chain.checksum(token_address)
        for key, token in self._config.tokens.items():
            if self._chain.checksum(token.token) == checksum:
                return key
        raise ValueError(f"Token address {token_address!r} not found in Hashnote registry")
