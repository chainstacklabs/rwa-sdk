"""ABI loader — reads JSON ABI files shipped with the package."""

import json
from functools import lru_cache
from pathlib import Path

ABI_DIR = Path(__file__).parent.parent / "abis"


@lru_cache(maxsize=32)
def _abi_text(name: str) -> str:
    return (ABI_DIR / f"{name}.json").read_text()


def load_abi(name: str) -> list:
    """Load an ABI by name (without .json extension).

    Returns a fresh list each call so callers may mutate without poisoning
    other consumers.
    """
    return json.loads(_abi_text(name))


def combined_abi(*names: str) -> list:
    """Merge multiple ABIs into one (e.g. erc20 + protocol-specific)."""
    merged = []
    for name in names:
        merged.extend(load_abi(name))
    return merged
