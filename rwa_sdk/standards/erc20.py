"""ERC-20 base token reader."""

from web3 import Web3
from web3.contract import Contract

from rwa_sdk.core.abi import load_abi


def get_erc20_contract(w3: Web3, address: str) -> Contract:
    """Get an ERC-20 contract instance."""
    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=load_abi("erc20"),
    )


def read_token_metadata(w3: Web3, address: str) -> dict:
    """Read basic ERC-20 metadata: name, symbol, decimals, totalSupply."""
    contract = get_erc20_contract(w3, address)
    decimals = contract.functions.decimals().call()
    raw_supply = contract.functions.totalSupply().call()
    return {
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": decimals,
        "total_supply_raw": raw_supply,
        "total_supply": raw_supply / (10**decimals),
    }


def read_balance(w3: Web3, token_address: str, holder: str) -> float:
    """Read token balance for a holder, scaled by decimals."""
    contract = get_erc20_contract(w3, token_address)
    decimals = contract.functions.decimals().call()
    raw = contract.functions.balanceOf(Web3.to_checksum_address(holder)).call()
    return raw / (10**decimals)
