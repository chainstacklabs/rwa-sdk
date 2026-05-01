"""Maple Finance adapter — syrupUSDC, syrupUSDT."""

import logging
from dataclasses import dataclass
from typing import ClassVar

from rwa_sdk.core.chain import Chain
from rwa_sdk.core.exceptions import RegistryError
from rwa_sdk.core.models import (
    Category,
    ComplianceCheck,
    ComplianceMethod,
    PoolInfo,
    TokenInfo,
    YieldType,
)
from rwa_sdk.infra.abi import combined_abi, load_abi
from rwa_sdk.infra.evm import EVMChainService
from rwa_sdk.protocols.base import register
from rwa_sdk.standards.erc20 import read_balance

_log = logging.getLogger(__name__)

# bytes32("P:lend") — Solidity bytes32 literals are right-padded with zeros
_LEND_FUNCTION_ID: bytes = b"P:lend" + b"\x00" * 26


@dataclass(frozen=True)
class MapleToken:
    token: str
    pool: str
    name: str
    category: Category
    pool_manager: str | None = None


@dataclass(frozen=True)
class MapleConfig:
    tokens: dict[str, MapleToken]
    globals: str | None = None
    pool_permission_manager: str | None = None


@register
class MapleAdapter:
    """Read-only adapter for Maple Finance lending pools."""

    protocol = "maple"

    config: ClassVar[dict[Chain, MapleConfig]] = {
        Chain.ETHEREUM: MapleConfig(
            tokens={
                "syrup_usdc": MapleToken(
                    # ERC-4626: pool IS the token — both share the same address
                    token="0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b",
                    pool="0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b",
                    name="Maple syrupUSDC",
                    category=Category.PRIVATE_CREDIT,
                    pool_manager="0x7aD5fFa5fdF509E30186F4609c2f6269f4B6158F",
                ),
                "syrup_usdt": MapleToken(
                    token="0x356B8d89c1e1239Cbbb9dE4815c39A1474d5BA7D",
                    pool="0x356B8d89c1e1239Cbbb9dE4815c39A1474d5BA7D",
                    name="Maple syrupUSDT",
                    category=Category.PRIVATE_CREDIT,
                ),
            },
            globals="0x34E7014E2Ef62C2F3Cc8c8c25Ac0110E2aA33B00",
            pool_permission_manager="0xBe10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3",
        ),
    }

    def __init__(self, chain: EVMChainService):
        self._chain = chain
        self._chain_id = chain.chain_id
        try:
            self._config = MapleAdapter.config[Chain(self._chain_id)]
        except (KeyError, ValueError) as err:
            raise RegistryError(f"Maple is not deployed on chain {self._chain_id}") from err

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def syrup_usdc(self) -> TokenInfo:
        """Get syrupUSDC pool token info."""
        return self._read_token("syrup_usdc")

    def syrup_usdt(self) -> TokenInfo:
        """Get syrupUSDT pool token info."""
        return self._read_token("syrup_usdt")

    def pool_info(self, pool_key: str = "syrup_usdc") -> PoolInfo:
        """Get detailed pool info for a Maple pool."""
        token = self._config.tokens[pool_key]
        contract = self._get_pool_contract(token.pool)

        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        total_assets = contract.functions.totalAssets().call() / one_share
        share_price = self._price_from_contract(contract, "convertToAssets")
        exit_price = self._price_from_contract(contract, "convertToExitAssets")
        asset_address = contract.functions.asset().call()

        idle_balance = read_balance(self._chain, asset_address, token.pool)
        utilization = (total_assets - idle_balance) / total_assets if total_assets > 0 else 0

        return PoolInfo(
            name=token.name,
            address=token.pool,
            chain_id=self._chain_id,
            asset=asset_address,
            total_assets=total_assets,
            share_price=share_price,
            exit_price=exit_price,
            utilization=utilization,
            protocol="maple",
        )

    def list_pools(self) -> list[str]:
        """Return the available pool keys for this chain (e.g. 'syrup_usdc', 'syrup_usdt')."""
        return list(self._config.tokens.keys())

    def share_price(self, pool_key: str = "syrup_usdc") -> float:
        """Gross share price via convertToAssets().

        Reflects the theoretical redemption value before deducting unrealized
        loan losses. Use this for APY calculations (comparing price over time).
        For liquidation or risk-adjusted NAV, prefer exit_price().
        """
        contract = self._get_pool_contract(self._config.tokens[pool_key].pool)
        return self._price_from_contract(contract, "convertToAssets")

    def exit_price(self, pool_key: str = "syrup_usdc") -> float:
        """Net share price via convertToExitAssets().

        Deducts unrealized losses from the gross price. Use this for
        risk-adjusted NAV and liquidation scenario analysis.
        Returns a value <= share_price().
        """
        contract = self._get_pool_contract(self._config.tokens[pool_key].pool)
        return self._price_from_contract(contract, "convertToExitAssets")

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, _value: int = 0
    ) -> ComplianceCheck:
        """Check transfer eligibility via Maple PoolPermissionManager.

        Tokens whose pool has a pool_manager entry use BITMAP compliance.
        All others (e.g. syrup_usdt) are permissionless and return NONE.
        Compliance is checked sender-first; if the sender is blocked the receiver is not queried.
        """
        pool_key = self._resolve_pool_key(token_address)
        if pool_key is None:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)

        token = self._config.tokens[pool_key]
        pool_manager_addr = token.pool_manager
        pm_contract_addr = self._config.pool_permission_manager

        if not pool_manager_addr or not pm_contract_addr:
            _log.debug(
                "Maple compliance skipped for %s: no PoolPermissionManager configured", pool_key
            )
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)

        contract = self._chain.get_contract(
            pm_contract_addr, load_abi("maple_pool_permission_manager")
        )
        checksum_pm = self._chain.checksum(pool_manager_addr)
        sender_ok = contract.functions.hasPermission(
            checksum_pm, self._chain.checksum(from_addr), _LEND_FUNCTION_ID
        ).call()
        receiver_ok = contract.functions.hasPermission(
            checksum_pm, self._chain.checksum(to_addr), _LEND_FUNCTION_ID
        ).call()

        if not sender_ok:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="sender not permitted",
                method=ComplianceMethod.BITMAP,
                blocking_party="sender",
            )
        if not receiver_ok:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="receiver not permitted",
                method=ComplianceMethod.BITMAP,
                blocking_party="receiver",
            )
        return ComplianceCheck(can_transfer=True, method=ComplianceMethod.BITMAP)

    def _read_token(self, pool_key: str) -> TokenInfo:
        token = self._config.tokens[pool_key]
        contract = self._get_pool_contract(token.pool)

        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        total_supply = contract.functions.totalSupply().call() / one_share
        total_assets = contract.functions.totalAssets().call() / one_share
        share_price = self._price_from_contract(contract, "convertToAssets")
        _log.debug("Maple %s share price: %.6f", pool_key, share_price)

        return TokenInfo(
            symbol=contract.functions.symbol().call(),
            name=contract.functions.name().call(),
            address=token.pool,
            chain_id=self._chain_id,
            decimals=decimals,
            total_supply=total_supply,
            price=share_price,
            price_source="ERC-4626 convertToAssets()",
            tvl=total_assets,
            yield_type=YieldType.VAULT,
            protocol="maple",
            category=token.category,
        )

    def _price_from_contract(self, contract, fn_name: str) -> float:
        one_share = 10 ** contract.functions.decimals().call()
        return getattr(contract.functions, fn_name)(one_share).call() / one_share

    def _get_pool_contract(self, address: str):
        return self._chain.get_contract(address, combined_abi("erc20", "erc4626", "maple_pool"))

    def _resolve_pool_key(self, token_address: str) -> str | None:
        checksummed = self._chain.checksum(token_address)
        for key, token in self._config.tokens.items():
            if self._chain.checksum(token.pool) == checksummed:
                return key
        return None

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Maple pool tokens on this chain."""
        return [self._read_token(key) for key in self._config.tokens]
