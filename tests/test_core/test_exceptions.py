"""Tests for core/exceptions.py."""

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError, RegistryError, RWASDKError


def test_rwa_sdk_error_is_exception():
    with pytest.raises(RWASDKError):
        raise RWASDKError("base error")


def test_oracle_staleness_error_is_rwa_sdk_error():
    err = OracleStalenessError(timestamp=1_000_000, age_seconds=7200, max_age_seconds=3600)
    assert isinstance(err, RWASDKError)
    assert err.timestamp == 1_000_000
    assert err.age_seconds == 7200
    assert err.max_age_seconds == 3600
    assert "7200s old" in str(err)
    assert "3600s" in str(err)


def test_registry_error_is_rwa_sdk_error():
    err = RegistryError("ONDO not found on chain 42161")
    assert isinstance(err, RWASDKError)
    assert "ONDO" in str(err)


def test_exception_hierarchy():
    """All SDK errors can be caught by their base class."""
    errors = [
        OracleStalenessError(0, 100, 50),
        RegistryError("missing"),
    ]
    for err in errors:
        assert isinstance(err, RWASDKError)
        assert isinstance(err, Exception)
