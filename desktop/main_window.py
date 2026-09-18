"""ChromaPeak Studio 桌面端主窗口（PyQt6 + pyqtgraph）。

界面与 Web 端保持一致：顶栏菜单 │ 左图标栏 │ 中央色谱图 │ 右算法/预处理/对比/日志/关于面板
│ 底部峰表/结果/文件信息 │ 状态栏。
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                            QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                            QHeaderView, QLabel, QLineEdit, QMainWindow,
                            QMessageBox, QPushButton, QScrollArea, QSizePolicy,
                            QSpinBox, QSplitter, QStackedWidget, QTabWidget,
                            QTableWidget, QTableWidgetItem, QTextBrowser,
                            QToolButton, QVBoxLayout, QWidget)

from core.algorithms import algorithm_meta
from core.io import load_chromatogram, save_peaks_csv
from core.pipeline import analyze, run_algorithms
from core.preprocess import PreprocessOptions
from core.sample_data import synthetic_chromatogram

from . import theme as T
from .batch_dialog import BatchDialog
from .param_panel import ParamPanel

RAIL_ITEMS = [
    ("algo", "算法", "SP_FileDialogDetailedView"),
    ("preprocess", "预处理", "SP_FileDialogContentsView"),
    ("compare", "对比", "SP_FileDialogListView"),
    ("log", "日志", "SP_FileDialogInfoView"),
    ("about", "关于", "SP_MessageBoxInformation"),
]

READOUT_QSS = (
    "background: rgba(28,31,36,0.92); border: 1px solid #2f353d;"
    "border-radius: 4px; padding: 3px 8px; color: #d7dce3;"
    "font-family: Consolas, monospace; font-size: 11px;"
)
LEGEND_QSS = (
    "QFrame#LegendBox { background: rgba(28,31,36,0.88);"
    " border: 1px solid #2f353d; border-radius: 5px; }"
)
CODE_QSS = (
    "border: 1px solid #2f353d; border-radius: 3px; padding: 0 5px;"
    " color: #8b949e; font-family: Consolas, monospace; font-size: 10px;"
)


# --------------------------------------------------------------------------- #
# 小部件
# --------------------------------------------------------------------------- #
class PlotLegend(QFrame):
    """贴合在图表左上角的可点选图例（点击切换曲线显隐）。"""

    toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LegendBox")
        self.setStyleSheet(LEGEND_QSS)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(6, 5, 6, 5)
        self._lay.setSpacing(1)
        self._items: dict[str, tuple[QToolButton, bool]] = {}

    @staticmethod
    def _dot(color: str) -> QIcon:
        pm = QPixmap(10, 10)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 8, 8)
        p.end()
        return QIcon(pm)

    def clear_items(self):
        while self._lay.count():
            it = self._lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        self._items.clear()

    def add_item(self, key: str, label: str, color: str):
        btn = QToolButton()
        btn.setText(label)
        btn.setIcon(self._dot(color))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QToolButton { border: none; padding: 2px 6px; text-align: left;"
            " color: #d7dce3; font-size: 11px; }"
            "QToolButton:hover { background: #2a3038; border-radius: 3px; }"
        )
        btn.clicked.connect(lambda _=False, k=key: self._toggle(k))
        self._lay.addWidget(btn)
        self._items[key] = (btn, True)

    def _toggle(self, key: str):
        btn, vis = self._items[key]
        vis = not vis
        self._items[key] = (btn, vis)
        btn.setStyleSheet(
            "QToolButton { border: none; padding: 2px 6px; text-align: left;"
            f" color: {'#d7dce3' if vis else '#5c646e'}; font-size: 11px; }}"
            "QToolButton:hover { background: #2a3038; border-radius: 3px; }"
        )
        self.toggled.emit(key, vis)

    def state(self) -> dict[str, bool]:
        return {k: v[1] for k, v in self._items.items()}


class AlgRow(QFrame):
    """右侧算法列表中的一行：勾选框 │ 色条+名称+编号 │ 执行 │ 峰数/耗时。"""

    rowSelected = pyqtSignal(str)
    rowToggled = pyqtSignal(str, bool)
    runOne = pyqtSignal(str)

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        code, label, color = T.alg_visual(name)
        self.name = name
        self.code = code
        self.color = color
        self.short_label = label.split("（")[0]
        self.active = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        head = QWidget()
        head.setObjectName("AlgRowHead")
        h = QHBoxLayout(head)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(6)

        self.check = QCheckBox()
        self.check.setChecked(True)
        self.check.stateChanged.connect(
            lambda _s: self.rowToggled.emit(self.name, self.check.isChecked()))
        h.addWidget(self.check)

        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background: {color}; border-radius: 2px;")
        h.addWidget(bar)

        self.name_lbl = QLabel(self.short_label)
        self.name_lbl.setToolTip(label)
        self.name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Preferred)
        h.addWidget(self.name_lbl, 1)

        self.code_lbl = QLabel(code)
        self.code_lbl.setStyleSheet(CODE_QSS)
        h.addWidget(self.code_lbl)

        self.run_btn = QPushButton("执行")
        self.run_btn.setObjectName("RunBtn")
        self.run_btn.setToolTip("只运行该算法并计时")
        self.run_btn.clicked.connect(lambda: self.runOne.emit(self.name))
        h.addWidget(self.run_btn)

        self.res_lbl = QLabel("待执行")
        self.res_lbl.setStyleSheet(
            "color: #8b949e; font-family: Consolas, monospace; font-size: 10px;")
        self.res_lbl.setFixedWidth(76)
        self.res_lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                                  | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self.res_lbl)

        root.addWidget(head)

        self.param_panel: ParamPanel | None = None
        self.param_host = QWidget()
        self.param_lay = QVBoxLayout(self.param_host)
        self.param_lay.setContentsMargins(34, 0, 10, 8)
        self.param_host.setVisible(False)
        root.addWidget(self.param_host)

        head.mousePressEvent = self._clicked  # type: ignore[assignment]

    def _clicked(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.rowSelected.emit(self.name)

    def set_active(self, active: bool):
        self.active = active
        self.setStyleSheet(
            "#AlgRowHead { background: rgba(47,127,244,0.16);"
            " border-left: 2px solid #2f7ff4; }" if active else
            "#AlgRowHead { background: transparent; border-left: 2px solid transparent; }"
        )
        if self.param_panel is not None:
            self.param_host.setVisible(active and self.check.isChecked())

    def bind_params(self, specs):
        if self.param_panel is None:
            self.param_panel = ParamPanel(specs)
            self.param_lay.addWidget(self.param_panel)
        else:
            self.param_panel.setVisible(True)

    def set_result(self, text: str, ok: bool | None):
        color = "#3fb950" if ok else "#f85149" if ok is False else "#8b949e"
        self.res_lbl.setText(text)
        self.res_lbl.setStyleSheet(
            f"color: {color}; font-family: Consolas, monospace; font-size: 10px;")


# --------------------------------------------------------------------------- #
# 主窗口
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChromaPeak Studio — 气相色谱峰识别算法测试平台")
        self.resize(1440, 920)

        self.x: np.ndarray | None = None
        self.y: np.ndarray | None = None
        self.y_proc: np.ndarray | None = None
        self.baseline: np.ndarray | None = None
        self.results: dict[str, list[dict]] = {}
        self.stats: dict[str, dict] = {}
        self.selected = ""
        self.last_ms: float | None = None
        self.file_name = ""
        self.logs: list[tuple[str, str, str]] = []

        self.show_raw = True
        self.show_proc = True
        self.show_markers = True
        self.cursor_on = True

        self.pre_opts = PreprocessOptions()

        self._rows: dict[str, AlgRow] = {}
        self._curves: dict[str, object] = {}
        self._marker_items: list[object] = []
        self._plot_cache: dict[str, np.ndarray] = {}

        # 防抖定时器必须在建 UI 之前就绪（构建算法列表时会连接它的 start）
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(240)
        self.debounce.timeout.connect(self.run_all)

        self._build_ui()
        self._build_menu()

        self.load_sample()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 状态栏必须先建：右侧算法面板构建时会回调 _update_alg_count()
        self._build_statusbar()

        outer.addWidget(self._build_rail())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1000, 340])
        outer.addWidget(splitter, 1)

        self.log("ChromaPeak Studio 已启动", "ok")

    # ---- 左图标栏 ----
    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("IconRail")
        rail.setFixedWidth(58)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(0)

        self.rail_buttons: dict[str, QToolButton] = {}
        for key, label, std in RAIL_ITEMS:
            btn = QToolButton()
            btn.setObjectName("RailBtn")
            btn.setText(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIcon(self.style().standardIcon(getattr(self.style().StandardPixmap, std)))
            btn.setIconSize(self._icon_size())
            btn.setFixedHeight(52)
            btn.clicked.connect(lambda _=False, k=key: self.show_panel(k))
            lay.addWidget(btn)
            self.rail_buttons[key] = btn
        lay.addStretch(1)
        self.rail_buttons["algo"].setChecked(True)
        return rail

    @staticmethod
    def _icon_size():
        from PyQt6.QtCore import QSize
        return QSize(18, 18)

    # ---- 中央：图 + 底部标签页 ----
    def _build_center(self) -> QWidget:
        center = QWidget()
        lay = QVBoxLayout(center)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.plot = pg.PlotWidget()
        self.plot.setBackground(T.PLOT_BG)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setLabel("bottom", "时间 / min")
        self.plot.setLabel("left", "响应")
        for ax_name in ("bottom", "left"):
            ax = self.plot.getAxis(ax_name)
            ax.setPen(pg.mkPen(T.PLOT_AXIS, width=1))
            ax.setTextPen(pg.mkPen(T.PLOT_AXIS))
        grid.addWidget(self.plot, 0, 0)

        self.legend = PlotLegend()
        self.legend.toggled.connect(self._on_legend_toggle)
        grid.addWidget(self.legend, 0, 0,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.readout = QLabel("—")
        self.readout.setStyleSheet(READOUT_QSS)
        self.readout.setVisible(False)
        grid.addWidget(self.readout, 0, 0,
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        lay.addWidget(host, 1)

        # 光标联动
        self.vline = None
        self.hline = None
        self.proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved,
                                    rateLimit=40, slot=self._on_mouse_move)

        lay.addWidget(self._build_bottom(), 0)
        return center

    def _build_bottom(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # ---- 峰表 ----
        peaks_page = QWidget()
        pv = QVBoxLayout(peaks_page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(0)

        bar = QWidget()
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(10, 5, 10, 5)
        bh.setSpacing(8)
        bh.addWidget(QLabel("来源"))
        self.src_combo = QComboBox()
        self.src_combo.setMinimumWidth(180)
        self.src_combo.currentIndexChanged.connect(lambda _i: self.refill_peak_table())
        bh.addWidget(self.src_combo)
        bh.addWidget(QLabel("筛选"))
        self.peak_search = QLineEdit()
        self.peak_search.setPlaceholderText("输入保留时间或算法编号…")
        self.peak_search.setMaximumWidth(240)
        self.peak_search.textChanged.connect(lambda _t: self.refill_peak_table())
        bh.addWidget(self.peak_search)
        bh.addStretch(1)
        self.peak_count_lbl = QLabel("共 0 个峰")
        self.peak_count_lbl.setObjectName("Hint")
        bh.addWidget(self.peak_count_lbl)
        pv.addWidget(bar)

        self.peak_table = QTableWidget(0, 11)
        self.peak_table.setHorizontalHeaderLabels(
            ["序号", "保留时间/min", "最小值/min", "峰高", "峰面积", "峰宽",
             "分离度 w/s", "不对称因子", "置信度", "来源算法", "标记"])
        self.peak_table.verticalHeader().setVisible(False)
        self.peak_table.setAlternatingRowColors(True)
        self.peak_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.peak_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.peak_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.peak_table.horizontalHeader().setStretchLastSection(True)
        pv.addWidget(self.peak_table, 1)
        self.tabs.addTab(peaks_page, "峰表")

        # ---- 结果（共识峰） ----
        res_page = QWidget()
        rv = QVBoxLayout(res_page)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        self.consensus_lbl = QLabel("共识峰：0")
        self.consensus_lbl.setObjectName("Hint")
        rv.addWidget(self.consensus_lbl)
        self.result_table = QTableWidget(0, 8)
        self.result_table.setHorizontalHeaderLabels(
            ["序号", "保留时间/min", "检出算法数", "离散度/min", "平均峰高",
             "平均置信度", "检出算法", "备注"])
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        rv.addWidget(self.result_table, 1)
        self.tabs.addTab(res_page, "结果")

        # ---- 文件信息 ----
        info_page = QWidget()
        iv = QVBoxLayout(info_page)
        iv.setContentsMargins(0, 0, 0, 0)
        self.info_table = QTableWidget(0, 2)
        self.info_table.setHorizontalHeaderLabels(["项目", "值"])
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.info_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.info_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        iv.addWidget(self.info_table, 1)
        self.tabs.addTab(info_page, "文件信息")

        return self.tabs

    # ---- 右侧面板 ----
    def _build_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget()
        hh = QHBoxLayout(head)
        hh.setContentsMargins(10, 7, 10, 7)
        self.panel_title = QLabel("算法")
        self.panel_title.setStyleSheet("font-weight: 600;")
        hh.addWidget(self.panel_title)
        hh.addStretch(1)
        self.panel_action = QPushButton("运行")
        self.panel_action.setObjectName("Link")
        self.panel_action.clicked.connect(self.run_all)
        hh.addWidget(self.panel_action)
        head.setStyleSheet("border-bottom: 1px solid #2f353d;")
        lay.addWidget(head)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_algo_page())
        self.stack.addWidget(self._build_preprocess_page())
        self.stack.addWidget(self._build_compare_page())
        self.stack.addWidget(self._build_log_page())
        self.stack.addWidget(self._build_about_page())
        lay.addWidget(self.stack, 1)
        return panel

    def _build_algo_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.alg_search = QLineEdit()
        self.alg_search.setPlaceholderText("搜索算法名称 / 编号…")
        self.alg_search.textChanged.connect(lambda _t: self.rebuild_alg_list())
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(10, 8, 10, 4)
        wl.addWidget(self.alg_search)
        lay.addWidget(wrap)

        sub = QWidget()
        sl = QHBoxLayout(sub)
        sl.setContentsMargins(10, 0, 10, 6)
        self.alg_count_lbl = QLabel("共 6 个 · 已选 6")
        self.alg_count_lbl.setObjectName("Hint")
        sl.addWidget(self.alg_count_lbl)
        sl.addStretch(1)
        b_all = QPushButton("全选")
        b_all.setObjectName("Link")
        b_all.clicked.connect(lambda: self.set_all_algorithms(True))
        b_none = QPushButton("全不选")
        b_none.setObjectName("Link")
        b_none.clicked.connect(lambda: self.set_all_algorithms(False))
        sl.addWidget(b_all)
        sl.addWidget(b_none)
        lay.addWidget(sub)

        self.alg_scroll = QScrollArea()
        self.alg_scroll.setWidgetResizable(True)
        self.alg_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.alg_host = QWidget()
        self.alg_lay = QVBoxLayout(self.alg_host)
        self.alg_lay.setContentsMargins(0, 0, 0, 0)
        self.alg_lay.setSpacing(0)
        self.alg_scroll.setWidget(self.alg_host)
        lay.addWidget(self.alg_scroll, 1)

        self.alg_foot = QLabel("")
        self.alg_foot.setWordWrap(True)
        self.alg_foot.setObjectName("Hint")
        self.alg_foot.setContentsMargins(10, 8, 10, 8)
        self.alg_foot.setStyleSheet(
            "border-top: 1px solid #2f353d; color: #8b949e; font-size: 11px;")
        lay.addWidget(self.alg_foot)

        self._metas = algorithm_meta()
        self._enabled: dict[str, bool] = {m["name"]: True for m in self._metas}
        self.selected = self._metas[0]["name"] if self._metas else ""
        self.rebuild_alg_list()
        return page

    def _build_preprocess_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self.pre_baseline = QCheckBox("基线校正（非对称最小二乘）")
        self.pre_baseline.setChecked(True)
        self.pre_baseline.stateChanged.connect(lambda _s: self._pre_changed())
        lay.addWidget(self.pre_baseline)

        self.pre_order = self._spin(1, 7, 3)
        lay.addWidget(self._field("多项式阶数", self.pre_order))
        self.pre_iters = self._spin(1, 50, 10)
        lay.addWidget(self._field("迭代次数", self.pre_iters))
        self.pre_tol = self._dspin(1e-6, 1e-2, 1e-4, 6, 1e-5)
        lay.addWidget(self._field("收敛容差", self.pre_tol))

        lay.addWidget(self._section("平滑"))
        self.pre_smooth = QCheckBox("Savitzky-Golay 平滑")
        self.pre_smooth.setChecked(True)
        self.pre_smooth.stateChanged.connect(lambda _s: self._pre_changed())
        lay.addWidget(self.pre_smooth)
        self.pre_win = self._spin(3, 101, 11, 2)
        lay.addWidget(self._field("窗口长度", self.pre_win))
        self.pre_poly = self._spin(1, 7, 3)
        lay.addWidget(self._field("多项式阶数", self.pre_poly))

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 6, 0, 0)
        btn = QPushButton("恢复默认")
        btn.clicked.connect(self._reset_preprocess)
        rl.addWidget(btn)
        rl.addStretch(1)
        lay.addWidget(row)

        lay.addStretch(1)
        note = QLabel(
            "基线校正采用非对称最小二乘（airPLS 变体），只惩罚低于基线的偏离，"
            "不会削掉真实峰；平滑在基线校正之后进行。改动任一参数会立即重算全部算法。")
        note.setWordWrap(True)
        note.setObjectName("Hint")
        lay.addWidget(note)
        return page

    def _build_compare_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.cmp_table = QTableWidget(0, 6)
        self.cmp_table.setHorizontalHeaderLabels(
            ["算法", "峰数", "耗时", "平均峰高", "不对称", "置信度"])
        self.cmp_table.verticalHeader().setVisible(False)
        self.cmp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cmp_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.cmp_table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.cmp_table, 1)
        note = QLabel(
            "峰数差异说明算法灵敏度不同——导数法偏保守，CWT 与 GNN 解卷积更容易拆出"
            "重叠峰；耗时反映计算代价。不对称因子接近 1 说明峰形对称，明显大于 1 表示拖尾。")
        note.setWordWrap(True)
        note.setObjectName("Hint")
        note.setContentsMargins(10, 8, 10, 8)
        note.setStyleSheet("border-top: 1px solid #2f353d; color: #8b949e;")
        lay.addWidget(note)
        return page

    def _build_log_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        self.log_view = QTextBrowser()
        self.log_view.setFrameShape(QFrame.Shape.NoFrame)
        self.log_view.setStyleSheet(
            "background: #1c1f24; font-family: Consolas, monospace; font-size: 11px;")
        lay.addWidget(self.log_view, 1)
        return page

    def _build_about_page(self) -> QWidget:
        from core.pipeline import available_algorithms

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        view = QTextBrowser()
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setStyleSheet("background: #1c1f24; font-size: 12px;")

        rows = []
        for name, label, color in [(m["name"], T.alg_label(m["name"]),
                                    T.alg_color(m["name"]))
                                   for m in available_algorithms()]:
            rows.append(
                f"<div style='margin-bottom:7px'>"
                f"<span style='color:{color}'>&#9632;</span> "
                f"<b>{label}</b> "
                f"<span style='color:#8b949e;font-family:Consolas'>{name}</span>"
                f"</div>")
        view.setHtml(
            "<div style='font-size:13px'><b>ChromaPeak Studio</b></div>"
            "<div style='color:#8b949e'>气相色谱峰识别算法测试平台 · v1.0.0</div>"
            "<p style='color:#8b949e'>同一套算法内核（Python 包 "
            "<code>chrompeak-core</code>）同时驱动桌面端（PyQt6 GUI / 命令行 CLI）"
            "与 Web 端（React + FastAPI），保证两端结果一致。</p>"
            "<div style='color:#8b949e;font-size:11px'>算法清单</div>"
            + "".join(rows) +
            "<div style='color:#8b949e;font-size:11px;margin-top:8px'>快捷操作</div>"
            "<div style='color:#8b949e'>"
            "· 图表上拖动可框选放大，右键菜单可复位<br>"
            "· 鼠标移动时右上角显示 t = 时间 / 响应 读数<br>"
            "· 点击图表左上角图例可显隐对应曲线<br>"
            "· 算法列表点「执行」可单独运行该算法并查看耗时"
            "</div>")
        lay.addWidget(view, 1)
        return page

    # ---- 状态栏 ----
    def _build_statusbar(self):
        sb = self.statusBar()
        self.sb_file = QLabel("文件：—")
        self.sb_pts = QLabel("点数：0")
        self.sb_dt = QLabel("采样间隔：—")
        self.sb_alg = QLabel("算法：0")
        self.sb_peak = QLabel("峰数：0")
        self.sb_ms = QLabel("耗时：—")
        self.sb_cursor = QLabel("光标：—")
        self.sb_msg = QLabel("就绪")
        for w in (self.sb_file, self.sb_pts, self.sb_dt, self.sb_alg,
                  self.sb_peak, self.sb_ms, self.sb_cursor):
            w.setObjectName("StatusCell")
            sb.addWidget(w)
        sb.addPermanentWidget(self.sb_msg)

    # ------------------------------------------------------------- 菜单栏 --
    def _build_menu(self):
        mb = self.menuBar()

        brand = QWidget()
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(4, 0, 8, 0)
        bl.setSpacing(6)
        logo = QLabel("CP")
        logo.setFixedSize(18, 18)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            "background: #2f7ff4; color: white; border-radius: 4px;"
            " font-size: 10px; font-weight: 700;")
        bl.addWidget(logo)
        title = QLabel("ChromaPeak Studio")
        title.setObjectName("AppTitle")
        bl.addWidget(title)
        sub = QLabel("— 气相色谱峰识别算法测试平台")
        sub.setObjectName("AppSubtitle")
        bl.addWidget(sub)
        mb.setCornerWidget(brand, Qt.Corner.TopLeftCorner)

        # ---- 文件 ----
        m = mb.addMenu("文件(&F)")
        self._act(m, "打开数据文件…", "Ctrl+O", self.open_file)
        self._act(m, "载入示例数据", "", self.load_sample)
        m.addSeparator()
        self._act(m, "导出峰表 CSV…", "Ctrl+S", lambda: self.export_file("csv"))
        self._act(m, "导出 Excel…", "", lambda: self.export_file("xlsx"))
        self._act(m, "导出图片 PNG…", "", self.export_png)
        m.addSeparator()
        self._act(m, "批量处理 ZIP…", "Ctrl+B", self.open_batch)
        m.addSeparator()
        self._act(m, "退出", "Ctrl+Q", self.close)

        # ---- 视图 ----
        m = mb.addMenu("视图(&V)")
        self.act_raw = self._act(m, "原始数据曲线", "", self._toggle_view, checkable=True)
        self.act_raw.setChecked(True)
        self.act_proc = self._act(m, "处理后曲线", "", self._toggle_view, checkable=True)
        self.act_proc.setChecked(True)
        self.act_mark = self._act(m, "峰位标记", "", self._toggle_view, checkable=True)
        self.act_mark.setChecked(True)
        m.addSeparator()
        self.act_cursor = self._act(m, "十字光标读数", "", self._toggle_view, checkable=True)
        self.act_cursor.setChecked(True)
        m.addSeparator()
        self._act(m, "算法面板", "", lambda: self.show_panel("algo"))
        self._act(m, "预处理面板", "", lambda: self.show_panel("preprocess"))
        self._act(m, "对比面板", "", lambda: self.show_panel("compare"))
        self._act(m, "运行日志", "", lambda: self.show_panel("log"))

        # ---- 算法 ----
        m = mb.addMenu("算法(&A)")
        self._act(m, "全选", "", lambda: self.set_all_algorithms(True))
        self._act(m, "全不选", "", lambda: self.set_all_algorithms(False))
        m.addSeparator()
        self._act(m, "运行全部已选算法", "F5", self.run_all)
        m.addSeparator()
        self.alg_menu = m
        self._fill_alg_menu()

        # ---- 工具 ----
        m = mb.addMenu("工具(&T)")
        self._act(m, "批量处理 ZIP…", "", self.open_batch)
        self._act(m, "预处理设置", "", lambda: self.show_panel("preprocess"))
        m.addSeparator()
        self._act(m, "清空运行日志", "", self.clear_log)

        # ---- 帮助 ----
        m = mb.addMenu("帮助(&H)")
        self._act(m, "关于 ChromaPeak Studio", "", lambda: self.show_panel("about"))
        self._act(m, "使用说明", "F1", self.show_help)

        # ---- 右上角动作 ----
        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 2, 6, 2)
        cl.setSpacing(2)
        for text, tip, slot in (
            ("对比", "打开算法对比面板", lambda: self.show_panel("compare")),
            ("批量", "批量处理 ZIP", self.open_batch),
            ("测量", "切换十字光标读数", self._toggle_cursor),
            ("导出", "导出峰表 CSV", lambda: self.export_file("csv")),
        ):
            b = QPushButton(text)
            b.setObjectName("Link")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            cl.addWidget(b)
        mb.setCornerWidget(corner, Qt.Corner.TopRightCorner)

    def _act(self, menu, text, shortcut, slot, checkable=False) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if checkable:
            a.setCheckable(True)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _fill_alg_menu(self):
        for m in self._metas:
            name = m["name"]
            code, label, _c = T.alg_visual(name)
            a = QAction(f"{code}  {label}", self)
            a.setCheckable(True)
            a.setChecked(True)
            a.toggled.connect(
                lambda checked, n=name: self._menu_algo_toggled(n, checked))
            self.alg_menu.addAction(a)

    def _menu_algo_toggled(self, name: str, checked: bool):
        self._enabled[name] = checked
        row = self._rows.get(name)
        if row is not None:
            row.check.blockSignals(True)
            row.check.setChecked(checked)
            row.check.blockSignals(False)
        self._update_alg_count()
        self.debounce.start()

    # ------------------------------------------------------------ 面板切换 --
    def show_panel(self, key: str):
        order = ["algo", "preprocess", "compare", "log", "about"]
        titles = {"algo": "算法", "preprocess": "预处理", "compare": "对比",
                  "log": "日志", "about": "关于"}
        if key not in order:
            return
        self.stack.setCurrentIndex(order.index(key))
        self.panel_title.setText(titles[key])
        btn = self.rail_buttons.get(key)
        if btn is not None:
            btn.setChecked(True)
        self.panel_action.setVisible(key == "algo")

    # ------------------------------------------------------------ 算法列表 --
    def rebuild_alg_list(self):
        q = self.alg_search.text().strip().lower()
        while self.alg_lay.count():
            it = self.alg_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows.clear()

        for meta in self._metas:
            name = meta["name"]
            code, label, _c = T.alg_visual(name)
            if q and q not in name.lower() and q not in label.lower() and q not in code.lower():
                continue
            row = AlgRow(name)
            row.check.setChecked(self._enabled.get(name, True))
            row.rowSelected.connect(self.select_algorithm)
            row.rowToggled.connect(self.toggle_algorithm)
            row.runOne.connect(self.run_single)
            row.bind_params(meta["params"])
            if row.param_panel is not None:
                row.param_panel.paramsChanged.connect(self.debounce.start)
            self.alg_lay.addWidget(row)
            self._rows[name] = row

        self.alg_lay.addStretch(1)
        self._update_alg_count()
        self._refresh_selection()

    def _update_alg_count(self):
        n = sum(1 for v in self._enabled.values() if v)
        self.alg_count_lbl.setText(f"共 {len(self._metas)} 个 · 已选 {n}")
        self.sb_alg.setText(f"算法：{n}")

    def _refresh_selection(self):
        for name, row in self._rows.items():
            row.set_active(name == self.selected)
            if row.param_panel is not None:
                row.param_host.setVisible(name == self.selected
                                          and row.check.isChecked())
        meta = next((m for m in self._metas if m["name"] == self.selected), None)
        if meta is not None:
            code, label, _c = T.alg_visual(self.selected)
            self.alg_foot.setText(f"{code} {label}\n{meta['description']}")

    def select_algorithm(self, name: str):
        self.selected = name
        self._refresh_selection()
        self.run_single(name)

    def toggle_algorithm(self, name: str, checked: bool):
        self._enabled[name] = checked
        for a in self.alg_menu.actions():
            if a.text().replace("  ", " ").startswith(T.alg_visual(name)[0]):
                a.blockSignals(True)
                a.setChecked(checked)
                a.blockSignals(False)
                break
        self._update_alg_count()
        self._refresh_selection()
        self.debounce.start()

    def set_all_algorithms(self, value: bool):
        for name in self._enabled:
            self._enabled[name] = value
        for row in self._rows.values():
            row.check.blockSignals(True)
            row.check.setChecked(value)
            row.check.blockSignals(False)
        for a in self.alg_menu.actions():
            if a.isCheckable():
                a.blockSignals(True)
                a.setChecked(value)
                a.blockSignals(False)
        self._update_alg_count()
        self._refresh_selection()
        self.debounce.start()

    def _checked_algorithms(self) -> list[str]:
        out = [m["name"] for m in self._metas if self._enabled.get(m["name"])]
        return out or ([self.selected] if self.selected else [])

    def _params_for(self, name: str) -> dict:
        row = self._rows.get(name)
        if row is not None and row.param_panel is not None:
            return row.param_panel.get_params()
        meta = next((m for m in self._metas if m["name"] == name), None)
        if meta is None:
            return {}
        return {p.key: p.default for p in meta["params"]}

    # -------------------------------------------------------------- 预处理 --
    @staticmethod
    def _spin(lo, hi, val, step=1) -> QSpinBox:
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(val)
        w.setSingleStep(step)
        return w

    @staticmethod
    def _dspin(lo, hi, val, decimals, step) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(decimals)
        w.setValue(val)
        w.setSingleStep(step)
        return w

    def _field(self, label: str, widget: QWidget) -> QWidget:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #8b949e;")
        h.addWidget(lbl, 1)
        widget.setFixedWidth(110)
        h.addWidget(widget)
        return box

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #8b949e; font-size: 10px; font-weight: 600;"
            " letter-spacing: 0.5px; padding-top: 6px;")
        return lbl

    def _collect_pre(self) -> PreprocessOptions:
        return PreprocessOptions(
            baseline=self.pre_baseline.isChecked(),
            baseline_order=int(self.pre_order.value()),
            baseline_iters=int(self.pre_iters.value()),
            baseline_tol=float(self.pre_tol.value()),
            smooth=self.pre_smooth.isChecked(),
            smooth_window=int(self.pre_win.value()),
            smooth_polyorder=int(self.pre_poly.value()),
        )

    def _pre_changed(self):
        self.pre_opts = self._collect_pre()
        self.debounce.start()

    def _reset_preprocess(self):
        self.pre_baseline.setChecked(True)
        self.pre_order.setValue(3)
        self.pre_iters.setValue(10)
        self.pre_tol.setValue(1e-4)
        self.pre_smooth.setChecked(True)
        self.pre_win.setValue(11)
        self.pre_poly.setValue(3)
        self._pre_changed()

    # ---------------------------------------------------------------- 数据 --
    def load_sample(self):
        self.x, self.y = synthetic_chromatogram()
        self.file_name = "示例数据（合成色谱）"
        self.log("载入示例数据（合成色谱）")
        self.run_all()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开色谱数据", "", "CSV/TXT (*.csv *.txt);;所有文件 (*.*)")
        if not path:
            return
        try:
            self.x, self.y = load_chromatogram(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"无法读取文件：{e}")
            return
        self.file_name = os.path.basename(path)
        self.log(f"载入文件 {self.file_name}", "ok")
        self.run_all()

    # ---------------------------------------------------------------- 运行 --
    def run_all(self):
        if self.x is None:
            return
        algos = self._checked_algorithms()
        if not algos:
            return
        self.pre_opts = self._collect_pre()
        params = {a: self._params_for(a) for a in algos}

        t0 = time.perf_counter()
        try:
            res = run_algorithms(self.x, self.y, algos, params,
                                 self.pre_opts.__dict__)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "运行失败", str(e))
            self.log(f"运行失败：{e}", "err")
            return
        total_ms = (time.perf_counter() - t0) * 1000

        self.y_proc = np.asarray(res["y_proc"])
        self.baseline = np.asarray(res["baseline"])
        self.results = res["results"]

        # 逐算法耗时（同一份数据独立计时，便于对比）
        for name in algos:
            s0 = time.perf_counter()
            try:
                one = analyze(self.x, self.y, name, params.get(name),
                              self.pre_opts.__dict__)
                ms = (time.perf_counter() - s0) * 1000
                self.stats[name] = {"peaks": len(one["peaks"]), "ms": ms, "ok": True}
            except Exception as e:  # noqa: BLE001
                self.stats[name] = {"peaks": 0, "ms": 0.0, "ok": False,
                                    "msg": str(e)}

        for name in list(self.stats):
            if name not in algos:
                self.stats.pop(name, None)

        self.last_ms = total_ms
        self._sync_alg_results()
        self.redraw()
        self.refill_peak_table()
        self.refill_result_table()
        self.refill_info_table()
        self._update_status()
        n = sum(len(v) for v in self.results.values())
        self.log(f"运行 {len(algos)} 个算法 → {n} 个峰（{total_ms:.0f} ms）", "ok")

    def run_single(self, name: str):
        self.selected = name
        self._refresh_selection()
        if self.x is None:
            return
        self.pre_opts = self._collect_pre()
        params = self._params_for(name)
        s0 = time.perf_counter()
        try:
            one = analyze(self.x, self.y, name, params, self.pre_opts.__dict__)
        except Exception as e:  # noqa: BLE001
            self.stats[name] = {"peaks": 0, "ms": 0.0, "ok": False, "msg": str(e)}
            self._sync_alg_results()
            self.log(f"{T.alg_visual(name)[0]} 执行失败：{e}", "err")
            return
        ms = (time.perf_counter() - s0) * 1000
        self.y_proc = np.asarray(one["y_proc"])
        self.baseline = np.asarray(one["baseline"])
        self.results[name] = one["peaks"]
        self.stats[name] = {"peaks": len(one["peaks"]), "ms": ms, "ok": True}
        self.last_ms = ms
        self._sync_alg_results()
        self.redraw()
        self.refill_peak_table()
        self.refill_result_table()
        self.refill_info_table()
        self._update_status()
        self.log(f"{T.alg_visual(name)[0]} 单独执行 → {len(one['peaks'])} 个峰"
                 f"（{ms:.0f} ms）", "ok")

    def _sync_alg_results(self):
        for name, row in self._rows.items():
            st = self.stats.get(name)
            if st is None:
                row.set_result("待执行" if self._enabled.get(name) else "未启用", None)
            elif st["ok"]:
                row.set_result(f"{st['peaks']} 峰 | {st['ms']:.0f} ms", True)
            else:
                row.set_result("失败", False)
        self.refill_compare()

    # ---------------------------------------------------------------- 绘图 --
    def redraw(self):
        for item in list(self._curves.values()):
            try:
                self.plot.removeItem(item)
            except Exception:  # noqa: BLE001
                pass
        self._curves.clear()
        for it in self._marker_items:
            try:
                self.plot.removeItem(it)
            except Exception:  # noqa: BLE001
                pass
        self._marker_items.clear()
        for ln in (self.vline, self.hline):
            if ln is not None:
                try:
                    self.plot.removeItem(ln)
                except Exception:  # noqa: BLE001
                    pass
        self.vline = self.hline = None
        self.legend.clear_items()

        if self.x is None:
            return

        if self.show_raw:
            c = self.plot.plot(self.x, self.y,
                               pen=pg.mkPen(T.PLOT_RAW, width=1))
            self._curves["raw"] = c
            self.legend.add_item("raw", "原始数据", T.PLOT_RAW)

        if self.show_proc and self.y_proc is not None:
            c = self.plot.plot(self.x, self.y_proc,
                               pen=pg.mkPen(T.PLOT_PROC, width=1.4),
                               fillLevel=0.0, brush=pg.mkBrush(232, 234, 237, 26))
            self._curves["proc"] = c
            self.legend.add_item("proc", "处理后（基线校正 + 平滑）", T.PLOT_PROC)

        if self.show_markers:
            for name, peaks in self.results.items():
                if not peaks:
                    continue
                color = T.alg_color(name)
                xs = [p["rt"] for p in peaks]
                ys = [self._apex_value(p) for p in peaks]
                sc = pg.ScatterPlotItem(
                    xs, ys, symbol="o", size=8,
                    pen=pg.mkPen(color, width=1.2), brush=pg.mkBrush(color))
                self.plot.addItem(sc)
                self._marker_items.append(sc)
                code, label, _c = T.alg_visual(name)
                self.legend.add_item(name, f"{code} · {label}", color)

        self._install_crosshair()
        self.plot.enableAutoRange()
        self.legend.adjustSize()

    def _apex_value(self, peak: dict) -> float:
        idx = int(peak.get("index", 0))
        arr = self.y_proc if self.y_proc is not None else self.y
        if arr is not None and 0 <= idx < len(arr):
            return float(arr[idx])
        return float(peak.get("height", 0.0))

    def _install_crosshair(self):
        pen = pg.mkPen((215, 220, 227, 100), width=1,
                       style=Qt.PenStyle.DashLine)
        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self.hline = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self.vline.setZValue(50)
        self.hline.setZValue(50)
        self.plot.addItem(self.vline, ignoreBounds=True)
        self.plot.addItem(self.hline, ignoreBounds=True)

    def _on_mouse_move(self, evt):
        if self.x is None or self.vline is None:
            return
        pos = evt[0]
        vb = self.plot.getPlotItem().vb
        if not self.plot.sceneBoundingRect().contains(pos):
            self.readout.setVisible(False)
            self.sb_cursor.setText("光标：—")
            return
        mp = vb.mapSceneToView(pos)
        self.vline.setPos(mp.x())
        self.hline.setPos(mp.y())
        if self.cursor_on:
            self.readout.setText(f"t = {mp.x():.4g} min / {mp.y():.4g}")
            self.readout.setVisible(True)
            self.sb_cursor.setText(f"光标：{mp.x():.4g} min / {mp.y():.4g}")
        else:
            self.readout.setVisible(False)

    def _on_legend_toggle(self, key: str, visible: bool):
        item = self._curves.get(key)
        if item is not None:
            item.setVisible(visible)
            return
        for it in self._marker_items:
            pass
        # 峰位标记按算法名索引
        idx = 0
        for name in self.results:
            if name == key:
                if idx < len(self._marker_items):
                    self._marker_items[idx].setVisible(visible)
                break
            if self.results[name]:
                idx += 1

    def _toggle_view(self):
        self.show_raw = self.act_raw.isChecked()
        self.show_proc = self.act_proc.isChecked()
        self.show_markers = self.act_mark.isChecked()
        self.cursor_on = self.act_cursor.isChecked()
        if not self.cursor_on:
            self.readout.setVisible(False)
        self.redraw()

    def _toggle_cursor(self):
        self.act_cursor.setChecked(not self.act_cursor.isChecked())
        self._toggle_view()

    # ------------------------------------------------------------ 表格填充 --
    def _all_peaks(self) -> list[dict]:
        out = []
        for peaks in self.results.values():
            out.extend(peaks)
        return out

    def refill_peak_table(self):
        x = self.x if self.x is not None else np.array([])
        allp = self._all_peaks()
        src = self.src_combo.currentText()
        q = self.peak_search.text().strip().lower()

        # 重建来源下拉（保持当前选择）
        want = ["全部来源"] + [n for n in self.results if self.results[n]]
        if [self.src_combo.itemText(i) for i in range(self.src_combo.count())] != want:
            self.src_combo.blockSignals(True)
            self.src_combo.clear()
            self.src_combo.addItems(want)
            i = want.index(src) if src in want else 0
            self.src_combo.setCurrentIndex(i)
            self.src_combo.blockSignals(False)
            src = self.src_combo.currentText()

        groups: dict[str, list[dict]] = {}
        for p in allp:
            groups.setdefault(p["algorithm"], []).append(p)

        prepared = []
        for alg, ps in groups.items():
            ps = sorted(ps, key=lambda d: d["rt"])
            for i, p in enumerate(ps):
                res = None
                if i > 0:
                    prev = ps[i - 1]
                    denom = float(prev.get("fwhm", 0)) + float(p.get("fwhm", 0))
                    if denom > 0:
                        res = 1.18 * (p["rt"] - prev["rt"]) / denom
                prepared.append((p, alg, i + 1, res))
        prepared.sort(key=lambda t: (t[0]["rt"], t[1]))

        rows = []
        for no, (p, alg, alg_no, res) in enumerate(prepared, start=1):
            code, label, _c = T.alg_visual(alg)
            if src != "全部来源" and alg != src:
                continue
            if q and q not in f"{p['rt']:.4f}" and q not in code.lower() \
                    and q not in label.lower():
                continue
            li = int(p.get("left", -1))
            ri = int(p.get("right", -1))
            x0 = float(x[li]) if 0 <= li < len(x) else p["rt"]
            x1 = float(x[ri]) if 0 <= ri < len(x) else p["rt"]
            rows.append([
                str(no), f"{p['rt']:.4f}", f"{x0:.4f}", f"{p['height']:.4f}",
                f"{p['area']:.4f}", f"{x1 - x0:.4f}",
                "—" if res is None else f"{res:.3f}",
                f"{p['asymmetry']:.3f}", f"{p['score']:.2f}", code,
                f"{label.split('（')[0]} #{alg_no}",
            ])

        self.peak_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                if c in (1, 2, 3, 4, 5, 6, 7, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter)
                self.peak_table.setItem(r, c, item)
        self.peak_count_lbl.setText(f"共 {len(rows)} / {len(allp)} 个峰")
        self.sb_peak.setText(f"峰数：{len(allp)}")

    def _clusters(self) -> list[dict]:
        if self.x is None or len(self.x) == 0:
            return []
        tol = max((float(self.x[-1]) - float(self.x[0])) * 0.004, 1e-9)
        peaks = sorted(self._all_peaks(), key=lambda d: d["rt"])
        groups: list[list[dict]] = []
        for p in peaks:
            if groups and abs(p["rt"] - groups[-1][-1]["rt"]) <= tol:
                groups[-1].append(p)
            else:
                groups.append([p])
        out = []
        for g in groups:
            algs = sorted({p["algorithm"] for p in g})
            rts = [p["rt"] for p in g]
            out.append({
                "rt": sum(rts) / len(rts),
                "n": len(algs),
                "algs": algs,
                "h": sum(p["height"] for p in g) / len(g),
                "score": sum(p["score"] for p in g) / len(g),
                "spread": max(rts) - min(rts),
            })
        return out

    def refill_result_table(self):
        cl = self._clusters()
        cons = sum(1 for c in cl if c["n"] >= 2)
        self.consensus_lbl.setText(
            f"共识峰（≥2 个算法共同检出）：{cons}　·　保留时间簇总数：{len(cl)}")
        self.result_table.setRowCount(len(cl))
        for i, c in enumerate(cl):
            vals = [
                str(i + 1), f"{c['rt']:.4f}", str(c["n"]), f"{c['spread']:.4f}",
                f"{c['h']:.4f}", f"{c['score']:.2f}",
                "  ".join(T.alg_visual(a)[0] for a in c["algs"]),
                "多算法一致" if c["n"] >= 2 else "单算法检出",
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j in (1, 3, 4, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                        | Qt.AlignmentFlag.AlignVCenter)
                if j == 2:
                    it.setForeground(QColor(T.OK if c["n"] >= 2 else T.TEXT_DIM))
                self.result_table.setItem(i, j, it)

    def refill_compare(self):
        names = [m["name"] for m in self._metas if self._enabled.get(m["name"])]
        self.cmp_table.setRowCount(len(names))
        for i, name in enumerate(names):
            st = self.stats.get(name, {})
            peaks = self.results.get(name, [])
            avg_h = sum(p["height"] for p in peaks) / len(peaks) if peaks else 0.0
            avg_a = sum(p["asymmetry"] for p in peaks) / len(peaks) if peaks else 0.0
            avg_s = sum(p["score"] for p in peaks) / len(peaks) if peaks else 0.0
            code, _label, _c = T.alg_visual(name)
            vals = [
                code,
                str(st.get("peaks", 0)),
                "—" if not st else f"{st.get('ms', 0):.0f} ms",
                f"{avg_h:.4f}", f"{avg_a:.3f}", f"{avg_s:.2f}",
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j >= 1:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                        | Qt.AlignmentFlag.AlignVCenter)
                self.cmp_table.setItem(i, j, it)

    def refill_info_table(self):
        x = self.x
        n = len(x) if x is not None else 0
        dt = abs(float(x[1] - x[0])) if n > 1 else 0.0
        items = [
            ("文件名", self.file_name or "—"),
            ("数据点数", str(n)),
            ("采样间隔", f"{dt:.4f}" if n > 1 else "—"),
            ("时间范围 / min", f"{float(x[0]):.3f} ~ {float(x[-1]):.3f}" if n else "—"),
            ("参与算法", str(len(self._checked_algorithms()))),
            ("检出峰总数", str(len(self._all_peaks()))),
            ("最近一次耗时", "—" if self.last_ms is None else f"{self.last_ms:.0f} ms"),
            ("预处理 · 基线校正",
             "开" if self.pre_opts.baseline else "关"),
            ("预处理 · 平滑",
             f"SG 窗口 {self.pre_opts.smooth_window} / 阶 {self.pre_opts.smooth_polyorder}"
             if self.pre_opts.smooth else "关"),
            ("算法内核", "chrompeak-core（与 Web 端共用）"),
        ]
        self.info_table.setRowCount(len(items))
        for i, (k, v) in enumerate(items):
            self.info_table.setItem(i, 0, QTableWidgetItem(k))
            self.info_table.setItem(i, 1, QTableWidgetItem(v))

    def _update_status(self):
        x = self.x
        n = len(x) if x is not None else 0
        dt = abs(float(x[1] - x[0])) if n > 1 else 0.0
        self.sb_file.setText(f"文件：{self.file_name or '—'}")
        self.sb_pts.setText(f"点数：{n}")
        self.sb_dt.setText(f"采样间隔：{dt:.4f}" if n > 1 else "采样间隔：—")
        self.sb_alg.setText(f"算法：{len(self._checked_algorithms())}")
        self.sb_peak.setText(f"峰数：{len(self._all_peaks())}")
        self.sb_ms.setText("耗时：—" if self.last_ms is None
                           else f"耗时：{self.last_ms:.0f} ms")

    # ---------------------------------------------------------------- 日志 --
    def log(self, msg: str, kind: str = ""):
        ts = time.strftime("%H:%M:%S")
        self.logs.append((ts, msg, kind))
        self.logs = self.logs[-300:]
        color = {"ok": T.OK, "err": T.DANGER, "warn": T.WARN}.get(kind, T.TEXT_DIM)
        self.log_view.append(
            f"<span style='color:#5c646e'>{ts}</span> "
            f"<span style='color:{color}'>{msg}</span>")

    def clear_log(self):
        self.logs.clear()
        self.log_view.clear()
        self.log("日志已清空")

    def show_help(self):
        QMessageBox.information(
            self, "使用说明",
            "1. 文件 → 打开数据文件（或载入示例数据）\n"
            "2. 右侧算法面板勾选算法、点算法名展开参数，改动后自动重算\n"
            "3. 图表上拖动框选放大，右键复位；鼠标移动显示 t / 响应 读数\n"
            "4. 底部标签页切换峰表 / 结果（共识峰）/ 文件信息\n"
            "5. 文件 → 导出峰表 CSV / Excel / 图片 PNG")

    # ---------------------------------------------------------------- 导出 --
    def export_file(self, kind: str):
        if self.x is None:
            QMessageBox.information(self, "提示", "请先载入数据")
            return
        peaks = self._all_peaks()
        if not peaks:
            QMessageBox.information(self, "提示", "当前没有可导出的峰")
            return
        if kind == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "peaks.csv",
                                                  "CSV (*.csv)")
            if path:
                save_peaks_csv(peaks, path)
                self.log(f"导出峰表 CSV：{os.path.basename(path)}"
                         f"（{len(peaks)} 行）", "ok")
                QMessageBox.information(self, "完成", f"已导出 {len(peaks)} 个峰")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "导出 Excel", "peaks.xlsx",
                                                  "Excel (*.xlsx)")
            if path:
                self._export_xlsx(peaks, path)
                self.log(f"导出 Excel：{os.path.basename(path)}", "ok")

    def _export_xlsx(self, peaks, path):
        try:
            from openpyxl import Workbook
        except Exception:  # noqa: BLE001
            QMessageBox.warning(self, "缺少依赖", "未安装 openpyxl，无法导出 Excel。")
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "Peaks"
        cols = ["index", "rt", "height", "area", "fwhm", "asymmetry",
                "score", "algorithm"]
        ws.append(cols)
        for pk in peaks:
            d = pk.to_dict() if hasattr(pk, "to_dict") else pk
            ws.append([d.get(c, "") for c in cols])
        wb.save(path)
        QMessageBox.information(self, "完成", f"已导出 {len(peaks)} 个峰到 Excel")

    def export_png(self):
        if self.x is None:
            QMessageBox.information(self, "提示", "请先载入数据")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出图片", "chromatogram.png",
                                              "PNG (*.png)")
        if path:
            exporter = pg.exporters.ImageExporter(self.plot.plotItem)
            exporter.export(path)
            self.log(f"导出图片：{os.path.basename(path)}", "ok")
            QMessageBox.information(self, "完成", f"已导出图片：{path}")

    def open_batch(self):
        dlg = BatchDialog(self)
        if dlg.exec():
            out_dir = dlg.out_dir
            files = dlg.files
            if not files or not out_dir:
                return
            algos = self._checked_algorithms()
            done = 0
            for f in files:
                try:
                    bx, by = load_chromatogram(f)
                    res = run_algorithms(bx, by, algos, None,
                                         self.pre_opts.__dict__)
                    base = os.path.splitext(os.path.basename(f))[0]
                    save_peaks_csv(
                        [p for ps in res["results"].values() for p in ps],
                        os.path.join(out_dir, f"{base}_peaks.csv"))
                    done += 1
                except Exception as e:  # noqa: BLE001
                    self.log(f"批量失败 {os.path.basename(f)}：{e}", "err")
            self.log(f"批量完成 {done}/{len(files)} 个文件 → {out_dir}", "ok")
            QMessageBox.information(self, "批量完成",
                                    f"已处理 {done}/{len(files)} 个文件 → {out_dir}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(T.QSS)
    T.install_fonts(app)
    pg.setConfigOptions(antialias=True, background=T.PLOT_BG,
                        foreground=T.PLOT_AXIS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
