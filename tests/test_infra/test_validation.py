"""Tests for infra.validation."""

import pytest


def test_checksum_address_valid_lowercase():
    from rwa_sdk.infra.validation import checksum_address

    result = checksum_address("0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
    assert result == "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


def test_checksum_address_already_checksummed():
    from rwa_sdk.infra.validation import checksum_address

    addr = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    assert checksum_address(addr) == addr


def test_checksum_address_invalid_raises_value_error():
    from rwa_sdk.infra.validation import checksum_address

    with pytest.raises(ValueError, match="Invalid EVM address"):
        checksum_address("not-an-address", "wallet")


def test_checksum_address_too_short_raises():
    from rwa_sdk.infra.validation import checksum_address

    with pytest.raises(ValueError, match="Invalid EVM address.*wallet"):
        checksum_address("0xdeadbeef", "wallet")
