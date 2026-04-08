"""SDK-specific exception hierarchy."""


class RWASDKError(Exception):
    """Base exception for all rwa-sdk errors."""


class OracleStalenessError(RWASDKError):
    """Raised when a price oracle's last update is older than the allowed window.

    Attributes:
        timestamp: Unix timestamp of the last oracle update.
        age_seconds: How old the data is (now - timestamp).
        max_age_seconds: The freshness threshold that was exceeded.
    """

    def __init__(self, timestamp: int, age_seconds: int, max_age_seconds: int) -> None:
        self.timestamp = timestamp
        self.age_seconds = age_seconds
        self.max_age_seconds = max_age_seconds
        super().__init__(
            f"Price data is stale: {age_seconds}s old, maximum allowed is {max_age_seconds}s "
            f"(last updated at unix timestamp {timestamp})"
        )


class RegistryError(RWASDKError):
    """Raised when a protocol, chain, or token is not found in the registry."""


class HttpError(RWASDKError):
    """Raised when an HTTP request fails (network error, non-2xx response, or bad JSON).

    Attributes:
        url: The URL that was requested.
        cause: The underlying exception.
    """

    def __init__(self, url: str, cause: Exception) -> None:
        self.url = url
        self.cause = cause
        super().__init__(f"HTTP request to {url!r} failed: {cause}")
