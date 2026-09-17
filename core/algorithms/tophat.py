"""ALG-M: morphological top-hat peak detector (grey opening)."""
from __future__ import annotations

from typing import List, Optional

import numpy as np
from scipy.ndimage import grey_opening

from .base import ParamSpec, Peak, PeakAlgorithm
from ._helpers import (enforce_min_distance, local_baseline,
                       peak_boundaries, refine_apex)


class TopHatAlgorithm(PeakAlgorithm):
    name = "ALG-M"
    description = "形态学 Top-hat：原信号减开运算，突出局部波峰（对基线漂移鲁棒）。"

    def default_params(self) -> List[ParamSpec]:
        return [
            ParamSpec("structure", "结构元尺寸", "int", 21, 3, 101, 2,
                      help="开运算结构元窗口大小（越大越平滑）"),
            ParamSpec("top_thresh", "Top-hat 阈值", "float", 0.08, 0.0, 1.0, 0.01,
                      help="Top-hat 响应需超过最大响应的比例"),
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

        structure = int(p["structure"])
        if structure % 2 == 0:
            structure += 1
        ys = y.copy()
        opening = grey_opening(ys, size=structure)
        tophat = ys - opening

        top_thresh = float(p["top_thresh"])
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])

        tmax = float(np.max(tophat)) if tophat.size else 0.0
        if tmax <= 0:
            return []

        # candidate apex: local maxima of the top-hat response
        cand = []
        for i in range(1, n - 1):
            if tophat[i] > tophat[i - 1] and tophat[i] >= tophat[i + 1] \
               and tophat[i] >= top_thresh * tmax:
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
