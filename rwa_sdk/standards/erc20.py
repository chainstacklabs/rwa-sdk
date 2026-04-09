"""ERC-20 base token reader."""

from rwa_sdk.infra.abi import load_abi
from rwa_sdk.infra.evm import EVMChainService


def read_token_metadata(chain: EVMChainService, address: str) -> dict:
    """Read basic ERC-20 metadata: name, symbol, decimals, totalSupply."""
    contract = chain.get_contract(address, load_abi("erc20"))
    decimals = contract.functions.decimals().call()
    raw_supply = contract.functions.totalSupply().call()
    return {
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": decimals,
        "total_supply_raw": raw_supply,
        "total_supply": raw_supply / (10**decimals),
    }


def read_balance(chain: EVMChainService, token_address: str, holder: str) -> float:
    """Read token balance for a holder, scaled by decimals."""
    contract = chain.get_contract(token_address, load_abi("erc20"))
    decimals = contract.functions.decimals().call()
    raw = contract.functions.balanceOf(chain.checksum(holder)).call()
    return raw / (10**decimals)
