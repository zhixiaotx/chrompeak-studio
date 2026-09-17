"""ALG-C: curvature (second-derivative) peak detector."""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..preprocess import savgol_smooth
from .base import ParamSpec, Peak, PeakAlgorithm
from ._helpers import (enforce_min_distance, local_baseline,
                       peak_boundaries, refine_apex)


class CurvatureAlgorithm(PeakAlgorithm):
    name = "ALG-C"
    description = "曲率法：Savitzky-Golay 平滑后取二阶导数，以负极大值（最凹）定位峰顶。"

    def default_params(self) -> List[ParamSpec]:
        return [
            ParamSpec("smooth", "平滑窗宽", "int", 15, 3, 101, 2,
                      help="Savitzky-Golay 窗宽（奇数）"),
            ParamSpec("curv_thresh", "曲率阈值", "float", 0.2, 0.0, 1.0, 0.01,
                      help="二阶导数负极小值需超过最大|二阶导|的比例"),
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

        window = int(p["smooth"])
        if window % 2 == 0:
            window += 1
        ys = savgol_smooth(y, window, 3) if window > 2 else y.copy()

        # second derivative (concave-down peak => strongly negative)
        d2y = np.gradient(np.gradient(ys))

        curv_thresh = float(p["curv_thresh"])
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])
        dmax = float(np.max(np.abs(d2y))) if d2y.size else 0.0
        if dmax <= 0:
            return []

        # candidate apex: local minima of d2y (most negative)
        cand = []
        for i in range(1, n - 1):
            if d2y[i] < -curv_thresh * dmax and d2y[i] < d2y[i - 1] and d2y[i] <= d2y[i + 1]:
                cand.append(i)
        cand = [refine_apex(ys, i, 3) for i in cand]
        cand = enforce_min_distance(cand, ys, min_distance)

        peaks: List[Peak] = []
        for apex in cand:
            lo = max(0, apex - min_distance * 2)
            hi = min(n, apex + min_distance * 2)
            base = local_baseline(ys, lo, hi)
            height = float(ys[apex] - base)
            if height < min_height:
                continue
            left, right = peak_boundaries(ys, apex, base, height, min_distance)
            area = float(np.trapezoid(ys[left:right + 1] - base, x[left:right + 1]))
            pk = Peak(index=int(apex), rt=float(x[apex]), height=height,
                      area=area, left=int(left), right=int(right),
                      algorithm=self.name)
            pk.score = min(1.0, height / (height + min_height))
            peaks.append(pk)
        return peaks
