"""Securitize adapter — BlackRock BUIDL."""

import logging

from web3 import Web3

from rwa_sdk.core.abi import combined_abi
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.registry import ETHEREUM, get_addresses

_log = logging.getLogger(__name__)

_TOKENS = {
    "buidl": {"name": "BlackRock BUIDL", "category": "us-treasury"},
    "buidl_i": {"name": "BlackRock BUIDL-I", "category": "us-treasury"},
}


class SecuritizeAdapter:
    """Read-only adapter for Securitize DS Protocol tokens (BlackRock BUIDL)."""

    def __init__(self, w3: Web3, chain_id: int = ETHEREUM):
        self._w3 = w3
        self._chain_id = chain_id
        self._addresses = get_addresses("securitize", chain_id)

    @property
    def protocol(self) -> str:
        return "securitize"

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def buidl(self) -> TokenInfo:
        """Get BUIDL token info."""
        return self._read_token("buidl")

    def buidl_i(self) -> TokenInfo:
        """Get BUIDL-I token info."""
        return self._read_token("buidl_i")

    def wallet_count(self, token_key: str = "buidl") -> int:
        """Get the number of BUIDL holder wallets."""
        return self._get_contract(token_key).functions.walletCount().call()

    def get_wallet_at(self, index: int, token_key: str = "buidl") -> str:
        """Get holder address by index."""
        return self._get_contract(token_key).functions.getWalletAt(index).call()

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, value: int = 0
    ) -> ComplianceCheck:
        """Run Securitize DS Protocol pre-transfer compliance check.

        Calls the on-chain `preTransferCheck(from, to, value)` function.
        Returns `restriction_code=0` if the transfer is permitted; any other
        code indicates a compliance failure with a human-readable reason in
        `restriction_message`.
        """
        token_key = self._resolve_token_key(token_address)
        return self._pre_transfer_check(from_addr, to_addr, value, token_key)

    def _pre_transfer_check(
        self, from_addr: str, to_addr: str, value: int, token_key: str = "buidl"
    ) -> ComplianceCheck:
        contract = self._get_contract(token_key)
        code, reason = contract.functions.preTransferCheck(
            Web3.to_checksum_address(from_addr),
            Web3.to_checksum_address(to_addr),
            value,
        ).call()
        _log.debug("BUIDL preTransferCheck: code=%d reason=%r", code, reason)
        return ComplianceCheck(
            can_transfer=(code == 0),
            restriction_code=code,
            restriction_message=reason,
            method=ComplianceMethod.PRE_TRANSFER_CHECK,
        )

    def get_ds_service(self, service_id: int, token_key: str = "buidl") -> str:
        """Get address of a DS Protocol service.

        service_id 1 = RegistryService, 2 = ComplianceService
        """
        return self._get_contract(token_key).functions.getDSService(service_id).call()

    def _read_token(self, token_key: str) -> TokenInfo:
        addrs = self._addresses["tokens"][token_key]
        contract = self._get_contract(token_key)
        meta = _TOKENS[token_key]

        decimals = contract.functions.decimals().call()
        total_supply_raw = contract.functions.totalSupply().call()
        total_supply = total_supply_raw / (10**decimals)

        # BUIDL = $1.00 constant NAV, yield via dividend minting
        return TokenInfo(
            symbol=contract.functions.symbol().call(),
            name=contract.functions.name().call(),
            address=addrs["token"],
            chain_id=self._chain_id,
            decimals=decimals,
            total_supply=total_supply,
            price=1.0,
            price_source="constant NAV ($1.00, yield via dividend mint)",
            tvl=total_supply,  # 1:1 at $1 NAV
            yield_type=YieldType.DIVIDEND_MINT,
            protocol="securitize",
            category=meta["category"],
        )

    def _get_contract(self, token_key: str):
        addrs = self._addresses["tokens"][token_key]
        return self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["token"]),
            abi=combined_abi("erc20", "securitize_token"),
        )

    def _resolve_token_key(self, token_address: str) -> str:
        """Resolve a checksummed token address to its registry key."""
        checksum = Web3.to_checksum_address(token_address)
        for key, addrs in self._addresses["tokens"].items():
            if Web3.to_checksum_address(addrs["token"]) == checksum:
                return key
        raise ValueError(f"Token address {token_address!r} not found in Securitize registry")

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Securitize tokens on this chain."""
        tokens = []
        for key in _TOKENS:
            if key in self._addresses["tokens"]:
                tokens.append(self._read_token(key))
        return tokens
