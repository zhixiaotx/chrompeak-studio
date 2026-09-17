"""Base definitions shared by all peak-detection algorithms.

Every algorithm subclasses :class:`PeakAlgorithm` and exposes a
``default_params()`` list so the desktop and web UIs can auto-generate a
parameter panel without knowing algorithm specifics.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class Peak:
    """A single detected chromatographic peak."""

    index: int = 0            # index in the (processed) signal array
    rt: float = 0.0           # retention time (x value) at the apex
    height: float = 0.0       # apex signal value (above baseline)
    area: float = 0.0         # integrated area
    left: int = -1            # left boundary index
    right: int = -1           # right boundary index
    fwhm: float = 0.0         # full width at half maximum
    asymmetry: float = 0.0    # asymmetry factor (tailing)
    score: float = 0.0        # confidence / quality score (0..1)
    algorithm: str = ""       # name of the detecting algorithm
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": int(self.index),
            "rt": float(self.rt),
            "height": float(self.height),
            "area": float(self.area),
            "left": int(self.left),
            "right": int(self.right),
            "fwhm": float(self.fwhm),
            "asymmetry": float(self.asymmetry),
            "score": float(self.score),
            "algorithm": self.algorithm,
            "extra": self.extra,
        }


@dataclass
class ParamSpec:
    """Describes a single tunable parameter for UI auto-generation."""

    key: str
    label: str
    type: str                     # "float" | "int" | "bool" | "choice"
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    help: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "default": self.default,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "choices": self.choices,
            "help": self.help,
        }


class PeakAlgorithm(ABC):
    """Abstract base class for all peak detectors."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def detect(self, x: np.ndarray, y: np.ndarray,
               params: Optional[Dict[str, Any]] = None) -> List[Peak]:
        """Detect peaks in signal ``y`` sampled at ``x``.

        Returns a list of :class:`Peak` (may be empty).
        """
        raise NotImplementedError

    def default_params(self) -> List[ParamSpec]:
        """Return the tunable parameters for this algorithm."""
        return []

    # ---- helpers shared by concrete algorithms ----

    @staticmethod
    def _resolve(params: Optional[Dict[str, Any]],
                 specs: List[ParamSpec]) -> Dict[str, Any]:
        """Merge user params over the algorithm defaults."""
        out: Dict[str, Any] = {s.key: s.default for s in specs}
        if params:
            for k, v in params.items():
                out[k] = v
        return out

    @staticmethod
    def _local_maxima(y: np.ndarray) -> np.ndarray:
        """Indices of strict local maxima."""
        y = np.asarray(y, float)
        if len(y) < 3:
            return np.array([], dtype=int)
        cand = np.where((y[1:-1] > y[:-2]) & (y[1:-1] > y[2:]))[0] + 1
        return cand

    @staticmethod
    def _baseline_segment(y: np.ndarray, lo: int, hi: int) -> float:
        """Estimate baseline as the minimum of the segment edges."""
        lo = max(0, lo)
        hi = min(len(y), hi)
        if lo >= hi:
            return 0.0
        edge = max(1, (hi - lo) // 10)
        left = y[lo: lo + edge]
        right = y[max(lo, hi - edge): hi]
        return float(min(np.min(left) if left.size else 0,
                         np.min(right) if right.size else 0))
