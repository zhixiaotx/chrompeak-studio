"""ALG-E: EMG model fitting and overlapping-peak deconvolution.

Fits an Exponentially Modified Gaussian to each detected peak (refining
height / area) and splits overlapping peaks using a two-EMG fit.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit
from scipy.special import erf

from .base import ParamSpec, Peak, PeakAlgorithm
from ._helpers import (enforce_min_distance, local_baseline, refine_apex)
from ..preprocess import baseline_correction, savgol_smooth


def _emg(t: np.ndarray, h: float, mu: float, sigma: float, tau: float) -> np.ndarray:
    sigma = max(abs(sigma), 1e-3)
    tau = max(abs(tau), 1e-3)
    z = (t - mu) / sigma
    expo = np.clip(0.5 * (sigma / tau) ** 2 - z * (sigma / tau), -50.0, 50.0)
    out = (h * sigma / tau) * np.sqrt(np.pi / 2.0)
    out = out * np.exp(expo)
    out = out * 0.5 * (1.0 + erf((z - sigma / tau) / np.sqrt(2.0)))
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    return out


def _emg2(t: np.ndarray, h1, mu1, s1, t1, h2, mu2, s2, t2) -> np.ndarray:
    return _emg(t, h1, mu1, s1, t1) + _emg(t, h2, mu2, s2, t2)


def _fit_single(xw: np.ndarray, yw: np.ndarray) -> Optional[Tuple]:
    h0 = float(np.max(yw)) if yw.size else 1.0
    mu0 = float(xw[int(np.argmax(yw))])
    s0 = max(float((xw[-1] - xw[0]) / 6.0), 1e-3)
    p0 = [h0, mu0, s0, s0 * 0.3]
    try:
        popt, _ = curve_fit(_emg, xw, yw, p0=p0, maxfev=20000,
                            bounds=([0, xw[0], 1e-3, 1e-4],
                                    [np.inf, xw[-1], np.inf, np.inf]))
        return tuple(popt)
    except Exception:
        return None


def _fit_double(xw: np.ndarray, yw: np.ndarray,
                mu_a: float, mu_b: float) -> Optional[Tuple]:
    h0 = float(np.max(yw)) / 2.0
    s0 = max(float((xw[-1] - xw[0]) / 8.0), 1e-3)
    p0 = [h0, mu_a, s0, s0 * 0.3, h0, mu_b, s0, s0 * 0.3]
    try:
        popt, _ = curve_fit(_emg2, xw, yw, p0=p0, maxfev=40000,
                            bounds=([0, xw[0], 1e-3, 1e-4,
                                     0, xw[0], 1e-3, 1e-4],
                                    [np.inf, xw[-1], np.inf, np.inf,
                                     np.inf, xw[-1], np.inf, np.inf]))
        return tuple(popt)
    except Exception:
        return None


class EmgAlgorithm(PeakAlgorithm):
    name = "ALG-E"
    description = "EMG 拟合：用指数修正高斯精修峰面积，并对重叠峰做双 EMG 解卷积分离。"

    def default_params(self) -> List[ParamSpec]:
        return [
            ParamSpec("min_height", "最小峰高", "float", 0.05, 0.0, 5.0, 0.01,
                      help="峰高低于此值忽略"),
            ParamSpec("min_distance", "最小峰间距", "int", 8, 1, 200, 1,
                      help="相邻峰最小采样点间隔"),
            ParamSpec("split_gap", "重叠判定间距", "float", 0.6, 0.1, 5.0, 0.1,
                      help="两峰 RT 间距小于此值尝试双 EMG 拆分"),
            ParamSpec("min_split_improve", "拆分提升阈值", "float", 0.3, 0.0, 1.0, 0.05,
                      help="双拟合 RSS 降低超过此比例才接受拆分"),
        ]

    def detect(self, x: np.ndarray, y: np.ndarray,
               params: Optional[dict] = None) -> List[Peak]:
        p = self._resolve(params, self.default_params())
        y = np.asarray(y, float)
        x = np.asarray(x, float)
        n = len(y)
        if n < 5:
            return []
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])
        split_gap = float(p["split_gap"])
        min_improve = float(p["min_split_improve"])

        # internally remove baseline so we work on a signal that sits on zero
        base_all = baseline_correction(y, 3, 10, 1e-4)
        yc = y - base_all
        ymax = float(np.max(yc)) if yc.size else 0.0
        if ymax <= 0:
            return []
        y = yc  # subsequent code operates on the baseline-corrected signal
        # light smoothing for robust coarse apex detection
        ys = savgol_smooth(y, 11, 3) if n > 11 else y.copy()
        ymax_s = float(np.max(ys)) if ys.size else ymax

        # coarse apexes via local maxima (absolute + relative threshold)
        cand = []
        for i in range(1, n - 1):
            if (ys[i] > ys[i - 1] and ys[i] >= ys[i + 1]
                    and ys[i] >= min_height and ys[i] >= 0.2 * ymax_s):
                cand.append(i)
        cand = [refine_apex(ys, i, 2) for i in cand]
        cand = enforce_min_distance(cand, ys, min_distance)
        if not cand:
            return []

        dt = float(np.median(np.diff(x))) if n > 1 else 1.0
        dt = dt if dt > 0 else 1.0
        gap_samples = max(1, int(round(split_gap / dt)))

        peaks: List[Peak] = []
        used = set()
        for idx, apex in enumerate(cand):
            if apex in used:
                continue
            lo = max(0, apex - min_distance * 2)
            hi = min(n, apex + min_distance * 2)
            base = local_baseline(y, lo, hi)
            # try merge with next close apex for overlap splitting
            next_apex = cand[idx + 1] if idx + 1 < len(cand) else None
            if next_apex is not None and (next_apex - apex) <= gap_samples:
                mlo = max(0, apex - min_distance * 2)
                mhi = min(n, next_apex + min_distance * 2)
                xw = x[mlo:mhi]
                yw = y[mlo:mhi] - local_baseline(y, mlo, mhi)
                fit2 = _fit_double(xw, yw, x[apex], x[next_apex])
                fit1 = _fit_single(xw, yw)
                if fit2 is not None:
                    rss2 = float(np.sum((yw - _emg2(xw, *fit2)) ** 2))
                    rss1 = float(np.sum((yw - _emg(xw, *fit1)) ** 2)) if fit1 else np.inf
                    if rss1 > 0 and (rss1 - rss2) / rss1 >= min_improve:
                        for k in range(2):
                            h, mu, s, t = fit2[k * 4:(k + 1) * 4]
                            if h < min_height:
                                continue
                            ai = int(np.argmin(np.abs(x - mu)))
                            area = float(np.trapezoid(_emg(x[mlo:mhi], h, mu, s, t),
                                                  x[mlo:mhi]))
                            pk = Peak(index=ai, rt=float(mu), height=float(h),
                                      area=area, algorithm=self.name)
                            pk.score = 1.0
                            peaks.append(pk)
                        used.add(apex)
                        used.add(next_apex)
                        continue
            # single EMG refine
            xw = x[lo:hi]
            yw = y[lo:hi] - base
            fit = _fit_single(xw, yw)
            if fit is None:
                continue
            h, mu, s, t = fit
            ai = int(np.argmin(np.abs(x - mu)))
            area = float(np.trapezoid(_emg(x[lo:hi], h, mu, s, t), x[lo:hi]))
            pk = Peak(index=ai, rt=float(mu), height=float(h), area=area,
                      left=int(lo), right=int(hi), algorithm=self.name)
            pk.score = 1.0
            peaks.append(pk)
            used.add(apex)

        peaks.sort(key=lambda pk: pk.rt)
        return peaks
