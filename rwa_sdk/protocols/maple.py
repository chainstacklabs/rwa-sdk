"""Maple Finance adapter — syrupUSDC, syrupUSDT."""

from typing import cast

from web3 import Web3

from rwa_sdk.core.abi import combined_abi, load_abi
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    PoolInfo,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.registry import ETHEREUM, get_addresses
from rwa_sdk.standards.erc20 import read_balance

_POOLS = {
    "syrup_usdc": {"name": "Maple syrupUSDC", "category": "private-credit"},
    "syrup_usdt": {"name": "Maple syrupUSDT", "category": "private-credit"},
}

# bytes32("P:lend") — Solidity bytes32 literals are right-padded with zeros
_LEND_FUNCTION_ID: bytes = b"P:lend" + b"\x00" * 26


class MapleAdapter:
    """Read-only adapter for Maple Finance lending pools."""

    def __init__(self, w3: Web3, chain_id: int = ETHEREUM):
        self._w3 = w3
        self._chain_id = chain_id
        self._addresses = get_addresses("maple", chain_id)

    @property
    def protocol(self) -> str:
        return "maple"

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def syrup_usdc(self) -> TokenInfo:
        """Get syrupUSDC pool token info."""
        return self._read_pool_token("syrup_usdc")

    def syrup_usdt(self) -> TokenInfo:
        """Get syrupUSDT pool token info."""
        return self._read_pool_token("syrup_usdt")

    def pool_info(self, pool_key: str = "syrup_usdc") -> PoolInfo:
        """Get detailed pool info for a Maple pool."""
        addrs = self._addresses["tokens"][pool_key]
        pool_addr = cast(str, addrs.get("pool"))
        contract = self._get_pool_contract(pool_addr)

        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        total_assets_raw = contract.functions.totalAssets().call()
        total_assets = total_assets_raw / one_share
        share_price_raw = contract.functions.convertToAssets(one_share).call()
        share_price = share_price_raw / one_share
        asset_address = contract.functions.asset().call()

        # Utilization: (totalAssets - idle cash) / totalAssets
        idle_balance = read_balance(self._w3, asset_address, pool_addr)
        utilization = (total_assets - idle_balance) / total_assets if total_assets > 0 else 0

        return PoolInfo(
            name=_POOLS[pool_key]["name"],
            address=pool_addr,
            chain_id=self._chain_id,
            asset=asset_address,
            total_assets=total_assets,
            share_price=share_price,
            utilization=utilization,
            protocol="maple",
        )

    def share_price(self, pool_key: str = "syrup_usdc") -> float:
        """Get current share price (gross, before unrealized losses)."""
        addrs = self._addresses["tokens"][pool_key]
        contract = self._get_pool_contract(cast(str, addrs.get("pool")))
        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        raw = contract.functions.convertToAssets(one_share).call()
        return raw / one_share

    def exit_price(self, pool_key: str = "syrup_usdc") -> float:
        """Get net share price (deducts unrealized losses)."""
        addrs = self._addresses["tokens"][pool_key]
        contract = self._get_pool_contract(cast(str, addrs.get("pool")))
        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        raw = contract.functions.convertToExitAssets(one_share).call()
        return raw / one_share

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, value: int = 0
    ) -> ComplianceCheck:
        """Check transfer eligibility via Maple PoolPermissionManager.

        Tokens whose pool has a pool_manager registry entry use BITMAP compliance.
        All others (e.g. syrup_usdt) are permissionless and return NONE.
        Compliance is checked sender-first; if the sender is blocked the receiver is not queried.
        """
        pool_key = self._resolve_pool_key(token_address)
        if pool_key is None:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)

        token_addrs = self._addresses["tokens"][pool_key]
        pool_manager_addr = token_addrs.get("pool_manager")
        pm_contract_addr = self._addresses.get("shared", {}).get("pool_permission_manager")

        if not pool_manager_addr or not pm_contract_addr:
            return ComplianceCheck(can_transfer=True, method=ComplianceMethod.NONE)

        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(pm_contract_addr),
            abi=load_abi("maple_pool_permission_manager"),
        )
        checksum_pm = Web3.to_checksum_address(pool_manager_addr)
        sender_ok = contract.functions.hasPermission(
            checksum_pm, Web3.to_checksum_address(from_addr), _LEND_FUNCTION_ID
        ).call()
        receiver_ok = contract.functions.hasPermission(
            checksum_pm, Web3.to_checksum_address(to_addr), _LEND_FUNCTION_ID
        ).call()

        if not sender_ok:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="sender not permitted",
                method=ComplianceMethod.BITMAP,
            )
        if not receiver_ok:
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message="receiver not permitted",
                method=ComplianceMethod.BITMAP,
            )
        return ComplianceCheck(can_transfer=True, method=ComplianceMethod.BITMAP)

    def _read_pool_token(self, pool_key: str) -> TokenInfo:
        addrs = self._addresses["tokens"][pool_key]
        pool_addr = cast(str, addrs.get("pool"))
        contract = self._get_pool_contract(pool_addr)
        meta = _POOLS[pool_key]

        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        total_supply_raw = contract.functions.totalSupply().call()
        total_supply = total_supply_raw / one_share
        total_assets_raw = contract.functions.totalAssets().call()
        total_assets = total_assets_raw / one_share
        share_price_raw = contract.functions.convertToAssets(one_share).call()
        share_price = share_price_raw / one_share

        return TokenInfo(
            symbol=contract.functions.symbol().call(),
            name=contract.functions.name().call(),
            address=pool_addr,
            chain_id=self._chain_id,
            decimals=decimals,
            total_supply=total_supply,
            price=share_price,
            price_source="ERC-4626 convertToAssets()",
            tvl=total_assets,
            yield_type=YieldType.VAULT,
            protocol="maple",
            category=meta["category"],
        )

    def _get_pool_contract(self, address: str):
        return self._w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=combined_abi("erc20", "erc4626", "maple_pool"),
        )

    def _resolve_pool_key(self, token_address: str) -> str | None:
        """Return pool key whose pool address matches token_address, else None.

        In Maple's ERC-4626 model the pool contract is also the token contract,
        so pool address and token address are the same.
        """
        checksummed = Web3.to_checksum_address(token_address)
        for key, addrs in self._addresses.get("tokens", {}).items():
            pool = addrs.get("pool", "")
            if pool and Web3.to_checksum_address(pool) == checksummed:
                return key
        return None

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Maple pool tokens on this chain."""
        tokens = []
        for key in _POOLS:
            if key in self._addresses["tokens"]:
                tokens.append(self._read_pool_token(key))
        return tokens
