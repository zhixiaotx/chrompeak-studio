"""Build standalone Windows executables with PyInstaller (no Python needed to run).

Run from the project root:

    python desktop/build_desktop.py              # 两种模式都构建（默认）
    python desktop/build_desktop.py --mode onefile
    python desktop/build_desktop.py --mode onedir

Produces, per mode, a GUI build and a non-GUI build:

  ┌──────────┬──────────────────────────────────┬──────────────────┐
  │ 模式      │ 产物                              │ 特点              │
  ├──────────┼──────────────────────────────────┼──────────────────┤
  │ onedir   │ dist/ChromaPeakStudio/…exe       │ 秒开（~3s），      │
  │          │ dist/ChromaPeakCLI/…exe          │ 但要发整个文件夹    │
  │ onefile  │ dist/ChromaPeakStudio.exe        │ 只有一个文件，      │
  │          │ dist/ChromaPeakCLI.exe           │ 但启动慢（需解压）  │
  └──────────┴──────────────────────────────────┴──────────────────┘

**关于启动速度**：onefile 每次运行都要把上百 MB 的内置依赖解压到临时目录，
实测本机 CLI 启动约 25 s，而 onedir 仅约 3 s。所以对外分发推荐 onedir，
onefile 适合「只想要一个文件」的场景。

本脚本还有两条重要设计约束，都是踩坑之后定下来的：

1. **绝不让 CLI 版背上 GUI 的依赖。**
   早先 COMMON 里统一写了 ``--collect-all desktop``，而 ``desktop`` 包里含有
   ``main_window.py``（import PyQt6 / pyqtgraph），于是命令行版白白多打包了
   76 MB 的 PyQt6 + 5 MB 的 pyqtgraph，而 ``cli.py`` 从头到尾只用 ``core``。
   现在把 GUI 专属依赖拆到 ``GUI_EXTRA``，CLI 只拿 ``CLI_EXTRA``。

2. **仅在真的有 ONNX 模型时才打包 onnxruntime（约 41 MB）。**
   ``core/algorithms/gnn_deconv.py`` 是**惰性** import onnxruntime 的，且只在
   ``models/gnn.onnx`` 存在时才走推理分支；没有模型时它按设计回退到二阶导 +
   相对阈值，功能不受影响。所以仓库里没有模型就干脆不打包。
"""
from __future__ import annotations

import argparse
import os

import PyInstaller.__main__  # type: ignore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = os.pathsep  # ";" on Windows, ":" on macOS/Linux
CORE = f"{os.path.join(ROOT, 'core')}{SEP}core"
MODELS = f"{os.path.join(ROOT, 'models')}{SEP}models"
MODELS_DIR = os.path.join(ROOT, "models")


def has_onnx_model() -> bool:
    """models/ 下是否存在可用的 .onnx 模型。"""
    if not os.path.isdir(MODELS_DIR):
        return False
    return any(f.lower().endswith(".onnx") for f in os.listdir(MODELS_DIR))


# ---------------------------------------------------------------- 公共部分

COMMON = [
    "--noconfirm",
    "--clean",
    # 显式把项目根加入模块搜索路径：入口脚本里的 `from desktop import ...`
    # 与 `from core import ...` 都依赖它（否则冻结后运行会 ImportError）
    "--paths", ROOT,
    "--add-data", CORE,
    "--add-data", MODELS,
    "--hidden-import", "scipy.special._ufuncs_cxx",
    "--hidden-import", "numpy",
    "--hidden-import", "scipy",
    "--collect-all", "core",
]

# PyQt6 由 main_window.py 的 import 语句自动被分析进来；这里补的是
# pyqtgraph 的数据文件与 desktop 包内被动态引用的子模块。
GUI_EXTRA = [
    "--windowed",
    "--collect-all", "pyqtgraph",
    "--collect-all", "desktop",
    "--hidden-import", "desktop",
    "--hidden-import", "desktop.theme",
    "--hidden-import", "desktop.param_panel",
    "--hidden-import", "desktop.batch_dialog",
]

# 注意：**不要**加 --collect-all desktop / --collect-all pyqtgraph，
# 否则会把 PyQt6 拖进来（cli.py 完全用不到）。
CLI_EXTRA = [
    "--console",
    "--hidden-import", "desktop",
    "--collect-all", "openpyxl",      # CLI 的 --out xxx.xlsx 需要
]

MODES = {
    "onefile": "--onefile",
    "onedir": "--onedir",
}


def _common_with_onnx(mode: str) -> list:
    args = list(COMMON) + [MODES[mode]]
    if has_onnx_model():
        args += ["--collect-all", "onnxruntime"]
    return args


def build_gui(mode: str):
    entry = os.path.join(ROOT, "desktop", "main_window.py")
    PyInstaller.__main__.run([
        entry, "--name", "ChromaPeakStudio",
        *GUI_EXTRA, *_common_with_onnx(mode),
    ])
    where = ("dist/ChromaPeakStudio/ChromaPeakStudio.exe" if mode == "onedir"
             else "dist/ChromaPeakStudio.exe")
    print(f"[ok] GUI（{mode}）: {where}")


def build_cli(mode: str):
    entry = os.path.join(ROOT, "desktop", "cli.py")
    PyInstaller.__main__.run([
        entry, "--name", "ChromaPeakCLI",
        *CLI_EXTRA, *_common_with_onnx(mode),
    ])
    where = ("dist/ChromaPeakCLI/ChromaPeakCLI.exe" if mode == "onedir"
             else "dist/ChromaPeakCLI.exe")
    print(f"[ok] CLI（{mode}）: {where}")


def build(mode: str = "both"):
    modes = ["onedir", "onefile"] if mode == "both" else [mode]
    print("=" * 64)
    if has_onnx_model():
        print("检测到 models/*.onnx  —— 将一并打包 onnxruntime（约 41 MB）")
    else:
        print("models/ 下无 .onnx 模型 —— 跳过 onnxruntime（省约 41 MB/个）")
        print("  （ALG-GNN 会按设计回退到二阶导 + 相对阈值，功能不受影响）")
    print(f"构建模式: {', '.join(modes)}")
    print("=" * 64)
    for m in modes:
        print(f"\n---- 模式 {m} ----")
        build_gui(m)
        build_cli(m)
    print("\n全部构建完成。dist/ 下产物：")
    print("  onedir  → dist/ChromaPeakStudio/ 与 dist/ChromaPeakCLI/（拷贝整个文件夹）")
    print("  onefile → dist/ChromaPeakStudio.exe 与 dist/ChromaPeakCLI.exe（单文件）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="打包 ChromaPeak Studio 桌面端")
    ap.add_argument("--mode", default="both", choices=["both", "onefile", "onedir"],
                    help="构建模式（默认 both）")
    build(ap.parse_args().mode)

