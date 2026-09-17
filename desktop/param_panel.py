"""Auto-generated parameter panel driven by ``ParamSpec`` metadata."""
from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout,
                            QHBoxLayout, QLabel, QSpinBox, QVBoxLayout,
                            QWidget, QCheckBox)

from core.algorithms.base import ParamSpec


class ParamPanel(QWidget):
    """Build a form from a list of :class:`ParamSpec` and expose values."""

    paramsChanged = pyqtSignal()

    def __init__(self, specs: List[ParamSpec], parent=None):
        super().__init__(parent)
        self.specs = specs
        self.widgets: Dict[str, QWidget] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for s in self.specs:
            w = self._make_widget(s)
            self.widgets[s.key] = w
            w.valueChanged.connect(lambda *_: self.paramsChanged.emit()) \
                if isinstance(w, (QDoubleSpinBox, QSpinBox)) \
                else w.currentTextChanged.connect(lambda *_: self.paramsChanged.emit()) \
                if isinstance(w, QComboBox) \
                else w.stateChanged.connect(lambda *_: self.paramsChanged.emit())
            form.addRow(QLabel(s.label), w)
        layout.addLayout(form)
        layout.addStretch(1)

    def _make_widget(self, s: ParamSpec) -> QWidget:
        if s.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(s.default))
            return w
        if s.type == "choice":
            w = QComboBox()
            for c in (s.choices or []):
                w.addItem(str(c))
            if s.default in (s.choices or []):
                w.setCurrentText(str(s.default))
            return w
        if s.type == "int":
            w = QSpinBox()
            if s.min is not None:
                w.setMinimum(int(s.min))
            if s.max is not None:
                w.setMaximum(int(s.max))
            if s.step:
                w.setSingleStep(int(s.step))
            w.setValue(int(s.default))
            return w
        # float
        w = QDoubleSpinBox()
        if s.min is not None:
            w.setMinimum(float(s.min))
        if s.max is not None:
            w.setMaximum(float(s.max))
        w.setDecimals(4)
        if s.step:
            w.setSingleStep(float(s.step))
        else:
            w.setSingleStep(0.01)
        w.setValue(float(s.default))
        return w

    def get_params(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for s in self.specs:
            w = self.widgets[s.key]
            if s.type == "bool":
                out[s.key] = w.isChecked()
            elif s.type == "choice":
                out[s.key] = w.currentText()
            elif s.type == "int":
                out[s.key] = w.value()
            else:
                out[s.key] = w.value()
        return out
