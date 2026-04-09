"""Oracle price freshness guard."""

import time

from rwa_sdk.core.exceptions import OracleStalenessError


def assert_price_fresh(timestamp: int, max_age_seconds: int = 3600) -> None:
    """Raise OracleStalenessError if *timestamp* is older than *max_age_seconds*.

    Args:
        timestamp: Unix timestamp (seconds) of the last oracle update.
        max_age_seconds: Maximum acceptable age in seconds. Defaults to 3600 (1 hour).

    Raises:
        ValueError: If *timestamp* is in the future or appears to be in milliseconds
            (greater than 1e12, which is year 33658 in unix seconds).
        OracleStalenessError: If the price data is older than *max_age_seconds*.
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
