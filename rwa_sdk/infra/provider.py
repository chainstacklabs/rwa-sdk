"""RPC provider abstraction wrapping web3.py."""

from web3 import Web3


def create_rpc_provider(rpc_url: str) -> Web3:
    """Create a Web3 HTTPProvider from an RPC URL."""
    if not rpc_url or not rpc_url.strip():
        raise ValueError("rpc_url must be a non-empty, non-whitespace string")
    return Web3(Web3.HTTPProvider(rpc_url))
