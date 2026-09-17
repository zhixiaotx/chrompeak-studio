"""Input/output for chromatogram files (csv / txt)."""
from __future__ import annotations

import io
from typing import Tuple

import numpy as np
import pandas as pd


def _from_df(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] >= 2:
        x = numeric.iloc[:, 0].to_numpy(float)
        y = numeric.iloc[:, 1].to_numpy(float)
    elif numeric.shape[1] == 1:
        y = numeric.iloc[:, 0].to_numpy(float)
        x = np.arange(len(y), dtype=float)
    else:
        raise ValueError("未能在文件中找到数值列")
    # drop rows with nan
    mask = ~(np.isnan(x) | np.isnan(y))
    return x[mask], y[mask]


def load_chromatogram(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load (x, y) from a csv/txt file, auto-detecting the delimiter."""
    try:
        df = pd.read_csv(path, sep=None, engine="python", header=None)
        x, y = _from_df(df)
        if len(x) > 1:
            return x, y
    except Exception:
        pass
    df = pd.read_csv(path, sep=None, engine="python", header=0)
    return _from_df(df)


def load_from_bytes(data: bytes, filename: str = "") -> Tuple[np.ndarray, np.ndarray]:
    """Load (x, y) from raw bytes (e.g. an uploaded file)."""
    try:
        df = pd.read_csv(io.BytesIO(data), sep=None, engine="python", header=None)
        x, y = _from_df(df)
        if len(x) > 1:
            return x, y
    except Exception:
        pass
    df = pd.read_csv(io.BytesIO(data), sep=None, engine="python", header=0)
    return _from_df(df)


def save_peaks_csv(peaks, path: str) -> None:
    """Save a list of :class:`Peak` objects (or dicts) to a CSV file."""
    import csv
    cols = ["index", "rt", "height", "area", "fwhm", "asymmetry", "score", "algorithm"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for pk in peaks:
            d = pk.to_dict() if hasattr(pk, "to_dict") else pk
            w.writerow({c: d.get(c, "") for c in cols})
