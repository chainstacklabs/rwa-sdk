"""Shared pytest fixtures for rwa-sdk tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_chain() -> MagicMock:
    """Mock EVMChainService. chain_id=1 (Ethereum) so all adapters initialise.
    Set mock_chain.get_contract.return_value = mock_contract per test.
    Set mock_chain.checksum.side_effect = lambda x: x when address dispatch is tested.
    """
    chain = MagicMock()
    chain.chain_id = 1
    return chain
