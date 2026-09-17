"""ChromaPeak Studio — 非 GUI 命令行版（桌面端无界面工具）。

用法：
  python -m desktop.cli analyze  data.csv --algorithms ALG-D ALG-E --out peaks.csv
  python -m desktop.cli batch   ./data_dir --out-dir out --algorithms ALG-D
  python -m desktop.cli project data.csv --out project.json
  python -m desktop.cli rerun   project.json --out peaks.csv

与 GUI 版共享同一份 core 算法包，适合服务器 / 批处理 / CI 场景。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from core.io import load_chromatogram, save_peaks_csv
from core.pipeline import analyze, available_algorithms, run_algorithms
from core.sample_data import synthetic_chromatogram


def _all_names() -> list:
    return [m["name"] for m in available_algorithms()]


def _write_csv(path: str, peaks: list):
    save_peaks_csv(peaks, path)
    print(f"  -> {path}  ({len(peaks)} peaks)")


def _write_xlsx(path: str, peaks: list):
    try:
        from openpyxl import Workbook
    except Exception:
        print("  [warn] 未安装 openpyxl，回退为 CSV")
        _write_csv(path.rsplit(".", 1)[0] + ".csv", peaks)
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Peaks"
    cols = ["index", "rt", "height", "area", "fwhm", "asymmetry", "score", "algorithm"]
    ws.append(cols)
    for pk in peaks:
        d = pk.to_dict() if hasattr(pk, "to_dict") else pk
        ws.append([d.get(c, "") for c in cols])
    wb.save(path)
    print(f"  -> {path}  ({len(peaks)} peaks)")


def cmd_analyze(args):
    if args.file and args.file.lower() == "sample":
        x, y = synthetic_chromatogram()
    else:
        x, y = load_chromatogram(args.file)
    algos = args.algorithms or _all_names()
    res = run_algorithms(x, y, algos)
    if args.json:
        print(json.dumps({"n_points": len(x),
                          "results": {k: len(v) for k, v in res["results"].items()}},
                         ensure_ascii=False, indent=2))
    for name, peaks in res["results"].items():
        print(f"[{name}] {len(peaks)} peaks")
        for pk in peaks[:20]:
            print(f"  rt={pk['rt']:.3f} h={pk['height']:.4f} "
                  f"area={pk['area']:.4f} fwhm={pk['fwhm']:.3f}")
    if args.out:
        all_peaks = [p for ps in res["results"].values() for p in ps]
        if args.out.lower().endswith(".xlsx"):
            _write_xlsx(args.out, all_peaks)
        else:
            _write_csv(args.out, all_peaks)


def cmd_batch(args):
    files = []
    for entry in os.listdir(args.folder):
        if entry.lower().endswith((".csv", ".txt")):
            files.append(os.path.join(args.folder, entry))
    if not files:
        print("未找到 csv/txt 文件")
        return
    os.makedirs(args.out_dir, exist_ok=True)
    algos = args.algorithms or _all_names()
    for f in files:
        try:
            x, y = load_chromatogram(f)
            res = run_algorithms(x, y, algos)
            base = os.path.splitext(os.path.basename(f))[0]
            out = os.path.join(args.out_dir, f"{base}_peaks.csv")
            _write_csv(out, [p for ps in res["results"].values() for p in ps])
        except Exception as e:  # noqa: BLE001
            print(f"  [skip] {f}: {e}")


def cmd_project(args):
    x, y = load_chromatogram(args.file) if args.file != "sample" \
        else synthetic_chromatogram()
    algos = args.algorithms or _all_names()
    res = run_algorithms(x, y, algos)
    project = {
        "version": 1,
        "algorithms": algos,
        "x": x.tolist() if hasattr(x, "tolist") else list(x),
        "y": y.tolist() if hasattr(y, "tolist") else list(y),
        "results": res["results"],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)
    print(f"项目已保存 -> {args.out}")


def cmd_rerun(args):
    with open(args.file, "r", encoding="utf-8") as f:
        project = json.load(f)
    x = project["x"]
    y = project["y"]
    algos = project.get("algorithms") or _all_names()
    res = run_algorithms(x, y, algos)
    all_peaks = [p for ps in res["results"].values() for p in ps]
    _write_csv(args.out, all_peaks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="ChromaPeak Studio CLI (非 GUI 版)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="分析单个文件")
    a.add_argument("file", help="csv/txt 路径，或 'sample' 使用示例数据")
    a.add_argument("--algorithms", nargs="*", help="算法名，默认全部")
    a.add_argument("--out", help="导出结果 (csv/xlsx)")
    a.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    a.set_defaults(func=cmd_analyze)

    b = sub.add_parser("batch", help="批量处理文件夹")
    b.add_argument("folder", help="包含 csv/txt 的文件夹")
    b.add_argument("--out-dir", required=True, help="输出目录")
    b.add_argument("--algorithms", nargs="*")
    b.set_defaults(func=cmd_batch)

    p = sub.add_parser("project", help="保存项目 JSON")
    p.add_argument("file", help="csv/txt 或 'sample'")
    p.add_argument("--algorithms", nargs="*")
    p.add_argument("--out", required=True, help="project.json 路径")
    p.set_defaults(func=cmd_project)

    r = sub.add_parser("rerun", help="从项目 JSON 重新分析")
    r.add_argument("file", help="project.json 路径")
    r.add_argument("--out", required=True, help="导出 peaks csv")
    r.set_defaults(func=cmd_rerun)

    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
