"""Ondo Finance adapter — USDY, OUSG, rUSDY, rOUSG."""

from web3 import Web3

from rwa_sdk.core.abi import combined_abi, load_abi
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.registry import ETHEREUM, get_addresses
from rwa_sdk.standards.erc20 import read_token_metadata


class OndoAdapter:
    """Read-only adapter for Ondo Finance RWA tokens."""

    def __init__(self, w3: Web3, chain_id: int = ETHEREUM):
        self._w3 = w3
        self._chain_id = chain_id
        self._addresses = get_addresses("ondo", chain_id)

    @property
    def protocol(self) -> str:
        return "ondo"

    @property
    def chain_id(self) -> int:
        return self._chain_id

    # --- USDY ---

    def usdy(self) -> TokenInfo:
        """Get USDY token info with current price from oracle."""
        addrs = self._addresses["tokens"]["usdy"]
        meta = read_token_metadata(self._w3, addrs["token"])
        price = self._read_usdy_price(addrs["oracle"])
        tvl = meta["total_supply"] * price if price else None

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=addrs["token"],
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source="RWADynamicOracle.getPrice()",
            tvl=tvl,
            yield_type=YieldType.ACCUMULATING,
            protocol="ondo",
            category="us-treasury",
        )

    def usdy_price(self) -> float:
        """Get current USDY price from oracle (18 decimals)."""
        return self._read_usdy_price(self._addresses["tokens"]["usdy"]["oracle"])

    def _read_usdy_price(self, oracle_address: str) -> float:
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(oracle_address),
            abi=load_abi("ondo_oracle"),
        )
        raw = contract.functions.getPrice().call()
        return raw / 10**18

    # --- OUSG ---

    def ousg(self) -> TokenInfo:
        """Get OUSG token info with current price from oracle."""
        addrs = self._addresses["tokens"]["ousg"]
        meta = read_token_metadata(self._w3, addrs["token"])
        price = self._read_ousg_price(addrs["oracle"], addrs["token"])
        tvl = meta["total_supply"] * price if price else None

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=addrs["token"],
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
        addrs = self._addresses["tokens"]["ousg"]
        return self._read_ousg_price(addrs["oracle"], addrs["token"])

    def _read_ousg_price(self, oracle_address: str, token_address: str) -> float:
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(oracle_address),
            abi=load_abi("ondo_ousg_oracle"),
        )
        raw = contract.functions.getAssetPrice(
            Web3.to_checksum_address(token_address)
        ).call()
        return raw / 10**18

    # --- rUSDY (rebasing wrapper) ---

    def rusdy(self) -> TokenInfo:
        """Get rUSDY rebasing token info."""
        addrs = self._addresses["tokens"]["rusdy"]
        meta = read_token_metadata(self._w3, addrs["token"])

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=addrs["token"],
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
        addrs = self._addresses["tokens"]["rusdy"]
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["token"]),
            abi=combined_abi("erc20", "ondo_rebasing"),
        )
        shares = contract.functions.sharesOf(
            Web3.to_checksum_address(holder)
        ).call()
        balance = contract.functions.balanceOf(
            Web3.to_checksum_address(holder)
        ).call()
        return {
            "shares": shares,
            "balance": balance / 10**18,
        }

    # --- rOUSG (rebasing wrapper) ---

    def rousg(self) -> TokenInfo:
        """Get rOUSG rebasing token info."""
        addrs = self._addresses["tokens"]["rousg"]
        meta = read_token_metadata(self._w3, addrs["token"])

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=addrs["token"],
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
        checksum = Web3.to_checksum_address(token_address)
        tokens = self._addresses["tokens"]

        usdy_addr = Web3.to_checksum_address(tokens["usdy"]["token"]) if "usdy" in tokens else None
        ousg_addr = Web3.to_checksum_address(tokens["ousg"]["token"]) if "ousg" in tokens else None

        if checksum == usdy_addr:
            return self._can_transfer_usdy(from_addr, to_addr)
        if checksum == ousg_addr:
            return self._can_transfer_ousg(from_addr, to_addr)

        # rUSDY and rOUSG are rebasing wrappers — same underlying compliance
        return self._can_transfer_usdy(from_addr, to_addr)

    def is_blocked(self, address: str) -> bool:
        """Check if address is on the USDY blocklist."""
        addrs = self._addresses["tokens"]["usdy"]
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["blocklist"]),
            abi=load_abi("ondo_blocklist"),
        )
        return contract.functions.isBlocked(
            Web3.to_checksum_address(address)
        ).call()

    def check_kyc(self, address: str, group: int = 0) -> bool:
        """Check KYC status for OUSG (requires KYC registry)."""
        addrs = self._addresses["tokens"]["ousg"]
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["kyc_registry"]),
            abi=load_abi("ondo_kyc_registry"),
        )
        return contract.functions.getKYCStatus(
            group, Web3.to_checksum_address(address)
        ).call()

    def _can_transfer_usdy(self, from_addr: str, to_addr: str) -> ComplianceCheck:
        from_blocked = self.is_blocked(from_addr)
        to_blocked = self.is_blocked(to_addr)

        if from_blocked or to_blocked:
            who = "sender" if from_blocked else "receiver"
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
        tokens_dict = self._addresses["tokens"]
        tokens = []
        if "usdy" in tokens_dict:
            tokens.append(self.usdy())
        if "ousg" in tokens_dict:
            tokens.append(self.ousg())
        if "rusdy" in tokens_dict:
            tokens.append(self.rusdy())
        if "rousg" in tokens_dict:
            tokens.append(self.rousg())
        return tokens
