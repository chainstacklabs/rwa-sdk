"""Maple Finance adapter — syrupUSDC, syrupUSDT."""

from web3 import Web3

from rwa_sdk.core.abi import combined_abi
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    PoolInfo,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.registry import MAPLE, ETHEREUM


_POOLS = {
    "syrup_usdc": {"name": "Maple syrupUSDC", "category": "private-credit"},
    "syrup_usdt": {"name": "Maple syrupUSDT", "category": "private-credit"},
}


class MapleAdapter:
    """Read-only adapter for Maple Finance lending pools."""

    def __init__(self, w3: Web3, chain_id: int = ETHEREUM):
        self._w3 = w3
        self._chain_id = chain_id
        self._addresses = MAPLE.get(chain_id, {})

    def syrup_usdc(self) -> TokenInfo:
        """Get syrupUSDC pool token info."""
        return self._read_pool_token("syrup_usdc")

    def syrup_usdt(self) -> TokenInfo:
        """Get syrupUSDT pool token info."""
        return self._read_pool_token("syrup_usdt")

    def pool_info(self, pool_key: str = "syrup_usdc") -> PoolInfo:
        """Get detailed pool info for a Maple pool."""
        addrs = self._addresses[pool_key]
        pool_addr = addrs["pool"]
        contract = self._get_pool_contract(pool_addr)

        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        total_assets_raw = contract.functions.totalAssets().call()
        total_assets = total_assets_raw / one_share
        share_price_raw = contract.functions.convertToAssets(one_share).call()
        share_price = share_price_raw / one_share
        asset_address = contract.functions.asset().call()

        # Utilization: (totalAssets - idle cash) / totalAssets
        # Read underlying asset balance of pool via raw balanceOf call
        balance_call_data = "0x70a08231" + Web3.to_checksum_address(pool_addr)[2:].zfill(64)
        idle = self._w3.eth.call({
            "to": Web3.to_checksum_address(asset_address),
            "data": Web3.to_bytes(hexstr=balance_call_data),
        })
        idle_balance = int(idle.hex(), 16) / one_share
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
        addrs = self._addresses[pool_key]
        contract = self._get_pool_contract(addrs["pool"])
        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        raw = contract.functions.convertToAssets(one_share).call()
        return raw / one_share

    def exit_price(self, pool_key: str = "syrup_usdc") -> float:
        """Get net share price (deducts unrealized losses)."""
        addrs = self._addresses[pool_key]
        contract = self._get_pool_contract(addrs["pool"])
        decimals = contract.functions.decimals().call()
        one_share = 10**decimals
        raw = contract.functions.convertToExitAssets(one_share).call()
        return raw / one_share

    def can_transfer(self, from_addr: str, to_addr: str) -> ComplianceCheck:
        """syrupUSDC pool tokens are permissionless — always allowed."""
        return ComplianceCheck(
            can_transfer=True,
            restriction_code=0,
            restriction_message="",
            method=ComplianceMethod.NONE,
        )

    def _read_pool_token(self, pool_key: str) -> TokenInfo:
        addrs = self._addresses[pool_key]
        pool_addr = addrs["pool"]
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

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Maple pool tokens on this chain."""
        tokens = []
        for key in _POOLS:
            if key in self._addresses:
                tokens.append(self._read_pool_token(key))
        return tokens
