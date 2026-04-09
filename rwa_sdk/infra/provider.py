"""RPC provider abstraction wrapping web3.py."""

from web3 import Web3


def create_rpc_provider(rpc_url: str | None = None) -> Web3:
    """Create a Web3 HTTPProvider from an RPC URL.

    Raises:
        ValueError: If rpc_url is None.
    """
    if rpc_url is None:
        raise ValueError(
            "rpc_url is required. Example: RWA(rpc_url='https://ethereum-mainnet.core.chainstack.com/YOUR_KEY')"
        )

    return Web3(Web3.HTTPProvider(rpc_url))
