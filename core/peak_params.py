"""Quantitative peak metrics: FWHM and asymmetry factor."""
from __future__ import annotations

from typing import List

import numpy as np

from .algorithms.base import Peak


def _crossings(x: np.ndarray, s: np.ndarray, level: float, lo: int, hi: int):
    """Return (left_idx, right_idx) where signal ``s`` crosses ``level``."""
    seg = s[lo:hi + 1]
    idx = np.where(seg >= level)[0]
    if idx.size == 0:
        return None, None
    left = lo + idx[0]
    right = lo + idx[-1]
    return left, right


def calc_peak_params(x: np.ndarray, y: np.ndarray, peak: Peak,
                     baseline: float = 0.0) -> Peak:
    """Fill ``fwhm`` and ``asymmetry`` for a single peak (in place)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    s = y - baseline
    lo = peak.left if peak.left >= 0 else max(0, peak.index - 5)
    hi = peak.right if peak.right >= 0 else min(len(y) - 1, peak.index + 5)
    lo, hi = max(0, lo), min(len(y) - 1, hi)
    if lo >= hi:
        return peak

    half = 0.5 * peak.height
    left_c, right_c = _crossings(x, s, half, lo, hi)
    if left_c is not None and right_c is not None and right_c > left_c:
        peak.fwhm = float(x[right_c] - x[left_c])
        a = float(x[peak.index] - x[left_c])
        b = float(x[right_c] - x[peak.index])
        if a > 0:
            peak.asymmetry = float(b / a)
    else:
        # fallback: FWHM from a Gaussian approximation
        dt = float(np.median(np.diff(x))) if len(x) > 1 else 1.0
        if peak.height > 0 and np.std(s[lo:hi + 1]) > 0:
            peak.fwhm = float(2.355 * (peak.index if False else 1.0))  # placeholder
            peak.fwhm = float((hi - lo) * dt * 0.5)
        peak.asymmetry = 1.0
    return peak


def calc_all(x: np.ndarray, y: np.ndarray, peaks: List[Peak],
             baseline: float = 0.0) -> List[Peak]:
    """Compute metrics for a list of peaks."""
    for pk in peaks:
        calc_peak_params(x, y, pk, baseline)
    return peaks
