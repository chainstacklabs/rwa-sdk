"""Oracle price freshness guard."""

import time

from rwa_sdk.core.exceptions import OracleStalenessError


def assert_price_fresh(timestamp: int, max_age_seconds: int = 3600) -> None:
    """Raise OracleStalenessError if the price timestamp is older than max_age_seconds.

    Raises:
        ValueError: If timestamp is in the future or appears to be milliseconds
            (value greater than 1e12).
        OracleStalenessError: If the price data is older than max_age_seconds.
    """
    now = int(time.time())
    if timestamp > 1_000_000_000_000:
        raise ValueError(
            f"timestamp {timestamp} looks like milliseconds — pass seconds instead"
        )
    if timestamp > now:
        raise ValueError(f"timestamp {timestamp} is in the future (now={now})")
    age = now - timestamp
    if age > max_age_seconds:
        raise OracleStalenessError(
            timestamp=timestamp, age_seconds=age, max_age_seconds=max_age_seconds
        )
