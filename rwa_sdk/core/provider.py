"""RPC provider abstraction wrapping web3.py."""

from web3 import Web3


def create_provider(rpc_url: str | None = None) -> Web3:
    """Create a Web3 provider.

    An RPC URL is required. Pass a Chainstack endpoint or any Ethereum RPC URL.
    """
    if rpc_url is None:
        raise ValueError(
            "rpc_url is required. Example: RWA(rpc_url='https://ethereum-mainnet.core.chainstack.com/YOUR_KEY')"
        )

    return Web3(Web3.HTTPProvider(rpc_url))
