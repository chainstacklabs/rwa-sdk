"""Ondo Finance adapter — USDY, OUSG, rUSDY, rOUSG."""

import logging
from dataclasses import dataclass
from typing import ClassVar

from rwa_sdk.infra.abi import combined_abi, load_abi
from rwa_sdk.core.chain import Chain
from rwa_sdk.core.exceptions import RegistryError
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.oracle import assert_price_fresh
from rwa_sdk.infra.evm import EVMChainService
from rwa_sdk.protocols.base import register
from rwa_sdk.standards.erc20 import read_token_metadata

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OndoToken:
    token: str
    oracle: str | None = None
    blocklist: str | None = None
    kyc_registry: str | None = None


@dataclass(frozen=True)
class OndoConfig:
    tokens: dict[str, OndoToken]


@register
class OndoAdapter:
    """Read-only adapter for Ondo Finance RWA tokens."""

    protocol = "ondo"

    config: ClassVar[dict[Chain, OndoConfig]] = {
        Chain.ETHEREUM: OndoConfig(tokens={
            "usdy": OndoToken(
                token="0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
                oracle="0xA0219AA5B31e65Bc920B5b6DFb8EdF0988121De0",
                blocklist="0xd8c8174691d936E2C80114EC449037b13421B0a8",
            ),
            "rusdy": OndoToken(token="0xaf37c1167910ebC994e266949387d2c7C326b879"),
            "ousg": OndoToken(
                token="0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92",
                oracle="0x9Cad45a8BF0Ed41Ff33074449B357C7a1fAb4094",
                kyc_registry="0xcf6958D69d535FD03BD6Df3F4fe6CDcd127D97df",
            ),
            "rousg": OndoToken(token="0x54043c656F0FAd0652D9Ae2603cDF347c5578d00"),
        }),
        Chain.ARBITRUM: OndoConfig(tokens={
            "usdy": OndoToken(token="0x35e050d3C0eC2d29D269a8EcEa763a183bDF9A9D"),
        }),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = OndoAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError):
            raise RegistryError(f"Ondo is not deployed on chain {self._chain_id}")

    @property
    def chain_id(self) -> int:
        return self._chain_id

    # --- USDY ---

    def usdy(self) -> TokenInfo:
        """Get USDY token info with current price from oracle."""
        token = self._config.tokens["usdy"]
        meta = read_token_metadata(self._chain, token.token)
        if token.oracle is None:
            raise RegistryError(f"No oracle registered for 'usdy' on chain {self._chain_id}")
        price = self._read_usdy_price(token.oracle)
        tvl = meta["total_supply"] * price if price else None

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source="RWADynamicOracle.getPriceData()",
            tvl=tvl,
            yield_type=YieldType.ACCUMULATING,
            protocol="ondo",
            category="us-treasury",
        )

    def usdy_price(self) -> float:
        """Get current USDY price from oracle (18 decimals)."""
        token = self._config.tokens["usdy"]
        if token.oracle is None:
            raise RegistryError(f"No oracle registered for 'usdy' on chain {self._chain_id}")
        return self._read_usdy_price(token.oracle)

    def _read_usdy_price(self, oracle_address: str) -> float:
        contract = self._chain.get_contract(oracle_address, load_abi("ondo_oracle"))
        price_raw, updated_at = contract.functions.getPriceData().call()
        assert_price_fresh(updated_at)
        price = price_raw / 10**18
        _log.debug("USDY price fetched: %.6f (updated_at=%d)", price, updated_at)
        return price

    # --- OUSG ---

    def ousg(self) -> TokenInfo:
        """Get OUSG token info with current price from oracle."""
        token = self._config.tokens["ousg"]
        meta = read_token_metadata(self._chain, token.token)
        if token.oracle is None:
            raise RegistryError(f"No oracle registered for 'ousg' on chain {self._chain_id}")
        price = self._read_ousg_price(token.oracle, token.token)
        tvl = meta["total_supply"] * price if price else None

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source="OndoOracle.getAssetPrice()",
            tvl=tvl,
            yield_type=YieldType.ACCUMULATING,
            protocol="ondo",
            category="us-treasury",
        )

    def ousg_price(self) -> float:
        """Get current OUSG price from oracle (18 decimals)."""
        token = self._config.tokens["ousg"]
        if token.oracle is None:
            raise RegistryError(f"No oracle registered for 'ousg' on chain {self._chain_id}")
        return self._read_ousg_price(token.oracle, token.token)

    def _read_ousg_price(self, oracle_address: str, token_address: str) -> float:
        contract = self._chain.get_contract(oracle_address, load_abi("ondo_ousg_oracle"))
        raw = contract.functions.getAssetPrice(
            self._chain.checksum(token_address)
        ).call()
        price = raw / 10**18
        _log.debug("OUSG price fetched: %.6f", price)
        return price

    # --- rUSDY (rebasing wrapper) ---

    def rusdy(self) -> TokenInfo:
        """Get rUSDY rebasing token info."""
        token = self._config.tokens["rusdy"]
        meta = read_token_metadata(self._chain, token.token)

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=1.0,  # Rebasing ≈ $1
            price_source="rebasing (balance adjusts)",
            tvl=meta["total_supply"],
            yield_type=YieldType.REBASING,
            protocol="ondo",
            category="us-treasury",
        )

    def rusdy_shares(self, holder: str) -> dict:
        """Get underlying shares for an rUSDY holder."""
        token = self._config.tokens["rusdy"]
        contract = self._chain.get_contract(token.token, combined_abi("erc20", "ondo_rebasing"))
        shares = contract.functions.sharesOf(
            self._chain.checksum(holder)
        ).call()
        balance = contract.functions.balanceOf(
            self._chain.checksum(holder)
        ).call()
        return {
            "shares": shares,
            "balance": balance / 10**18,
        }

    # --- rOUSG (rebasing wrapper) ---

    def rousg(self) -> TokenInfo:
        """Get rOUSG rebasing token info."""
        token = self._config.tokens["rousg"]
        meta = read_token_metadata(self._chain, token.token)

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=token.token,
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=1.0,
            price_source="rebasing (balance adjusts)",
            tvl=meta["total_supply"],
            yield_type=YieldType.REBASING,
            protocol="ondo",
            category="us-treasury",
        )

    # --- Compliance ---

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, value: int = 0
    ) -> ComplianceCheck:
        """Dispatch to the correct compliance check based on token address."""
        checksum = self._chain.checksum(token_address)
        tokens = self._config.tokens

        usdy_addr = self._chain.checksum(tokens["usdy"].token) if "usdy" in tokens else None
        ousg_addr = self._chain.checksum(tokens["ousg"].token) if "ousg" in tokens else None

        if checksum == usdy_addr:
            return self._can_transfer_usdy(from_addr, to_addr)
        if checksum == ousg_addr:
            return self._can_transfer_ousg(from_addr, to_addr)

        # rUSDY and rOUSG are rebasing wrappers — USDY compliance applies.
        return self._can_transfer_usdy(from_addr, to_addr)

    def is_blocked(self, address: str) -> bool:
        """Check if address is on the USDY blocklist."""
        token = self._config.tokens["usdy"]
        if token.blocklist is None:
            raise RegistryError(f"No blocklist registered for 'usdy' on chain {self._chain_id}")
        contract = self._chain.get_contract(token.blocklist, load_abi("ondo_blocklist"))
        return contract.functions.isBlocked(
            self._chain.checksum(address)
        ).call()

    def check_kyc(self, address: str, group: int = 0) -> bool:
        """Check KYC status for OUSG (requires KYC registry)."""
        token = self._config.tokens["ousg"]
        if token.kyc_registry is None:
            raise RegistryError(f"No kyc_registry registered for 'ousg' on chain {self._chain_id}")
        contract = self._chain.get_contract(token.kyc_registry, load_abi("ondo_kyc_registry"))
        return contract.functions.getKYCStatus(
            group, self._chain.checksum(address)
        ).call()

    def _can_transfer_usdy(self, from_addr: str, to_addr: str) -> ComplianceCheck:
        from_blocked = self.is_blocked(from_addr)
        to_blocked = self.is_blocked(to_addr)

        if from_blocked or to_blocked:
            who = "sender" if from_blocked else "receiver"
            _log.warning("USDY transfer blocked: %s", who)
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message=f"{who} is on the blocklist",
                method=ComplianceMethod.BLOCKLIST,
            )

        return ComplianceCheck(
            can_transfer=True,
            restriction_code=0,
            restriction_message="",
            method=ComplianceMethod.BLOCKLIST,
        )

    def _can_transfer_ousg(
        self, from_addr: str, to_addr: str, group: int = 0
    ) -> ComplianceCheck:
        from_kyc = self.check_kyc(from_addr, group)
        to_kyc = self.check_kyc(to_addr, group)

        if not from_kyc or not to_kyc:
            who = "sender" if not from_kyc else "receiver"
            _log.warning("OUSG transfer blocked (KYC): %s", who)
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=2,
                restriction_message=f"{who} not KYC-verified",
                method=ComplianceMethod.KYC_REGISTRY,
            )

        return ComplianceCheck(
            can_transfer=True,
            restriction_code=0,
            restriction_message="",
            method=ComplianceMethod.KYC_REGISTRY,
        )

    # --- Aggregation ---

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Ondo tokens on this chain."""
        tokens = []
        if "usdy" in self._config.tokens:
            tokens.append(self.usdy())
        if "ousg" in self._config.tokens:
            tokens.append(self.ousg())
        if "rusdy" in self._config.tokens:
            tokens.append(self.rusdy())
        if "rousg" in self._config.tokens:
            tokens.append(self.rousg())
        return tokens
