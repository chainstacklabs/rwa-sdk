"""Oracle price freshness guard."""

import time

from rwa_sdk.core.exceptions import OracleStalenessError


def assert_price_fresh(timestamp: int, max_age_seconds: int = 3600) -> None:
    """Raise OracleStalenessError if *timestamp* is older than *max_age_seconds*."""
    age = int(time.time()) - timestamp
    if age > max_age_seconds:
        raise OracleStalenessError(timestamp=timestamp, age_seconds=age, max_age_seconds=max_age_seconds)
