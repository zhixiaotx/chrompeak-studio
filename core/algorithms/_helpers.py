"""Shared helpers for peak-detection algorithms."""
from __future__ import annotations

from typing import List

import numpy as np


def enforce_min_distance(indices: List[int], y: np.ndarray,
                         min_distance: int) -> List[int]:
    """Keep the highest peak among any group closer than ``min_distance``."""
    if min_distance <= 0 or not indices:
        return list(indices)
    idx = sorted(indices, key=lambda i: y[i], reverse=True)
    kept: List[int] = []
    for i in idx:
        if all(abs(i - k) >= min_distance for k in kept):
            kept.append(i)
    return sorted(kept)


def refine_apex(y: np.ndarray, i: int, window: int = 3) -> int:
    """Return the local-maximum index near ``i`` within ``window``."""
    lo = max(0, i - window)
    hi = min(len(y), i + window + 1)
    seg = y[lo:hi]
    return lo + int(np.argmax(seg))


def peak_boundaries(y: np.ndarray, apex: int, base: float,
                    height: float, min_distance: int):
    """Walk left/right from ``apex`` until the signal returns to baseline.

    Returns ``(left, right)`` indices.
    """
    n = len(y)
    thr = base + 0.05 * height
    left = apex
    while left > 0:
        if y[left] <= thr:
            break
        # stop if we hit the start or a rising edge far away
        left -= 1
        if apex - left > max(min_distance * 3, 50):
            break
    right = apex
    while right < n - 1:
        if y[right] <= thr:
            break
        right += 1
        if right - apex > max(min_distance * 3, 50):
            break
    return left, right


def local_baseline(y: np.ndarray, lo: int, hi: int) -> float:
    """Minimum of the segment edges (used as the local baseline)."""
    lo = max(0, lo)
    hi = min(len(y), hi)
    if lo >= hi:
        return 0.0
    edge = max(1, (hi - lo) // 8)
    left = y[lo:lo + edge]
    right = y[max(lo, hi - edge):hi]
    return float(min(np.min(left) if left.size else 0,
                     np.min(right) if right.size else 0))
