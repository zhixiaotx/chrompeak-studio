#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ChromaPeak Studio 发布打包脚本。

一条命令产出三个「可直接分发」的压缩包（互相独立、可按需取用）：

1. ChromaPeakStudio-src-<ver>.zip   纯源码包：完整项目代码，含 README、构建脚本、
                                     部署配置；不含 node_modules / venv / dist / build，
                                     体积小、可二次开发。
2. ChromaPeakStudio-web-<ver>.zip   静态站包：web/frontend/dist 的全部构建产物，
                                     解压后即为可直接托管（GitHub Pages / OSS / Nginx）
                                     的静态站点，ZIP 根目录就是站点根目录。
3. ChromaPeakStudio-exe-<ver>.zip   便携 exe 包：PyInstaller 产出的 GUI + CLI 两个
                                     onedir 目录，解压即用，目标机器无需安装 Python。

用法：
    python package_release.py                # 打全部三个包
    python package_release.py --only src     # 只打源码包（可逗号分隔 src,web,exe）
    python package_release.py --out-dir D:/out

设计约定：
- **只读源目录、只写 release/，从不删除任何已有文件**（重名包自动加时间戳后缀，不覆盖）。
- 每个包内都放一份 `RELEASE_MANIFEST.txt`，写明包内容、构建来源与验证步骤。
- 缺失前置产物（如 dist 未构建）时给出明确提示，而不是打出一个空包。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "release"

# ---------------------------------------------------------------- 排除规则

# 源码包要排除的目录名（出现在任意层级）
EXCLUDE_DIR_NAMES = {
    ".git",
    ".github",          # 保留：CI 配置属于源码，见下方 EXCLUDE_DIR_NAMES_REL 例外
    "node_modules",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    "release",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".ruff_cache",
    "exports",          # web/backend/exports 运行时输出
    "out",              # sample_data/out 运行时输出
}
# 上面把 .github 一起排除了，但它是源码的一部分，这里显式取消排除
EXCLUDE_DIR_NAMES.discard(".github")

# 源码包要排除的扩展名
EXCLUDE_SUFFIXES = {
    ".pyc", ".pyo", ".pyd",
    ".spec",            # PyInstaller 临时 spec，脚本每次重新生成
    ".db",              # chrompeak.db 运行时数据库
    ".log",
    ".zip",
    ".egg-info",
    ".tsbuildinfo",
}

# 源码包精确排除的文件名
EXCLUDE_FILES = {"build_desktop.log"}

# 单个文件体积上限（源码包内超过此值直接跳过，防止误打包大文件）
SRC_MAX_FILE_MB = 25


# ---------------------------------------------------------------- 工具函数


def read_version() -> str:
    """从 core/__init__.py 读取 __version__，失败则回退 0.0.0。"""
    init = ROOT / "core" / "__init__.py"
    if init.exists():
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return "0.0.0"


def should_skip_dir(rel: Path) -> bool:
    return any(part in EXCLUDE_DIR_NAMES for part in rel.parts)


def should_skip_file(rel: Path) -> bool:
    if rel.name in EXCLUDE_FILES:
        return True
    if rel.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    # 临时/备份目录（本仓库构建时用 _old_<hhmmss> 归档旧产物）
    if any(part.startswith("_old_") for part in rel.parts):
        return True
    return False


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0  # type: ignore[assignment]
    return f"{n} B"


def unique_path(path: Path) -> Path:
    """若目标已存在，附加时间戳后缀，绝不覆盖已有包。"""
    if not path.exists():
        return path
    stamp = time.strftime("%H%M%S")
    return path.with_name(f"{path.stem}_v{stamp}{path.suffix}")


def write_manifest(zf: zipfile.ZipFile, name: str, body: str) -> None:
    zf.writestr(name, body)


def zip_stats(zf_path: Path) -> tuple[int, int]:
    """返回 (条目数, 解压后总字节)。"""
    total = 0
    with zipfile.ZipFile(zf_path) as zf:
        infos = zf.infolist()
        total = sum(i.file_size for i in infos)
        return len(infos), total


# ---------------------------------------------------------------- 三种打包器


def build_src(version: str, out_dir: Path) -> Path | None:
    print("\n[1/3] 源码包 …")
    dst = unique_path(out_dir / f"ChromaPeakStudio-src-{version}.zip")
    count = 0
    skipped_big: list[str] = []

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            cur = Path(dirpath)
            rel_dir = cur.relative_to(ROOT)

            # 就地裁剪，os.walk 就不会进入被排除目录
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]

            for fn in filenames:
                rel = rel_dir / fn
                if rel_dir == Path("."):
                    rel = Path(fn)
                if should_skip_file(rel):
                    continue
                src = cur / fn
                try:
                    size = src.stat().st_size
                except OSError:
                    continue
                if size > SRC_MAX_FILE_MB * 1024 * 1024:
                    skipped_big.append(f"{rel} ({human(size)})")
                    continue
                zf.write(src, arcname=str(Path("chrompeak-studio") / rel))
                count += 1

        manifest = f"""ChromaPeak Studio — 源码包 (source distribution)
=================================================
版本        : {version}
生成时间    : {time.strftime('%Y-%m-%d %H:%M:%S')}
包内文件数  : {count}
根目录      : chrompeak-studio/

内容说明
--------
包含完整可编译源码：core/ 核心算法包、desktop/ 桌面端（PyQt6 GUI + CLI + 打包脚本）、
web/backend FastAPI 后端、web/frontend React 前端源码、tests/ 单元测试、
.github/workflows CI 配置、README.md 完整文档、sample_data/ 示例数据。

已排除（体积大或可再生）
------------------------
node_modules/  venv/  dist/  build/  release/  __pycache__/  .pytest_cache/
*.pyc  *.spec  *.log  *.db  web/frontend/dist/  sample_data/out/  web/backend/exports/

使用方式
--------
  # 1) 核心算法（无需任何界面依赖）
  pip install numpy scipy
  python -m core

  # 2) 桌面端 GUI / CLI
  pip install -r desktop/requirements.txt
  python -m desktop.main_window      # GUI
  python -m desktop.cli --help       # CLI

  # 3) 打包成 exe（目标机免装 Python）
  python desktop/build_desktop.py

  # 4) Web 端
  cd web/frontend && npm install && npm run dev
  cd web/backend  && pip install -r requirements.txt && uvicorn main:app --reload

验证步骤
--------
  1. pip install -r desktop/requirements.txt
  2. python -m pytest -q          # 期望全部通过
  3. python -m core               # 期望打印 6 种算法各自的峰数
"""
        # 与包内其余内容同级，保证解压后只有一个顶层目录
        write_manifest(zf, "chrompeak-studio/RELEASE_MANIFEST.txt", manifest)

    return dst


def build_web(version: str, out_dir: Path) -> Path | None:
    print("\n[2/3] 静态站包 …")
    dist = ROOT / "web" / "frontend" / "dist"
    if not dist.is_dir() or not (dist / "index.html").exists():
        print("  ! 未找到 web/frontend/dist/index.html —— 请先构建前端：")
        print("      cd web/frontend && npm install && npm run build")
        return None

    dst = unique_path(out_dir / f"ChromaPeakStudio-web-{version}.zip")
    count = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, _dirnames, filenames in os.walk(dist):
            for fn in filenames:
                src = Path(dirpath) / fn
                rel = src.relative_to(dist)
                # dist 内容直接放在 ZIP 根目录 → 解压即站点根目录
                zf.write(src, arcname=str(rel))
                count += 1

        assets = sorted(p.name for p in (dist / "assets").glob("*")) if (dist / "assets").is_dir() else []
        manifest = f"""ChromaPeak Studio — 静态站包 (static site bundle)
=================================================
版本        : {version}
生成时间    : {time.strftime('%Y-%m-%d %H:%M:%S')}
包内文件数  : {count}（含本清单）
站点根目录  : 本 ZIP 的根目录（index.html 在最外层，可直接作为站点根）

内容说明
--------
由 Vite 构建的纯静态产物，含 index.html、assets/ 下的 JS / CSS、404.html。
资源引用一律使用相对路径（vite base = "./"），因此可部署在任意子路径下。

关键文件
--------
  index.html          入口页
  assets/{assets[0] if assets else '(js)'}   应用主包
  404.html            SPA 回退页

行为说明（重要）
----------------
**本静态包不包含后端**，部署后前端会自动进入「离线演示模式」：
算法在浏览器本地运行（web/frontend/src/analysis.ts 的 TS 实现），
支持分析 / 参数调优 / JSON 导入导出 / 本地保存项目 / 本地 ZIP 批量，
不会因为请求不存在的后端而报 404 / 405。若需云端账号与保存，请另行部署 web/backend。

部署方式（任选其一）
--------------------
  # GitHub Pages：把本包内容推到 gh-pages 分支即可
  # Nginx / OSS / COS：解压到站点根目录
  # 本地预览
  python -m http.server 8000

验证步骤
--------
  1. 解压后确认根目录存在 index.html
  2. python -m http.server 8000  → 浏览器打开 http://127.0.0.1:8000/
  3. 页面顶部应出现黄色「离线演示模式」提示条，色谱图正常出峰
  4. 拖动「平滑窗口 / 最小峰高」等参数，峰数应实时变化
"""
        write_manifest(zf, "RELEASE_MANIFEST.txt", manifest)

    return dst


def build_exe(version: str, out_dir: Path) -> Path | None:
    print("\n[3/3] 便携 exe 包 …")
    gui_dir = ROOT / "dist" / "ChromaPeakStudio"
    cli_dir = ROOT / "dist" / "ChromaPeakCLI"
    if not gui_dir.is_dir():
        print("  ! 未找到 dist/ChromaPeakStudio —— 请先打包：")
        print("      python desktop/build_desktop.py")
        return None

    dst = unique_path(out_dir / f"ChromaPeakStudio-exe-{version}.zip")
    count = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for label, base in (("ChromaPeakStudio", gui_dir), ("ChromaPeakCLI", cli_dir)):
            if not base.is_dir():
                print(f"  - 跳过 {label}（目录不存在）")
                continue
            for dirpath, _dirnames, filenames in os.walk(base):
                for fn in filenames:
                    src = Path(dirpath) / fn
                    rel = src.relative_to(base)
                    zf.write(src, arcname=str(Path(label) / rel))
                    count += 1

        manifest = f"""ChromaPeak Studio — 便携版 (Windows portable)
=================================================
版本        : {version}
生成时间    : {time.strftime('%Y-%m-%d %H:%M:%S')}
包内文件数  : {count}（含本清单）
解压后目录  :
  ChromaPeakStudio/ChromaPeakStudio.exe   图形界面版（无控制台窗口）
  ChromaPeakCLI/ChromaPeakCLI.exe         命令行版

目标机器无需安装 Python / 无需安装任何依赖，解压即用。
请保持各自目录内的 _internal/ 文件夹与 exe 同级，切勿只单独拷 exe。

使用方式
--------
  图形界面版：双击 ChromaPeakStudio/ChromaPeakStudio.exe
  命令行版  ：
    ChromaPeakCLI\\ChromaPeakCLI.exe analyze sample_data\\demo.csv --algorithms ALG-D ALG-E ALG-W
    ChromaPeakCLI\\ChromaPeakCLI.exe batch   data_dir --out-dir out --algorithms ALG-D
    ChromaPeakCLI\\ChromaPeakCLI.exe project data.csv --out project.json
    ChromaPeakCLI\\ChromaPeakCLI.exe rerun   project.json --out peaks.csv

命令行常用参数
--------------
  --algorithms  算法列表，取值 ALG-D / ALG-E / ALG-W / ALG-M / ALG-C / ALG-GNN
  --out         结果 CSV 输出路径
  --out-dir     批量模式输出目录

验证步骤
--------
  1. 解压本包到任意目录（建议路径不含中文与空格，避免个别环境编码问题）
  2. 双击 ChromaPeakStudio.exe，确认窗口正常显示、无报错弹窗、界面文字为正常中文（非方块）
  3. 在 cmd 中执行：
       ChromaPeakCLI\\ChromaPeakCLI.exe --help                 # 期望打印子命令帮助
       ChromaPeakCLI\\ChromaPeakCLI.exe analyze <某个CSV>       # 期望输出峰表
  4. 若 GUI 启动即崩溃，请检查杀毒软件是否隔离了 _internal 下的 dll

系统要求
--------
Windows 10 / 11 (x64)。首次启动可能稍慢（需解压内置依赖）。
"""
        write_manifest(zf, "RELEASE_MANIFEST.txt", manifest)

    return dst


# ---------------------------------------------------------------- 主流程

BUILDERS = {
    "src": ("源码包", build_src),
    "web": ("静态站包", build_web),
    "exe": ("便携 exe 包", build_exe),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ChromaPeak Studio 发布打包")
    ap.add_argument("--only", default="src,web,exe",
                    help="只打指定包，逗号分隔，可选 src / web / exe（默认全部）")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT), help="输出目录（默认 ./release）")
    args = ap.parse_args(argv)

    want = [k.strip() for k in args.only.split(",") if k.strip()]
    unknown = [k for k in want if k not in BUILDERS]
    if unknown:
        print(f"未知的包类型：{unknown}（可选：src / web / exe）", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = read_version()

    print("=" * 62)
    print(f"ChromaPeak Studio 发布打包  ·  version {version}")
    print(f"源目录 : {ROOT}")
    print(f"输出到 : {out_dir}")
    print(f"打包项 : {', '.join(want)}")
    print("=" * 62)

    results: list[tuple[str, Path, int, int]] = []
    for i, key in enumerate(("src", "web", "exe"), start=1):
        if key not in want:
            continue
        label, fn = BUILDERS[key]
        path = fn(version, out_dir)
        if path is None:
            print(f"  × {label} 跳过（缺少前置产物）")
            continue
        n, raw = zip_stats(path)
        results.append((label, path, n, raw))
        print(f"  √ {label} → {path.name}")
        print(f"      压缩后 {human(path.stat().st_size)} / 解压后约 {human(raw)} / {n} 个条目")

    print("\n" + "=" * 62)
    if results:
        print("完成，产物清单：")
        for label, path, n, raw in results:
            print(f"  · {path}")
        print(f"  （共 {len(results)} 个包，位于 {out_dir}）")
    else:
        print("没有生成任何包。")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
