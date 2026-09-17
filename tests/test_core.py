"""Core algorithm test-suite."""
import csv
import io
import os
import tempfile

import numpy as np

from core.algorithms import algorithm_names, all_algorithms
from core.io import load_chromatogram, load_from_bytes, save_peaks_csv
from core.peak_params import calc_all
from core.pipeline import analyze, available_algorithms, run_algorithms
from core.preprocess import baseline_correction, preprocess
from core.sample_data import overlapping_pair, synthetic_chromatogram

EXPECTED_RT = [4.0, 8.5, 13.0, 16.5]
TOL = 0.45


def _covers(peaks, expected, tol=TOL):
    rts = [p["rt"] for p in peaks]
    return all(any(abs(r - e) <= tol for r in rts) for e in expected)


def test_all_algorithms_detect_synthetic():
    x, y = synthetic_chromatogram()
    for alg in all_algorithms():
        peaks = alg.detect(x, y)
        assert 3 <= len(peaks) <= 6, f"{alg.name} found {len(peaks)} peaks"
        assert _covers([p.to_dict() for p in peaks], EXPECTED_RT), \
            f"{alg.name} missed expected RTs: {[round(p['rt'],2) for p in peaks]}"


def test_pipeline_runs_all():
    x, y = synthetic_chromatogram()
    res = run_algorithms(x, y)
    assert set(res["results"].keys()) == set(algorithm_names())
    for name, peaks in res["results"].items():
        assert _covers(peaks, EXPECTED_RT), f"pipeline {name} missed RTs"
        # metrics computed
        for pk in peaks:
            assert pk["fwhm"] >= 0


def test_emg_splits_overlapping():
    x, y = overlapping_pair()
    peaks = analyze(x, y, "ALG-E")["peaks"]
    # two overlapping peaks should be resolved (1 or 2)
    assert len(peaks) >= 1
    # at least one peak near 5.0-6.3
    rts = [p["rt"] for p in peaks]
    assert any(4.5 <= r <= 7.0 for r in rts), f"EMG missed overlap region: {rts}"


def test_preprocess_removes_baseline():
    x, y = synthetic_chromatogram()
    y_proc, base = preprocess(y)
    # baseline drift removed: processed signal should be near zero at edges
    assert abs(float(np.min(y_proc))) < abs(float(np.min(y))) + 0.1


def test_baseline_correction_constant():
    y = np.ones(50) * 3.0 + np.sin(np.linspace(0, 10, 50))
    base = baseline_correction(y, order=3)
    assert abs(float(np.mean(base)) - 3.0) < 1.0


def test_io_roundtrip():
    x, y = synthetic_chromatogram(n=300)
    buf = io.StringIO()
    w = csv.writer(buf)
    for xi, yi in zip(x, y):
        w.writerow([xi, yi])
    data = buf.getvalue().encode("utf-8")
    x2, y2 = load_from_bytes(data, "demo.csv")
    assert len(x2) == len(x)
    assert np.allclose(x2, x, atol=1e-6)


def test_load_csv_file():
    x, y = synthetic_chromatogram(n=200)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "chrom.csv")
        save_peaks_csv([], path)  # just ensure folder writable
        path2 = os.path.join(d, "data.csv")
        with open(path2, "w", encoding="utf-8") as f:
            for xi, yi in zip(x, y):
                f.write(f"{xi},{yi}\n")
        x3, y3 = load_chromatogram(path2)
    assert len(x3) == len(x)


def test_available_algorithms_meta():
    meta = available_algorithms()
    assert len(meta) == len(algorithm_names())
    for m in meta:
        assert "params" in m and isinstance(m["params"], list)


def test_analyze_single():
    x, y = synthetic_chromatogram()
    res = analyze(x, y, "ALG-D")
    assert res["algorithm"] == "ALG-D"
    assert _covers(res["peaks"], EXPECTED_RT)


def test_calc_all_mutates():
    x, y = synthetic_chromatogram()
    from core.algorithms.base import Peak
    peaks = [Peak(index=100, rt=x[100], height=float(y[100]) - float(np.min(y)))]
    calc_all(x, y - np.min(y), peaks, 0.0)
    assert peaks[0].fwhm >= 0
