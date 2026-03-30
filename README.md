# rwa-sdk

Read-only Python SDK for querying Real World Asset (RWA) tokens across EVM chains.

One interface for token metadata, price/NAV, TVL, and transfer compliance across Ondo, BlackRock BUIDL, Backed, Maple, and Centrifuge — the protocols that make up the majority of on-chain RWA value.

## Why

There's no unified Python SDK for RWA tokens. If you want to query tokenized treasuries, private credit, or equities on-chain, you're stitching together raw ABIs, protocol-specific docs, and multi-chain plumbing by hand.

These protocols look similar on the surface (all ERC-20) but diverge underneath — three different yield patterns, four compliance models, no standard oracle interface. This SDK normalizes all of it.

## Install

```bash
uv add git+https://github.com/chainstacklabs/rwa-sdk
```

Or with pip:

```bash
pip install git+https://github.com/chainstacklabs/rwa-sdk
```

Requires Python 3.10+. Only two dependencies: `web3` and `pydantic`.

## Quick start

```python
from rwa_sdk import RWA

rwa = RWA(rpc_url="https://ethereum-mainnet.core.chainstack.com/YOUR_KEY")

# Get token info with live price from on-chain oracle
token = rwa.ondo.usdy()
print(token.symbol)      # USDY
print(token.price)       # 1.1279 (from RWADynamicOracle)
print(token.tvl)         # 587132506.0
print(token.yield_type)  # YieldType.ACCUMULATING
```

## Supported protocols

| Protocol | Tokens | Yield pattern | Price source |
|---|---|---|---|
| Ondo Finance | USDY, OUSG, rUSDY, rOUSG | Accumulating / Rebasing | Ondo oracle |
| BlackRock BUIDL | BUIDL, BUIDL-I | Dividend mint ($1 NAV) | Constant |
| Backed Finance | bIB01, bCSPX, bNVDA | Accumulating | Chainlink feeds |
| Maple Finance | syrupUSDC, syrupUSDT | ERC-4626 vault | `convertToAssets()` |
| Centrifuge | JTRSY | ERC-4626 vault | Centrifuge API |

## Usage

### Query all tokens at once

```python
for t in rwa.all_tokens():
    price = f"${t.price:.4f}" if t.price else "N/A"
    tvl = f"${t.tvl:,.0f}" if t.tvl else "N/A"
    print(f"{t.symbol:12s} | {t.protocol:10s} | {price:>12s} | {tvl}")
```

Output:

```
USDY         | ondo       |      $1.1279 | $587,132,506
OUSG         | ondo       |    $114.7259 | $388,964,385
rUSDY        | ondo       |      $1.0000 | $13,800,855
rOUSG        | ondo       |      $1.0000 | $0
bIB01        | backed     |    $119.7900 | $5,429,698
bCSPX        | backed     |          N/A | N/A
bNVDA        | backed     |          N/A | N/A
BUIDL        | securitize |      $1.0000 | $168,501,226
BUIDL-I      | securitize |      $1.0000 | $767,225,232
syrupUSDC    | maple      |      $1.1576 | $1,786,175,587
syrupUSDT    | maple      |      $1.1214 | $1,002,816,176
JTRSY        | centrifuge |      $1.0984 | $1,090,331,446
```

### Compliance checks

Each protocol enforces transfer restrictions differently. The SDK normalizes them:

```python
# Ondo — blocklist check
check = rwa.ondo.can_transfer_usdy(sender, receiver)
print(check.can_transfer)          # True/False
print(check.restriction_message)   # "sender is on the blocklist"

# Securitize/BUIDL — DS Protocol pre-transfer check
check = rwa.securitize.pre_transfer_check(sender, receiver, amount)
print(check.restriction_code)      # 0 = allowed
print(check.restriction_message)   # human-readable reason

# Backed — Chainalysis sanctions only
check = rwa.backed.can_transfer(sender, receiver)

# Centrifuge — ERC-1404 transfer restriction
check = rwa.centrifuge.check_transfer_restriction(sender, receiver, amount)
```

### ERC-4626 vault details (Maple)

```python
# Pool-level data
pool = rwa.maple.pool_info("syrup_usdc")
print(pool.total_assets)   # TVL in USDC
print(pool.share_price)    # gross share price
print(pool.utilization)    # 0.9999

# Gross vs net share price
print(rwa.maple.share_price())  # before unrealized losses
print(rwa.maple.exit_price())   # after unrealized losses
```

### BUIDL holder data

```python
count = rwa.securitize.wallet_count()
print(f"{count} BUIDL holders")

# Enumerate holders by index
for i in range(min(count, 10)):
    print(rwa.securitize.get_wallet_at(i))
```

### Direct price reads

```python
rwa.ondo.usdy_price()     # 1.1279 (from RWADynamicOracle)
rwa.ondo.ousg_price()     # 114.7259 (from OndoOracle)
rwa.maple.share_price()   # 1.1576 (from convertToAssets)
```

## How it works

All reads are on-chain via `eth_call` — no database, no indexer, no API keys (except Centrifuge which uses their public GraphQL API for price data).

The SDK ships JSON ABIs for every contract it reads. No runtime Etherscan fetching.

### Yield patterns normalized

| Pattern | How price works | Protocols |
|---|---|---|
| Accumulating | Token balance constant, price rises over time | Ondo USDY/OUSG, Backed bTokens |
| Rebasing | Price stays ~$1, balance adjusts | Ondo rUSDY/rOUSG |
| ERC-4626 vault | Share price accrues via `convertToAssets()` | Maple, Centrifuge |
| Dividend mint | Flat $1 NAV, new tokens minted as yield | BUIDL |

### RPC provider

Ships pre-configured for [Chainstack](https://chainstack.com) but works with any Ethereum RPC:

```python
# Chainstack (default)
rwa = RWA(rpc_url="https://ethereum-mainnet.core.chainstack.com/YOUR_KEY")

# Any RPC
rwa = RWA(rpc_url="https://your-rpc-endpoint")

# Access the underlying Web3 instance
rwa.w3.eth.block_number
```

## Data models

All return types are Pydantic models:

```python
from rwa_sdk import TokenInfo, ComplianceCheck, PoolInfo, YieldType

# TokenInfo fields
token.symbol         # str
token.name           # str
token.address        # str
token.chain_id       # int (1 = Ethereum)
token.decimals       # int
token.total_supply   # float
token.price          # float | None
token.price_source   # str | None (e.g. "RWADynamicOracle.getPrice()")
token.tvl            # float | None
token.yield_type     # YieldType enum
token.protocol       # str
token.category       # str | None (e.g. "us-treasury", "private-credit")
```

## License

MIT
