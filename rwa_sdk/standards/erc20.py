"""ERC-20 base token reader."""

from rwa_sdk.infra.abi import load_abi
from rwa_sdk.infra.evm import EVMChainService


def get_erc20_contract(chain: EVMChainService, address: str):
    """Get an ERC-20 contract instance."""
    return chain.get_contract(address, load_abi("erc20"))


def read_token_metadata(chain: EVMChainService, address: str) -> dict:
    """Read basic ERC-20 metadata: name, symbol, decimals, totalSupply."""
    contract = get_erc20_contract(chain, address)
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
    contract = get_erc20_contract(chain, token_address)
    decimals = contract.functions.decimals().call()
    raw = contract.functions.balanceOf(chain.checksum(holder)).call()
    return raw / (10**decimals)
