"""Signal preprocessing: baseline correction and smoothing."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.signal import savgol_filter


@dataclass
class PreprocessOptions:
    """Options controlling the preprocessing pipeline."""

    baseline: bool = True
    baseline_order: int = 3
    baseline_iters: int = 10
    baseline_tol: float = 1e-4
    smooth: bool = True
    smooth_window: int = 11
    smooth_polyorder: int = 3

    @staticmethod
    def from_dict(d: Optional[dict]) -> "PreprocessOptions":
        if not d:
            return PreprocessOptions()
        return PreprocessOptions(
            baseline=bool(d.get("baseline", True)),
            baseline_order=int(d.get("baseline_order", 3)),
            baseline_iters=int(d.get("baseline_iters", 10)),
            baseline_tol=float(d.get("baseline_tol", 1e-4)),
            smooth=bool(d.get("smooth", True)),
            smooth_window=int(d.get("smooth_window", 11)),
            smooth_polyorder=int(d.get("smooth_polyorder", 3)),
        )


def _airpls_baseline(y: np.ndarray, order: int = 3,
                     max_iters: int = 10, tol: float = 1e-4) -> np.ndarray:
    """Asymmetric least squares baseline (Eilers & Boelens, airpls variant)."""
    n = len(y)
    if n < order + 2:
        return np.zeros(n)
    w = np.ones(n)
    z = y.copy()
    for _ in range(max_iters):
        # weighted polynomial fit
        coeffs = np.polyfit(np.arange(n), z, order)
        baseline = np.polyval(coeffs, np.arange(n))
        d = y - baseline
        # only penalise positive deviations (peaks sit above baseline)
        new_w = np.where(d > 0, 0.0, np.exp(-(d / (np.std(d) + 1e-12)) ** 2))
        if np.max(np.abs(new_w - w)) < tol:
            w = new_w
            break
        w = new_w
        z = w * y + (1 - w) * baseline
    coeffs = np.polyfit(np.arange(n), z, order)
    return np.polyval(coeffs, np.arange(n))


def baseline_correction(y: np.ndarray, order: int = 3,
                        max_iters: int = 10, tol: float = 1e-4) -> np.ndarray:
    """Return baseline estimate for signal ``y``."""
    return _airpls_baseline(np.asarray(y, float), order, max_iters, tol)


def savgol_smooth(y: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
    """Savitzky-Golay smoothing with a safe window size."""
    y = np.asarray(y, float)
    n = len(y)
    if window < 3 or n < window:
        return y
    if polyorder >= window:
        polyorder = window - 1
    return savgol_filter(y, window_length=window, polyorder=polyorder)


def preprocess(y: np.ndarray,
               opts: Optional[PreprocessOptions] = None,
               x: Optional[np.ndarray] = None):
    """Run the full preprocessing pipeline.

    Returns ``(y_proc, baseline)`` where ``y_proc = y - baseline`` (smoothed).
    """
    opts = opts or PreprocessOptions()
    y = np.asarray(y, float).copy()
    baseline = np.zeros_like(y)
    if opts.baseline:
        baseline = baseline_correction(y, opts.baseline_order,
                                       opts.baseline_iters, opts.baseline_tol)
        y = y - baseline
    if opts.smooth:
        y = savgol_smooth(y, opts.smooth_window, opts.smooth_polyorder)
    return y, baseline
