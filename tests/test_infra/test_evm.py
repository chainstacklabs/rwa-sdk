"""Tests for infra.evm — EVMChainService."""

from unittest.mock import MagicMock


def test_default_evm_chain_service_reads_chain_id():
    from rwa_sdk.infra.evm import DefaultEVMChainService

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 1
    svc = DefaultEVMChainService(mock_w3)
    assert svc.chain_id == 1


def test_default_evm_chain_service_get_contract_checksums_address():
    from rwa_sdk.infra.evm import DefaultEVMChainService

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 1
    svc = DefaultEVMChainService(mock_w3)
    mock_contract = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract
    abi = [{"name": "foo"}]
    result = svc.get_contract("0xd8da6bf26964af9d7eed9e03e53415d37aa96045", abi)
    mock_w3.eth.contract.assert_called_once_with(
        address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        abi=abi,
    )
    assert result is mock_contract


def test_default_evm_chain_service_checksum_returns_eip55():
    from rwa_sdk.infra.evm import DefaultEVMChainService

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 1
    svc = DefaultEVMChainService(mock_w3)
    result = svc.checksum("0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
    assert result == "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


def test_evm_chain_service_satisfies_protocol():
    from rwa_sdk.infra.evm import DefaultEVMChainService, EVMChainService

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 1
    svc = DefaultEVMChainService(mock_w3)
    assert isinstance(svc, EVMChainService)
