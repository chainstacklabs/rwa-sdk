"""Backed Finance adapter — bIB01, bCSPX, bNVDA."""

from web3 import Web3

from rwa_sdk.core.abi import load_abi
from rwa_sdk.core.models import (
    ComplianceCheck,
    ComplianceMethod,
    TokenInfo,
    YieldType,
)
from rwa_sdk.core.registry import ETHEREUM, get_addresses
from rwa_sdk.standards.erc20 import read_token_metadata

# Token metadata not available on-chain in a structured way
_TOKEN_META = {
    "bib01": {"category": "bond-etf", "feed_decimals": 8},
    "bcspx": {"category": "equity-etf", "feed_decimals": 8},
    "bnvda": {"category": "equity", "feed_decimals": None},
}


class BackedAdapter:
    """Read-only adapter for Backed Finance tokenized securities."""

    def __init__(self, w3: Web3, chain_id: int = ETHEREUM):
        self._w3 = w3
        self._chain_id = chain_id
        self._addresses = get_addresses("backed", chain_id)

    @property
    def protocol(self) -> str:
        return "backed"

    @property
    def chain_id(self) -> int:
        return self._chain_id

    # --- Tokens ---

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
        addrs = self._addresses["tokens"][token_key]
        meta = read_token_metadata(self._w3, addrs["token"])
        token_meta = _TOKEN_META[token_key]

        price = None
        price_source = None
        if addrs.get("chainlink_feed"):
            price = self._read_chainlink_price(
                addrs["chainlink_feed"], token_meta["feed_decimals"]
            )
            price_source = "Chainlink latestRoundData()"

        tvl = meta["total_supply"] * price if price else None

        return TokenInfo(
            symbol=meta["symbol"],
            name=meta["name"],
            address=addrs["token"],
            chain_id=self._chain_id,
            decimals=meta["decimals"],
            total_supply=meta["total_supply"],
            price=price,
            price_source=price_source,
            tvl=tvl,
            yield_type=YieldType.ACCUMULATING,
            protocol="backed",
            category=token_meta["category"],
        )

    # --- Price ---

    def _read_chainlink_price(self, feed_address: str, decimals: int) -> float:
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(feed_address),
            abi=load_abi("chainlink_aggregator"),
        )
        result = contract.functions.latestRoundData().call()
        answer = result[1]  # (roundId, answer, startedAt, updatedAt, answeredInRound)
        return answer / (10**decimals)

    # --- Compliance ---

    def _is_sanctioned(self, address: str) -> bool:
        sanctions_addr = self._addresses["shared"].get("sanctions_list")
        if not sanctions_addr:
            return False
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(sanctions_addr),
            abi=load_abi("chainalysis_sanctions"),
        )
        return contract.functions.isSanctioned(
            Web3.to_checksum_address(address)
        ).call()

    def can_transfer(
        self, token_address: str, from_addr: str, to_addr: str, value: int = 0
    ) -> ComplianceCheck:
        """Check if a transfer would be allowed (sanctions check only)."""
        from_sanctioned = self._is_sanctioned(from_addr)
        to_sanctioned = self._is_sanctioned(to_addr)

        if from_sanctioned or to_sanctioned:
            who = "sender" if from_sanctioned else "receiver"
            return ComplianceCheck(
                can_transfer=False,
                restriction_code=1,
                restriction_message=f"{who} is sanctioned",
                method=ComplianceMethod.SANCTIONS,
            )

        return ComplianceCheck(
            can_transfer=True,
            restriction_code=0,
            restriction_message="",
            method=ComplianceMethod.SANCTIONS,
        )

    def _is_paused(self, token_key: str) -> bool:
        addrs = self._addresses["tokens"][token_key]
        contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(addrs["token"]),
            abi=load_abi("backed_token"),
        )
        return contract.functions.isPaused().call()

    # --- Aggregation ---

    def all_tokens(self) -> list[TokenInfo]:
        """Get info for all Backed tokens on this chain."""
        tokens = []
        for key in _TOKEN_META:
            if key in self._addresses["tokens"]:
                tokens.append(self._read_token(key))
        return tokens
