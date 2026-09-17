"""ALG-W: continuous wavelet transform (Ricker) ridge peak detector.

Implemented manually (no PyWavelets dependency) so it runs on Python 3.13.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from .base import ParamSpec, Peak, PeakAlgorithm
from ._helpers import (enforce_min_distance, local_baseline,
                       peak_boundaries, refine_apex)


def _ricker(length: int, sigma: float) -> np.ndarray:
    """Normalised Ricker (Mexican hat) wavelet of given length."""
    if length % 2 == 0:
        length += 1
    t = np.arange(-(length // 2), length // 2 + 1)
    x = t / sigma
    psi = (1.0 - x ** 2) * np.exp(-x ** 2 / 2.0)
    s = np.sum(np.abs(psi))
    return psi / s if s > 0 else psi


def _cwt(y: np.ndarray, scales_samples: np.ndarray) -> np.ndarray:
    """Return CWT coefficients, shape (len(scales), n)."""
    n = len(y)
    coeffs = np.zeros((len(scales_samples), n))
    for si, s in enumerate(scales_samples):
        s = max(s, 1.0)
        half = int(min(round(10 * s), n // 2))
        if half < 1:
            half = 1
        psi = _ricker(2 * half + 1, s)
        c = np.convolve(y, psi, mode="same")
        coeffs[si] = c / s
    return coeffs


class CwtAlgorithm(PeakAlgorithm):
    name = "ALG-W"
    description = "CWT 小波脊线：多尺度 Ricker 小波最大响应定位峰，对噪声与重叠峰鲁棒。"

    def default_params(self) -> List[ParamSpec]:
        return [
            ParamSpec("min_scale", "最小尺度", "float", 0.05, 0.01, 2.0, 0.01,
                      help="最小小波尺度（秒）"),
            ParamSpec("max_scale", "最大尺度", "float", 0.6, 0.1, 3.0, 0.05,
                      help="最大小波尺度（秒）"),
            ParamSpec("num_scales", "尺度数量", "int", 24, 4, 80, 1,
                      help="参与脊线追踪的尺度个数"),
            ParamSpec("ridge_thresh", "脊线阈值", "float", 0.12, 0.0, 1.0, 0.01,
                      help="脊线强度需超过最大响应的比例"),
            ParamSpec("min_height", "最小峰高", "float", 0.05, 0.0, 5.0, 0.01,
                      help="峰高低于此值忽略"),
            ParamSpec("min_distance", "最小峰间距", "int", 8, 1, 200, 1,
                      help="相邻峰最小采样点间隔"),
        ]

    def detect(self, x: np.ndarray, y: np.ndarray,
               params: Optional[dict] = None) -> List[Peak]:
        p = self._resolve(params, self.default_params())
        y = np.asarray(y, float)
        x = np.asarray(x, float)
        n = len(y)
        if n < 5:
            return []

        dt = float(np.median(np.diff(x))) if n > 1 else 1.0
        dt = dt if dt > 0 else 1.0
        scales_samples = np.linspace(float(p["min_scale"]),
                                     float(p["max_scale"]),
                                     int(p["num_scales"])) / dt
        scales_samples = np.clip(scales_samples, 1.0, n // 2)

        coeffs = _cwt(y, scales_samples)
        ridge = np.max(coeffs, axis=0)

        ridge_thresh = float(p["ridge_thresh"])
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])

        rmax = float(np.max(ridge)) if ridge.size else 0.0
        if rmax <= 0:
            return []

        cand = []
        for i in range(1, n - 1):
            if ridge[i] > ridge[i - 1] and ridge[i] >= ridge[i + 1] \
               and ridge[i] >= ridge_thresh * rmax:
                cand.append(i)
        cand = [refine_apex(y, i, 2) for i in cand]
        cand = enforce_min_distance(cand, y, min_distance)

        peaks: List[Peak] = []
        for apex in cand:
            lo = max(0, apex - min_distance * 2)
            hi = min(n, apex + min_distance * 2)
            base = local_baseline(y, lo, hi)
            height = float(y[apex] - base)
            if height < min_height:
                continue
            left, right = peak_boundaries(y, apex, base, height, min_distance)
            area = float(np.trapezoid(y[left:right + 1] - base, x[left:right + 1]))
            pk = Peak(index=int(apex), rt=float(x[apex]), height=height,
                      area=area, left=int(left), right=int(right),
                      algorithm=self.name)
            pk.score = min(1.0, height / (height + min_height))
            peaks.append(pk)
        return peaks
