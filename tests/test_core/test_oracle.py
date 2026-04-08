"""Tests for core.oracle."""

import time

import pytest

from rwa_sdk.core.exceptions import OracleStalenessError
from rwa_sdk.core.oracle import assert_price_fresh


def test_fresh_price_passes() -> None:
    assert_price_fresh(int(time.time()) - 60)


def test_stale_price_raises() -> None:
    stale_ts = int(time.time()) - 7200
    with pytest.raises(OracleStalenessError) as exc_info:
        assert_price_fresh(stale_ts, max_age_seconds=3600)
    err = exc_info.value
    assert err.timestamp == stale_ts
    assert err.age_seconds >= 7200
    assert err.max_age_seconds == 3600


def test_custom_max_age() -> None:
    assert_price_fresh(int(time.time()) - 10, max_age_seconds=30)

    with pytest.raises(OracleStalenessError):
        assert_price_fresh(int(time.time()) - 31, max_age_seconds=30)
