"""CLI demo: ``python -m core [--file path] [--algorithms ALG ...]``."""
from __future__ import annotations

import argparse
import json
import sys

from .io import load_chromatogram, save_peaks_csv
from .pipeline import run_algorithms, available_algorithms
from .sample_data import synthetic_chromatogram


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ChromaPeak core CLI")
    ap.add_argument("--file", help="chromatogram csv/txt path")
    ap.add_argument("--algorithms", nargs="*", help="algorithm names to run")
    ap.add_argument("--out", help="export detected peaks to CSV")
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    args = ap.parse_args(argv)

    if args.file:
        x, y = load_chromatogram(args.file)
    else:
        x, y = synthetic_chromatogram()

    res = run_algorithms(x, y, args.algorithms)

    if args.json:
        print(json.dumps({
            "n_points": len(x),
            "results": {k: len(v) for k, v in res["results"].items()},
        }))
    else:
        for name, peaks in res["results"].items():
            print(f"[{name}] {len(peaks)} peaks")
            for pk in peaks[:12]:
                print(f"  rt={pk['rt']:.3f}  h={pk['height']:.3f}  "
                      f"area={pk['area']:.3f}  fwhm={pk['fwhm']:.3f}  "
                      f"asym={pk['asymmetry']:.2f}")

    if args.out:
        # export the union of all detected peaks (one row per peak)
        all_peaks = []
        for peaks in res["results"].values():
            all_peaks.extend(peaks)
        save_peaks_csv(all_peaks, args.out)
        print(f"exported {len(all_peaks)} peaks -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
