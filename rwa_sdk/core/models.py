"""Pydantic models for normalized RWA data."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Category(str, Enum):
    """Asset category vocabulary for RWA tokens."""

    US_TREASURY = "us-treasury"
    PRIVATE_CREDIT = "private-credit"
    BOND_ETF = "bond-etf"
    EQUITY_ETF = "equity-etf"
    EQUITY = "equity"


class YieldType(str, Enum):
    """How the token accrues yield."""

    ACCUMULATING = "accumulating"  # Price rises, balance constant (USDY, OUSG, bTokens)
    REBASING = "rebasing"  # Balance adjusts, price ~$1 (rUSDY, rOUSG)
    VAULT = "vault"  # ERC-4626 share price accrual (Maple, Centrifuge)
    DIVIDEND_MINT = "dividend_mint"  # Flat NAV, new tokens minted (BUIDL)


class ComplianceMethod(str, Enum):
    """How transfer restrictions are enforced."""

    PRE_TRANSFER_CHECK = "preTransferCheck"  # Securitize DS Protocol
    TRANSFER_RESTRICTION = "checkTransferRestriction"  # ERC-1404 (Centrifuge)
    BLOCKLIST = "blocklist"  # Ondo USDY
    KYC_REGISTRY = "kyc_registry"  # Ondo OUSG
    SANCTIONS = "sanctions"  # Chainalysis only (Backed)
    BITMAP = "bitmap"  # Maple PoolPermissionManager
    NONE = "none"  # Permissionless


class TokenInfo(BaseModel):
    """Normalized token data returned by protocol adapters."""

    symbol: str
    name: str
    address: str
    chain_id: int = 1
    decimals: int
    total_supply: float
    price: float | None = None
    price_source: str | None = None
    tvl: float | None = None
    yield_type: YieldType
    protocol: str
    category: Category | None = None


class ComplianceCheck(BaseModel):
    """Result of a transfer eligibility check."""

    can_transfer: bool
    restriction_code: int = 0
    restriction_message: str = ""
    method: ComplianceMethod
    blocking_party: Literal["sender", "receiver"] | None = None


class PoolInfo(BaseModel):
    """Pool-level data for vault-based protocols (Maple, Centrifuge)."""

    name: str
    address: str
    chain_id: int = 1
    asset: str  # Underlying asset address (e.g. USDC)
    total_assets: float
    share_price: float
    exit_price: float | None = None
    utilization: float | None = None
    protocol: str
