"""Batch-processing dialog: select multiple files and an output directory."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                            QListWidget, QMessageBox, QPushButton, QVBoxLayout)


class BatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量处理")
        self.resize(560, 420)
        self.files: list = []
        self.out_dir = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择多个色谱文件（csv/txt）："))

        self.list = QListWidget()
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("添加文件")
        self.btn_dir = QPushButton("选择输出目录")
        self.btn_ok = QPushButton("开始处理")
        self.btn_cancel = QPushButton("取消")
        for b in (self.btn_add, self.btn_dir, self.btn_ok, self.btn_cancel):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.lbl_out = QLabel("输出目录：未选择")
        layout.addWidget(self.lbl_out)

        self.btn_add.clicked.connect(self._add)
        self.btn_dir.clicked.connect(self._pick_dir)
        self.btn_ok.clicked.connect(self._accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _add(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "添加色谱文件", "", "CSV/TXT (*.csv *.txt);;所有文件 (*.*)")
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.list.addItem(p)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.out_dir = d
            self.lbl_out.setText(f"输出目录：{d}")

    def _accept(self):
        if not self.files:
            QMessageBox.warning(self, "提示", "请先添加文件")
            return
        if not self.out_dir:
            QMessageBox.warning(self, "提示", "请选择输出目录")
            return
        self.accept()
