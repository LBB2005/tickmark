"""Binomial statistics for every reported rate.

Ported from the AEO Portfolio Index. Every gap between models is an interval,
not a bare point estimate: a number without one is an invitation to over-read.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

Z90 = 1.6448536269514722  # two-sided 90%


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float

    def excludes_zero(self) -> bool:
        return self.low > 0 or self.high < 0


def wilson(k: int, n: int, z: float = Z90) -> Interval:
    """Wilson score interval for a single proportion."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must be in [0, n]")
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    spread = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return Interval(p, max(0.0, centre - spread), min(1.0, centre + spread))


def _wilson_bounds(k: int, n: int, z: float) -> tuple[float, float]:
    interval = wilson(k, n, z)
    return interval.low, interval.high


def difference(k1: int, n1: int, k2: int, n2: int, z: float = Z90) -> Interval:
    """Newcombe's method 10 interval for p1 - p2."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = _wilson_bounds(k1, n1, z)
    l2, u2 = _wilson_bounds(k2, n2, z)
    delta = math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    epsilon = math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return Interval(p1 - p2, (p1 - p2) - delta, (p1 - p2) + epsilon)


def is_material(k1: int, n1: int, k2: int, n2: int, z: float = Z90) -> bool:
    """True only when the change clears the gate. Everything else is inconclusive."""
    return difference(k1, n1, k2, n2, z).excludes_zero()
