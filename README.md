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
from rwa_sdk import RWAChain

rwa = RWAChain(rpc_url="https://ethereum-mainnet.core.chainstack.com/YOUR_KEY")

# Get token info with live price from on-chain oracle
token = rwa.adapters.ondo.usdy()
print(token.symbol)      # USDY
print(token.price)       # 1.1290 (from RWADynamicOracle.getPriceData())
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
USDY         | ondo       |      $1.1290 | $587,132,506
OUSG         | ondo       |    $114.8500 | $388,964,385
rUSDY        | ondo       |      $1.0000 | $13,800,855
rOUSG        | ondo       |      $1.0000 | $0
bIB01        | backed     |    $119.9600 | $5,429,698
bCSPX        | backed     |          N/A | N/A
bNVDA        | backed     |          N/A | N/A
BUIDL        | securitize |      $1.0000 | $168,501,226
BUIDL-I      | securitize |      $1.0000 | $767,225,232
syrupUSDC    | maple      |      $1.1590 | $1,786,175,587
syrupUSDT    | maple      |      $1.1214 | $1,002,816,176
JTRSY        | centrifuge |      $1.0997 | $1,090,331,446
```

### Compliance checks

Each protocol enforces transfer restrictions differently. The SDK normalizes them through a single `can_transfer()` call:

```python
# Unified interface — works for any token by symbol
check = rwa.can_transfer("USDY", sender, receiver)
print(check.can_transfer)          # True/False
print(check.method)                # ComplianceMethod.BLOCKLIST
print(check.restriction_message)   # "sender is on the blocklist"
print(check.blocking_party)        # "sender" | "receiver" | None

# Or call the adapter directly with a token address
check = rwa.adapters.ondo.can_transfer(token_address, sender, receiver)          # value ignored
check = rwa.adapters.securitize.can_transfer(token_address, sender, receiver, amount)
check = rwa.adapters.backed.can_transfer(token_address, sender, receiver)          # value ignored
check = rwa.adapters.centrifuge.can_transfer(token_address, sender, receiver, amount)
```

Compliance methods per protocol:

| Protocol | Method | Model |
|---|---|---|
| Ondo USDY/rUSDY | Blocklist | `ComplianceMethod.BLOCKLIST` |
| Ondo OUSG/rOUSG | KYC registry | `ComplianceMethod.KYC_REGISTRY` |
| Backed | Chainalysis sanctions | `ComplianceMethod.SANCTIONS` |
| Maple syrupUSDC | PoolPermissionManager bitmap | `ComplianceMethod.BITMAP` |
| Maple syrupUSDT | Permissionless | `ComplianceMethod.NONE` |
| Securitize BUIDL | DS Protocol preTransferCheck | `ComplianceMethod.PRE_TRANSFER_CHECK` |
| Centrifuge JTRSY | ERC-1404 restriction | `ComplianceMethod.TRANSFER_RESTRICTION` |

### ERC-4626 vault details (Maple)

```python
# Pool-level data
pool = rwa.adapters.maple.pool_info("syrup_usdc")
print(pool.total_assets)   # TVL in USDC
print(pool.share_price)    # gross share price
print(pool.utilization)    # 0.9999

# Gross vs net share price
print(rwa.adapters.maple.share_price())  # before unrealized losses
print(rwa.adapters.maple.exit_price())   # after unrealized losses
```

### BUIDL holder data

```python
# Returns all registered wallet addresses
wallets = rwa.adapters.securitize.list_wallets("buidl")
print(f"{len(wallets)} BUIDL holders")
for addr in wallets[:10]:
    print(addr)
```

### Direct price reads

```python
rwa.adapters.ondo.usdy_price()    # 1.1290 (from RWADynamicOracle.getPriceData())
rwa.adapters.ondo.ousg_price()    # 114.85 (from OndoOracle.getAssetPrice())
rwa.adapters.maple.share_price()  # 1.1590 (from convertToAssets())
```

### Balance query

```python
balance = rwa.balance_of("USDY", "0xYourWallet")
print(balance)  # float, human-readable (raw / 10^decimals)
```

### Multi-chain

One instance per chain. Securitize BUIDL is deployed on Ethereum, Arbitrum, Polygon, and Avalanche:

```python
from rwa_sdk import RWAChain

eth = RWAChain(rpc_url="https://ethereum-rpc.publicnode.com")
arb = RWAChain(rpc_url="https://arbitrum-one-rpc.publicnode.com")

eth_tokens = eth.all_tokens()   # all 12 tokens
arb_tokens = arb.all_tokens()   # BUIDL on Arbitrum only

print(eth.chain_id)    # 1
print(arb.chain_id)    # 42161
print(eth.chain_name)  # Ethereum
```

### Custom adapters

```python
from rwa_sdk.protocols.base import ProtocolAdapter

class MyAdapter:
    protocol = "my_protocol"
    chain_id = 1

    def all_tokens(self): ...
    def can_transfer(self, token_address, from_addr, to_addr, value=0): ...

# Inject at construction or register after
rwa = RWAChain(rpc_url="...", adapters=[MyAdapter()])
# or
rwa.register_adapter(MyAdapter())
```

Adapters are validated against the `ProtocolAdapter` protocol at injection time. Missing `protocol`, `chain_id`, `all_tokens`, or `can_transfer` raises `TypeError` immediately.

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
token.price_source   # str | None (e.g. "RWADynamicOracle.getPriceData()")
token.tvl            # float | None
token.yield_type     # YieldType enum
token.protocol       # str
token.category       # Category | None (e.g. Category.US_TREASURY)
```

## License

MIT
