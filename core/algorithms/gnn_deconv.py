"""ALG-GNN: GNN-based peak deconvolution via ONNX Runtime.

If a trained ONNX model exists it is used to produce a per-point peak
probability heat map; otherwise the algorithm falls back to a robust
second-derivative detector so the pipeline never breaks.
"""
from __future__ import annotations

import os
from typing import List, Optional

import numpy as np

from .base import ParamSpec, Peak, PeakAlgorithm
from ._helpers import (enforce_min_distance, local_baseline,
                       peak_boundaries, refine_apex)


def _find_model() -> Optional[str]:
    cand = [
        os.environ.get("CHROMPEAK_GNN_ONNX"),
        os.path.join(os.path.dirname(__file__), "..", "..", "models", "gnn.onnx"),
        os.path.join(os.path.dirname(__file__), "..", "models", "gnn.onnx"),
    ]
    for c in cand:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def _graph_features(x: np.ndarray, y: np.ndarray):
    """Node features (N,3): normalised y, dy, d2y; chain kNN edges (k=4)."""
    y = np.asarray(y, float)
    n = len(y)
    dt = float(np.median(np.diff(x))) if n > 1 else 1.0
    dt = dt if dt > 0 else 1.0
    dy = np.gradient(y) / dt
    d2y = np.gradient(dy)
    fy = (y - np.mean(y)) / (np.std(y) + 1e-12)
    fdy = (dy - np.mean(dy)) / (np.std(dy) + 1e-12)
    fd2 = (d2y - np.mean(d2y)) / (np.std(d2y) + 1e-12)
    feats = np.stack([fy, fdy, fd2], axis=1).astype(np.float32)
    # kNN chain edges (each node linked to 4 nearest neighbours by index)
    k = 4
    src, dst = [], []
    for i in range(n):
        for j in range(1, k + 1):
            if i - j >= 0:
                src.append(i); dst.append(i - j)
            if i + j < n:
                src.append(i); dst.append(i + j)
    edge_index = np.array([src, dst], dtype=np.int64)
    return feats, edge_index


def _onnx_heat(session, feats: np.ndarray, edge_index: np.ndarray):
    from scipy.special import expit
    inputs = {"x": feats, "edge_index": edge_index}
    try:
        out = session.run(None, inputs)[0]
    except Exception:
        # some exports name the inputs differently
        out = session.run(None, {"input": feats, "edge_index": edge_index})[0]
    heat = out.reshape(-1)
    return expit(heat).astype(np.float32)  # squash to 0..1


class GnnDeconvAlgorithm(PeakAlgorithm):
    name = "ALG-GNN"
    description = "GNN 解卷积：图神经网络输出逐点峰概率热力，再经 EMG 精修；无模型时回退二阶导数。"

    def default_params(self) -> List[ParamSpec]:
        return [
            ParamSpec("heat_thresh", "热力阈值", "float", 0.5, 0.05, 0.99, 0.01,
                      help="GNN 热力值超过此比例视为峰（回退模式下用于二阶导阈值）"),
            ParamSpec("min_height", "最小峰高", "float", 0.05, 0.0, 5.0, 0.01,
                      help="峰高低于此值忽略"),
            ParamSpec("min_distance", "最小峰间距", "int", 8, 1, 200, 1,
                      help="相邻峰最小采样点间隔"),
        ]

    def _fallback(self, x, y, p) -> List[Peak]:
        """Second-derivative fallback detector."""
        from ..preprocess import savgol_smooth
        y = np.asarray(y, float)
        x = np.asarray(x, float)
        n = len(y)
        if n < 5:
            return []
        window = 15
        ys = savgol_smooth(y, window, 3) if n > window else y.copy()
        d2y = np.gradient(np.gradient(ys))
        dmax = float(np.max(np.abs(d2y))) if d2y.size else 0.0
        if dmax <= 0:
            return []
        # fallback uses a fixed fraction of the max |2nd deriv|; the ONNX
        # path keeps heat_thresh as a 0..1 probability cut-off
        thr = -0.2 * dmax
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])
        cand = []
        for i in range(1, n - 1):
            if d2y[i] < thr and d2y[i] < d2y[i - 1] and d2y[i] <= d2y[i + 1]:
                cand.append(i)
        cand = [refine_apex(ys, i, 3) for i in cand]
        cand = enforce_min_distance(cand, ys, min_distance)
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

    def detect(self, x: np.ndarray, y: np.ndarray,
               params: Optional[dict] = None) -> List[Peak]:
        p = self._resolve(params, self.default_params())
        y = np.asarray(y, float)
        x = np.asarray(x, float)
        n = len(y)
        if n < 5:
            return []

        model = _find_model()
        if model is None:
            return self._fallback(x, y, p)

        try:
            import onnxruntime as ort
        except Exception:
            return self._fallback(x, y, p)

        feats, edge_index = _graph_features(x, y)
        try:
            session = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
            heat = _onnx_heat(session, feats, edge_index)
        except Exception:
            return self._fallback(x, y, p)

        heat_thresh = float(p["heat_thresh"])
        min_height = float(p["min_height"])
        min_distance = int(p["min_distance"])

        cand = []
        for i in range(1, n - 1):
            if heat[i] > heat_thresh and heat[i] >= heat[i - 1] and heat[i] >= heat[i + 1]:
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
            pk.score = float(heat[apex])
            peaks.append(pk)
        return peaks
