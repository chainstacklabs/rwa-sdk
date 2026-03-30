"""ERC-4626 vault reader."""

from web3 import Web3
from web3.contract import Contract

from rwa_sdk.core.abi import combined_abi


def get_vault_contract(w3: Web3, address: str) -> Contract:
    """Get an ERC-4626 vault contract (includes ERC-20 functions)."""
    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=combined_abi("erc20", "erc4626"),
    )


def read_vault_data(w3: Web3, address: str) -> dict:
    """Read vault metadata: asset, totalAssets, share price."""
    contract = get_vault_contract(w3, address)
    decimals = contract.functions.decimals().call()
    total_supply_raw = contract.functions.totalSupply().call()
    total_assets_raw = contract.functions.totalAssets().call()

    one_share = 10**decimals
    share_price_raw = contract.functions.convertToAssets(one_share).call()
    share_price = share_price_raw / one_share

    asset_address = contract.functions.asset().call()

    return {
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": decimals,
        "asset": asset_address,
        "total_supply": total_supply_raw / (10**decimals),
        "total_assets_raw": total_assets_raw,
        "total_assets": total_assets_raw / (10**decimals),
        "share_price": share_price,
    }
