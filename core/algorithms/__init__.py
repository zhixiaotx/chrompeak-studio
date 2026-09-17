"""Algorithm registry: instantiate and enumerate peak detectors."""
from __future__ import annotations

from typing import Dict, List, Type

from .base import Peak, PeakAlgorithm
from .derivative import DerivativeAlgorithm
from .cwt import CwtAlgorithm
from .tophat import TopHatAlgorithm
from .curvature import CurvatureAlgorithm
from .emg_fit import EmgAlgorithm
from .gnn_deconv import GnnDeconvAlgorithm

_REGISTRY: Dict[str, Type[PeakAlgorithm]] = {
    DerivativeAlgorithm.name: DerivativeAlgorithm,
    CwtAlgorithm.name: CwtAlgorithm,
    TopHatAlgorithm.name: TopHatAlgorithm,
    CurvatureAlgorithm.name: CurvatureAlgorithm,
    EmgAlgorithm.name: EmgAlgorithm,
    GnnDeconvAlgorithm.name: GnnDeconvAlgorithm,
}


def all_algorithms() -> List[PeakAlgorithm]:
    """Return one instance of every registered algorithm."""
    return [cls() for cls in _REGISTRY.values()]


def get_algorithm(name: str) -> PeakAlgorithm:
    return _REGISTRY[name]()


def algorithm_names() -> List[str]:
    return list(_REGISTRY.keys())


def algorithm_meta() -> List[dict]:
    """Metadata for UI: name, description, default params."""
    out = []
    for alg in all_algorithms():
        out.append({
            "name": alg.name,
            "description": alg.description,
            "params": [s.to_dict() for s in alg.default_params()],
        })
    return out


__all__ = [
    "Peak", "PeakAlgorithm", "ParamSpec",
    "all_algorithms", "get_algorithm", "algorithm_names", "algorithm_meta",
]
