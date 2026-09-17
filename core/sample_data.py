"""Synthetic chromatogram generation for demos and tests."""
from __future__ import annotations

import math
import numpy as np

# (retention_time, height, sigma, tau) for each synthetic peak
_DEFAULT_PEAKS = [
    (4.0, 1.00, 0.12, 0.020),
    (8.5, 0.60, 0.10, 0.015),
    (13.0, 0.85, 0.15, 0.030),
    (16.5, 0.40, 0.08, 0.010),
]


def _emg(t: np.ndarray, h: float, mu: float, sigma: float, tau: float) -> np.ndarray:
    """Exponentially Modified Gaussian (tailed peak)."""
    sigma = max(sigma, 1e-6)
    tau = max(tau, 1e-6)
    z = (t - mu) / sigma
    # numerically stable scaling + exponent (clip to avoid overflow/nan)
    expo = np.clip(0.5 * (sigma / tau) ** 2 - z * (sigma / tau), -50.0, 50.0)
    out = (h * sigma / tau) * np.sqrt(np.pi / 2.0) * np.exp(expo)
    out = out * 0.5 * (1.0 + _erf((z - sigma / tau) / np.sqrt(2.0)))
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    # suppress numerical garbage far on the rising side
    out = np.where(t < mu - 8 * sigma, 0.0, out)
    return out


def _erf(x: np.ndarray) -> np.ndarray:
    return np.vectorize(lambda v: math.erf(float(v)))(x)


def synthetic_chromatogram(n: int = 2000, t_min: float = 0.0, t_max: float = 20.0,
                           seed: int = 42, noise: float = 0.008,
                           peaks=None) -> tuple[np.ndarray, np.ndarray]:
    """Return (x, y) for a synthetic chromatogram with tailing peaks."""
    rng = np.random.default_rng(seed)
    t = np.linspace(t_min, t_max, n)
    y = 0.04 * t / t_max                      # slight upward drift
    y = y + 0.03 * np.sin(2 * np.pi * t / t_max)
    for rt, h, sigma, tau in (peaks or _DEFAULT_PEAKS):
        y = y + _emg(t, h, rt, sigma, tau)
    y = y + rng.normal(0.0, noise, n)
    return t, y


def overlapping_pair(n: int = 1500, t_min: float = 0.0, t_max: float = 14.0,
                     seed: int = 7, noise: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Two partially overlapping peaks for EMG deconvolution demo."""
    rng = np.random.default_rng(seed)
    t = np.linspace(t_min, t_max, n)
    y = 0.02 * t / t_max
    y = y + _emg(t, 0.9, 5.0, 0.18, 0.05) + _emg(t, 0.7, 6.3, 0.20, 0.06)
    y = y + rng.normal(0.0, noise, n)
    return t, y
