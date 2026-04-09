"""ERC-4626 vault reader."""

from rwa_sdk.infra.abi import combined_abi
from rwa_sdk.infra.evm import EVMChainService


def get_vault_contract(chain: EVMChainService, address: str):
    """Get an ERC-4626 vault contract (includes ERC-20 functions)."""
    return chain.get_contract(address, combined_abi("erc20", "erc4626"))


def read_vault_data(chain: EVMChainService, address: str) -> dict:
    """Read vault metadata: asset, totalAssets, share price."""
    contract = get_vault_contract(chain, address)
    decimals = contract.functions.decimals().call()
    total_supply_raw = contract.functions.totalSupply().call()
    total_assets_raw = contract.functions.totalAssets().call()
    one_share = 10**decimals
    share_price_raw = contract.functions.convertToAssets(one_share).call()
    asset_address = contract.functions.asset().call()
    return {
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": decimals,
        "asset": asset_address,
        "total_supply": total_supply_raw / (10**decimals),
        "total_assets_raw": total_assets_raw,
        "total_assets": total_assets_raw / (10**decimals),
        "share_price": share_price_raw / one_share,
    }
