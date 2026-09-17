"""Build standalone Windows executables with PyInstaller (no Python needed to run).

Run from the project root:  python desktop/build_desktop.py

Produces two executables under dist/:
  - ChromaPeakStudio.exe   (GUI 版, --windowed, 无控制台)
  - ChromaPeakCLI.exe      (非 GUI 版, 控制台命令行工具)

The bundled app finds ``core``/``models`` via ``sys._MEIPASS``.
"""
from __future__ import annotations

import os

import PyInstaller.__main__  # type: ignore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = os.pathsep  # ";" on Windows, ":" on macOS/Linux
CORE = f"{os.path.join(ROOT, 'core')}{SEP}core"
MODELS = f"{os.path.join(ROOT, 'models')}{SEP}models"

COMMON = [
    "--onedir",
    "--noconfirm",
    "--clean",
    "--add-data", CORE,
    "--add-data", MODELS,
    "--hidden-import", "scipy.special._ufuncs_cxx",
    "--hidden-import", "numpy",
    "--hidden-import", "scipy",
    "--collect-all", "core",
    "--collect-all", "pyqtgraph",
    "--collect-all", "onnxruntime",
]


def build_gui():
    entry = os.path.join(ROOT, "desktop", "main_window.py")
    PyInstaller.__main__.run([
        entry, "--name", "ChromaPeakStudio",
        "--windowed", *COMMON,
    ])
    print("[ok] GUI 可执行文件: dist/ChromaPeakStudio/ChromaPeakStudio.exe")


def build_cli():
    entry = os.path.join(ROOT, "desktop", "cli.py")
    PyInstaller.__main__.run([
        entry, "--name", "ChromaPeakCLI",
        "--console", *COMMON,
    ])
    print("[ok] 非 GUI 可执行文件: dist/ChromaPeakCLI/ChromaPeakCLI.exe")


def build():
    build_gui()
    build_cli()
    print("全部构建完成。可执行文件位于 dist/ 下，拷贝整个文件夹即可在没有 Python 的电脑上运行。")


if __name__ == "__main__":
    build()
