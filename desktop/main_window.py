"""ChromaPeak Studio desktop application (PyQt6 + pyqtgraph)."""
from __future__ import annotations

import os
import sys

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                            QHeaderView, QLabel, QListWidget, QListWidgetItem,
                            QMainWindow, QMessageBox, QPushButton, QSplitter,
                            QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.io import load_chromatogram, save_peaks_csv
from core.pipeline import analyze, available_algorithms, run_algorithms
from core.sample_data import synthetic_chromatogram

from .batch_dialog import BatchDialog
from .param_panel import ParamPanel

ALG_COLORS = {
    "ALG-D": "#e6194B", "ALG-W": "#3cb44b", "ALG-M": "#4363d8",
    "ALG-C": "#f58231", "ALG-E": "#911eb4", "ALG-GNN": "#46f0f0",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChromaPeak Studio")
        self.resize(1280, 820)
        self.x = None
        self.y = None
        self.y_proc = None
        self.baseline = None
        self.alg_meta = available_algorithms()
        self.selected = self.alg_meta[0]["name"] if self.alg_meta else "ALG-D"
        self._init_ui()
        # 200ms debounced live preview
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(200)
        self.debounce.timeout.connect(self.run_selected)
        self.load_sample()

    # ---------------- UI ----------------
    def _init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        # left column: algorithm list + param panel
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.addWidget(QLabel("算法"))
        self.alg_list = QListWidget()
        self.alg_list.setFixedWidth(220)
        for m in self.alg_meta:
            item = QListWidgetItem(m["name"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, m["name"])
            self.alg_list.addItem(item)
        self.alg_list.currentItemChanged.connect(self._on_alg_selected)
        left_l.addWidget(self.alg_list)
        self.param_host = QWidget()
        left_l.addWidget(QLabel("参数"))
        left_l.addWidget(self.param_host)
        self._build_param_panel(self.selected)

        # center column: plot + table + toolbar
        center = QWidget()
        c_l = QVBoxLayout(center)
        tb = QHBoxLayout()
        self.btn_open = QPushButton("打开文件")
        self.btn_sample = QPushButton("示例数据")
        self.btn_run = QPushButton("运行全部")
        self.btn_batch = QPushButton("批量处理")
        self.btn_csv = QPushButton("导出 CSV")
        self.btn_xlsx = QPushButton("导出 Excel")
        self.btn_png = QPushButton("导出 PNG")
        for b in (self.btn_open, self.btn_sample, self.btn_run,
                  self.btn_batch, self.btn_csv, self.btn_xlsx, self.btn_png):
            tb.addWidget(b)
        c_l.addLayout(tb)

        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "保留时间")
        self.plot.setLabel("left", "信号")
        c_l.addWidget(self.plot, 3)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["算法", "RT", "峰高", "面积", "半高宽", "不对称", "置信度"])
        self.table.horizontalHeader().setStretchLastSection(True)
        c_l.addWidget(self.table, 2)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.btn_open.clicked.connect(self.open_file)
        self.btn_sample.clicked.connect(self.load_sample)
        self.btn_run.clicked.connect(self.run_all)
        self.btn_batch.clicked.connect(self.open_batch)
        self.btn_csv.clicked.connect(lambda: self.export_file("csv"))
        self.btn_xlsx.clicked.connect(lambda: self.export_file("xlsx"))
        self.btn_png.clicked.connect(self.export_png)

    def _build_param_panel(self, alg_name):
        specs = next(m["params"] for m in self.alg_meta if m["name"] == alg_name)
        # rebuild panel
        old = self.param_host.layout()
        if old:
            while old.count():
                old.takeAt(0).widget().deleteLater()
        self.param_panel = ParamPanel(specs)
        self.param_panel.paramsChanged.connect(self.debounce.start)
        host_l = QVBoxLayout(self.param_host)
        host_l.addWidget(self.param_panel)

    def _on_alg_selected(self, current, _prev):
        if current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        self.selected = name
        self._build_param_panel(name)
        self.run_selected()

    # ---------------- data ----------------
    def load_sample(self):
        self.x, self.y = synthetic_chromatogram()
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
        self.run_all()

    # ---------------- analysis ----------------
    def _checked_algorithms(self):
        out = []
        for i in range(self.alg_list.count()):
            it = self.alg_list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out or [self.selected]

    def run_selected(self):
        if self.x is None:
            return
        params = self.param_panel.get_params()
        res = analyze(self.x, self.y, self.selected, params)
        self.y_proc = np.array(res["y_proc"])
        self.baseline = np.array(res["baseline"])
        self._draw({self.selected: res["peaks"]})
        self._fill_table({self.selected: res["peaks"]})

    def run_all(self):
        if self.x is None:
            return
        algos = self._checked_algorithms()
        params = {a: self.param_panel.get_params() if a == self.selected else None
                  for a in algos}
        # only the selected algorithm gets live params; others use defaults
        res = run_algorithms(self.x, self.y, algos,
                             {a: (params[a] or {}) for a in algos})
        self.y_proc = np.array(res["y_proc"])
        self.baseline = np.array(res["baseline"])
        self._draw(res["results"])
        self._fill_table(res["results"])

    # ---------------- drawing ----------------
    def _draw(self, results: dict):
        self.plot.clear()
        if self.x is None:
            return
        self.plot.plot(self.x, self.y, pen=pg.mkPen("#888888", width=1),
                      name="原始")
        if self.y_proc is not None:
            self.plot.plot(self.x, self.y_proc, pen=pg.mkPen("#222222", width=1.5),
                          name="处理后")
        for alg, peaks in results.items():
            color = ALG_COLORS.get(alg, "#ff0000")
            xs = [p["rt"] for p in peaks]
            ys = [self.y[int(p["index"])] if 0 <= p["index"] < len(self.y) else p["rt"]
                  for p in peaks]
            ys = [p["height"] for p in peaks]
            self.plot.plot(xs, ys, pen=None,
                           symbol="o", symbolSize=9,
                           symbolBrush=color, symbolPen=color,
                           name=alg)

    def _fill_table(self, results: dict):
        rows = []
        for alg, peaks in results.items():
            for p in peaks:
                rows.append([alg, f"{p['rt']:.3f}", f"{p['height']:.4f}",
                             f"{p['area']:.4f}", f"{p['fwhm']:.3f}",
                             f"{p['asymmetry']:.2f}", f"{p['score']:.2f}"])
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)

    # ---------------- export ----------------
    def _collect_peaks(self):
        algos = self._checked_algorithms()
        res = run_algorithms(self.x, self.y, algos)
        all_peaks = []
        for peaks in res["results"].values():
            all_peaks.extend(peaks)
        return all_peaks

    def export_file(self, kind):
        if self.x is None:
            return
        peaks = self._collect_peaks()
        if kind == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "peaks.csv",
                                                  "CSV (*.csv)")
            if path:
                save_peaks_csv(peaks, path)
                QMessageBox.information(self, "完成", f"已导出 {len(peaks)} 个峰")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "导出 Excel", "peaks.xlsx",
                                                  "Excel (*.xlsx)")
            if path:
                self._export_xlsx(peaks, path)

    def _export_xlsx(self, peaks, path):
        try:
            from openpyxl import Workbook
        except Exception:  # noqa: BLE001
            QMessageBox.warning(self, "缺少依赖",
                                "未安装 openpyxl，无法导出 Excel。")
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
        if self.plot is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出图片", "chromatogram.png",
                                              "PNG (*.png)")
        if path:
            exporter = pg.exporters.ImageExporter(self.plot.plotItem)
            exporter.export(path)
            QMessageBox.information(self, "完成", f"已导出图片：{path}")

    def open_batch(self):
        dlg = BatchDialog(self)
        if dlg.exec():
            out_dir = dlg.out_dir
            files = dlg.files
            if not files or not out_dir:
                return
            for f in files:
                try:
                    x, y = load_chromatogram(f)
                    algos = self._checked_algorithms()
                    res = run_algorithms(x, y, algos)
                    base = os.path.splitext(os.path.basename(f))[0]
                    save_peaks_csv(
                        [p for ps in res["results"].values() for p in ps],
                        os.path.join(out_dir, f"{base}_peaks.csv"))
                except Exception as e:  # noqa: BLE001
                    print(f"batch failed for {f}: {e}")
            QMessageBox.information(self, "批量完成",
                                    f"已处理 {len(files)} 个文件 -> {out_dir}")


def main():
    app = QApplication(sys.argv)
    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
