"""RPC provider abstraction wrapping web3.py."""

from web3 import Web3


def create_rpc_provider(rpc_url: str) -> Web3:
    """Create a Web3 HTTPProvider from an RPC URL."""
    return Web3(Web3.HTTPProvider(rpc_url))
