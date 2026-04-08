"""Tests for core/exceptions.py."""

from rwa_sdk.core.exceptions import OracleStalenessError, RegistryError, RWASDKError


def test_oracle_staleness_error_fields_and_message():
    err = OracleStalenessError(timestamp=1_000_000, age_seconds=7200, max_age_seconds=3600)
    assert isinstance(err, RWASDKError)
    assert err.timestamp == 1_000_000
    assert err.age_seconds == 7200
    assert err.max_age_seconds == 3600
    assert "7200s old" in str(err)
    assert "3600s" in str(err)


def test_registry_error_message():
    err = RegistryError("ONDO not found on chain 42161")
    assert isinstance(err, RWASDKError)
    assert "ONDO" in str(err)
