"""统一视觉层：深色 QSS 主题 + 算法编号/配色映射。

与前端 web/frontend/src/theme.ts 保持一致——改色时两端一起改。
"""
from __future__ import annotations

# ---------------- 色板 ----------------
BG = "#14161a"          # 窗口底色
PANEL = "#1c1f24"       # 面板
PANEL_2 = "#22262c"     # 次级面板 / 输入框
ELEV = "#2a3038"        # 悬浮 / 选中
BORDER = "#2f353d"      # 边框
TEXT = "#d7dce3"        # 主文字
TEXT_DIM = "#8b949e"    # 次级文字
ACCENT = "#2f7ff4"      # 主色（选中行 / 高亮）
OK = "#3fb950"
WARN = "#d29922"
DANGER = "#f85149"

# 图表配色
PLOT_BG = "#191d23"
PLOT_GRID = "#252a32"
PLOT_AXIS = "#8b949e"
PLOT_RAW = "#98a2b3"
PLOT_PROC = "#e8eaed"

# ---------------- 算法视觉 ----------------
ALG_VISUALS = {
    "ALG-D": ("ALG-D", "导数法（一阶导数过零）", "#3b82f6"),
    "ALG-E": ("ALG-E", "指数修正高斯拟合", "#ef4444"),
    "ALG-W": ("ALG-W", "CWT 小波变换", "#a855f7"),
    "ALG-M": ("ALG-M", "形态学 Top-Hat", "#22c55e"),
    "ALG-C": ("ALG-C", "曲率法（二阶导数）", "#f59e0b"),
    "ALG-GNN": ("ALG-GNN", "图神经网络解卷积", "#06b6d4"),
}


def alg_visual(name: str):
    """Return ``(code, label, color)`` for an algorithm name."""
    return ALG_VISUALS.get(name, (name, name, "#8b949e"))


def alg_label(name: str) -> str:
    return alg_visual(name)[1]


def alg_color(name: str) -> str:
    return alg_visual(name)[2]


# ---------------- 全局样式表 ----------------
QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 12px;
    color: {TEXT};
    outline: none;
}}

QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Root {{ background: {BG}; }}

/* ---------- 顶栏 ---------- */
QWidget#TopBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QLabel#AppTitle {{
    font-size: 13px;
    font-weight: 600;
    color: #e8eaed;
    padding-left: 4px;
}}
QLabel#AppSubtitle {{ color: {TEXT_DIM}; font-size: 11px; }}

QMenuBar {{
    background: transparent;
    padding: 0 4px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 4px;
    color: {TEXT_DIM};
}}
QMenuBar::item:selected {{ background: {ELEV}; color: {TEXT}; }}
QMenuBar::item:pressed {{ background: {ACCENT}; color: #fff; }}

QMenu {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 26px 6px 14px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #fff; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

/* ---------- 图标栏 ---------- */
QWidget#IconRail {{
    background: {PANEL};
    border-right: 1px solid {BORDER};
}}
QToolButton#RailBtn {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: {TEXT_DIM};
    padding: 8px 0 6px 0;
    font-size: 10px;
}}
QToolButton#RailBtn:hover {{ background: {PANEL_2}; color: {TEXT}; }}
QToolButton#RailBtn:checked {{
    background: {PANEL_2};
    color: {ACCENT};
    border-left: 2px solid {ACCENT};
}}

/* ---------- 面板 ---------- */
QWidget#Panel {{ background: {PANEL}; }}
QWidget#Card {{ background: {PANEL}; border: 1px solid {BORDER}; }}
QLabel#SectionTitle {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QLabel#Hint {{ color: {TEXT_DIM}; font-size: 11px; }}

/* ---------- 输入 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: #fff;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {ELEV};
    border: none;
    width: 14px;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 20px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {ELEV}; }}
QPushButton:pressed {{ background: {ACCENT}; color: #fff; }}
QPushButton:disabled {{ color: #5a636e; background: #1a1d22; }}
QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #fff;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: #4a91f7; }}
QPushButton#Link {{
    background: transparent;
    border: none;
    color: {ACCENT};
    padding: 2px 6px;
}}
QPushButton#Link:hover {{ color: #7fb2ff; text-decoration: underline; }}
QPushButton#RunBtn {{
    background: {ELEV};
    border: 1px solid {BORDER};
    padding: 2px 9px;
    font-size: 11px;
    min-height: 16px;
}}
QPushButton#RunBtn:hover {{ background: {ACCENT}; border-color: {ACCENT}; color: #fff; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: {PANEL_2};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    image: none;
}}

/* ---------- 列表 / 表格 ---------- */
QListWidget, QTreeWidget, QTableWidget {{
    background: {PANEL};
    border: none;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    alternate-background-color: #1f2429;
}}
QListWidget::item {{ padding: 5px 8px; border-bottom: 1px solid {BORDER}; }}
QListWidget::item:selected {{ background: {ACCENT}; }}
QListWidget::item:hover {{ background: {PANEL_2}; }}

QHeaderView::section {{
    background: {PANEL_2};
    color: {TEXT_DIM};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 5px 8px;
    font-weight: 600;
}}
QTableWidget::item {{ padding: 3px 8px; }}

/* ---------- 标签页 ---------- */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER};
    background: {PANEL};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
    background: {PANEL_2};
}}
QTabBar::tab:hover {{ color: {TEXT}; }}

/* ---------- 状态栏 ---------- */
QStatusBar {{
    background: {PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QStatusBar::item {{ border: none; }}
QLabel#StatusCell {{ color: {TEXT_DIM}; font-size: 11px; }}
QLabel#StatusCell b {{ color: {TEXT}; }}

/* ---------- 分割条 / 滚动条 ---------- */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QScrollBar:vertical {{
    background: {PANEL}; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #3a4149; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #4a525c; }}
QScrollBar:horizontal {{ background: {PANEL}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: #3a4149; border-radius: 5px; min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {PANEL_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 6px;
}}
"""


# ---------------- 字体 ----------------
#: 优先使用的中文字体（按顺序探测，取系统里第一个存在的）
FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Segoe UI",
    "PingFang SC",
    "Noto Sans CJK SC",
    "DejaVu Sans",
)

#: 备用字体文件（当 Qt 找不到系统字体库时，直接把这些文件注册进应用）
_FONT_FILES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def install_fonts(app) -> str:
    """注册字体并设置全局字体，返回最终选用的字体名。

    PyQt6 在部分精简运行环境（离屏渲染 / 打包后缺 fontconfig）下找不到系统字体库，
    界面文字会全部渲染成方块。这里显式加载字体文件兜底，保证中文可读。
    """
    import os

    from PyQt6.QtGui import QFont, QFontDatabase

    for path in _FONT_FILES:
        if os.path.exists(path):
            try:
                QFontDatabase.addApplicationFont(path)
            except Exception:  # noqa: BLE001
                pass

    families = set(QFontDatabase.families())
    chosen = "Sans Serif"
    for name in FONT_CANDIDATES:
        if name in families:
            chosen = name
            break

    font = QFont(chosen, 9)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    return chosen
