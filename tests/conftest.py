"""Shared pytest fixtures for rwa-sdk tests."""

import pytest
from unittest.mock import MagicMock

from web3 import Web3


@pytest.fixture
def mock_w3():
    """A MagicMock standing in for a Web3 instance."""
    return MagicMock(spec=Web3)
