"""ALG-D: first-derivative zero-crossing peak detector."""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..preprocess import savgol_smooth
from .base import ParamSpec, Peak, PeakAlgorithm
from ._helpers import (enforce_min_distance, local_baseline,
                       peak_boundaries, refine_apex)


class DerivativeAlgorithm(PeakAlgorithm):
    name = "ALG-D"
    description = "一阶导数过零检峰：斜率阈值定位起点，一阶导过零+二阶导负定峰顶。"

    def default_params(self) -> List[ParamSpec]:
        return [
            ParamSpec("smooth", "平滑窗宽", "int", 15, 3, 101, 2,
                      help="Savitzky-Golay 窗宽（奇数），抑制噪声"),
            ParamSpec("slope_thresh", "斜率阈值", "float", 0.02, 0.0, 5.0, 0.01,
                      help="一阶导数绝对值需超过此值才视为峰"),
            ParamSpec("min_height", "最小峰高", "float", 0.05, 0.0, 5.0, 0.01,
                      help="峰高（相对基线）低于此值忽略"),
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

        # first derivative wrt x (physically scaled)
        dt = np.gradient(x)
        dt = np.where(dt == 0, np.nan, dt)
        dy = np.gradient(ys) / np.nan_to_num(dt, nan=1.0)
        # second derivative sign (concave down => peak)
        d2y = np.gradient(dy)

        slope_thresh = float(p["slope_thresh"])
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])

        # candidate apex: dy crosses + -> - AND concave down
        cand = []
        for i in range(1, n - 1):
            if dy[i - 1] >= 0 and dy[i] < 0 and d2y[i] < 0:
                if abs(dy[i]) >= slope_thresh or abs(dy[i - 1]) >= slope_thresh:
                    cand.append(i)
        cand = [refine_apex(ys, i, 2) for i in cand]
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
