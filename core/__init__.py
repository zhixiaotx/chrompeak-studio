"""chrompeak-core: shared peak-detection library (desktop + web)."""
from __future__ import annotations

from .algorithms.base import Peak, PeakAlgorithm, ParamSpec
from .io import load_chromatogram, load_from_bytes, save_peaks_csv
from .peak_params import calc_peak_params, calc_all
from .pipeline import (analyze, run_algorithms, available_algorithms)
from .preprocess import PreprocessOptions, preprocess, baseline_correction

__version__ = "0.1.0"

__all__ = [
    "Peak", "PeakAlgorithm", "ParamSpec",
    "load_chromatogram", "load_from_bytes", "save_peaks_csv",
    "calc_peak_params", "calc_all",
    "analyze", "run_algorithms", "available_algorithms",
    "PreprocessOptions", "preprocess", "baseline_correction",
    "__version__",
]
