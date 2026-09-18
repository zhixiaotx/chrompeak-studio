"""Unified analysis pipeline: preprocess -> run algorithms -> metrics."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .algorithms import (algorithm_meta, all_algorithms, get_algorithm)
from .algorithms._helpers import dedup_identical_peaks
from .peak_params import calc_all
from .preprocess import PreprocessOptions, preprocess


def available_algorithms() -> List[dict]:
    """UI metadata: name, description, default params for every algorithm."""
    return algorithm_meta()


def analyze(x: np.ndarray, y: np.ndarray, algorithm: str,
            params: Optional[dict] = None,
            preprocess_opts: Optional[dict] = None,
            compute_metrics: bool = True) -> Dict:
    """Run a single algorithm and return its peaks (as dicts)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    opts = PreprocessOptions.from_dict(preprocess_opts)
    y_proc, baseline = preprocess(y, opts)
    alg = get_algorithm(algorithm)
    peaks = dedup_identical_peaks(alg.detect(x, y_proc, params or {}))
    if compute_metrics:
        calc_all(x, y_proc, peaks, 0.0)
    return {
        "algorithm": algorithm,
        "peaks": [pk.to_dict() for pk in peaks],
        "baseline": baseline.tolist(),
        "y_proc": y_proc.tolist(),
    }


def run_algorithms(x: np.ndarray, y: np.ndarray,
                   algorithms: Optional[List[str]] = None,
                   params: Optional[Dict[str, dict]] = None,
                   preprocess_opts: Optional[dict] = None,
                   compute_metrics: bool = True) -> Dict:
    """Run one or all algorithms and return a structured result.

    Returns a dict with keys: ``x``, ``y``, ``y_proc``, ``baseline``,
    ``results`` (algorithm name -> list of peak dicts).
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    opts = PreprocessOptions.from_dict(preprocess_opts)
    y_proc, baseline = preprocess(y, opts)

    if algorithms is None:
        algorithms = [a.name for a in all_algorithms()]
    params = params or {}

    results: Dict[str, List[dict]] = {}
    for name in algorithms:
        alg = get_algorithm(name)
        peaks = dedup_identical_peaks(alg.detect(x, y_proc, params.get(name, {})))
        if compute_metrics:
            calc_all(x, y_proc, peaks, 0.0)
        results[name] = [pk.to_dict() for pk in peaks]

    return {
        "x": x.tolist(),
        "y": y.tolist(),
        "y_proc": y_proc.tolist(),
        "baseline": baseline.tolist(),
        "results": results,
    }
