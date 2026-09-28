"""Small, well-behaved helpers used to check the analyzer does not invent problems."""

from collections.abc import Iterable


def chunked(items: list[int], size: int) -> Iterable[list[int]]:
    """Yield consecutive chunks of ``items`` with at most ``size`` elements."""
    if size < 1:
        raise ValueError("size must be >= 1")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def mean(values: list[float]) -> float:
    """Arithmetic mean; raises ValueError on an empty list."""
    if not values:
        raise ValueError("values must not be empty")
    return sum(values) / len(values)
