"""Auto-generated parameter panel driven by ``ParamSpec`` metadata.

既接受 :class:`core.algorithms.base.ParamSpec` 实例，也接受它的 ``to_dict()``
结果（``core.algorithms.algorithm_meta()`` 返回的是 dict），方便 UI 直接消费。
"""
from __future__ import annotations

from typing import Any, Dict, List, Union

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                            QLabel, QSpinBox, QVBoxLayout, QWidget)

from core.algorithms.base import ParamSpec

SpecLike = Union[ParamSpec, dict]

_FIELDS = ("key", "label", "type", "default", "min", "max", "step", "choices", "help")


class _SpecView:
    """把 dict 规格包装成和 :class:`ParamSpec` 一样的只读属性访问。"""

    __slots__ = _FIELDS

    def __init__(self, d: dict):
        for f in _FIELDS:
            setattr(self, f, d.get(f))


def _spec(s: SpecLike) -> _SpecView:
    if isinstance(s, dict):
        return _SpecView(s)
    return _SpecView({f: getattr(s, f, None) for f in _FIELDS})


class ParamPanel(QWidget):
    """Build a form from a list of parameter specs and expose current values."""

    paramsChanged = pyqtSignal()

    def __init__(self, specs: List[SpecLike], parent=None):
        super().__init__(parent)
        self.specs = [_spec(s) for s in specs]
        self.widgets: Dict[str, QWidget] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(4)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        for s in self.specs:
            w = self._make_widget(s)
            self.widgets[s.key] = w
            self._connect(w)
            lbl = QLabel(str(s.label or s.key))
            lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            if s.help:
                lbl.setToolTip(str(s.help))
            form.addRow(lbl, w)
        layout.addLayout(form)

    def _connect(self, w: QWidget):
        if isinstance(w, (QDoubleSpinBox, QSpinBox)):
            w.valueChanged.connect(lambda *_: self.paramsChanged.emit())
        elif isinstance(w, QComboBox):
            w.currentTextChanged.connect(lambda *_: self.paramsChanged.emit())
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(lambda *_: self.paramsChanged.emit())

    def _make_widget(self, s: _SpecView) -> QWidget:
        if s.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(s.default))
            return w
        if s.type == "choice":
            w = QComboBox()
            choices = s.choices or []
            for c in choices:
                w.addItem(str(c))
            if s.default in choices:
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
        w.setSingleStep(float(s.step) if s.step else 0.01)
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

    def reset(self):
        """恢复到各参数的默认值。"""
        for s in self.specs:
            w = self.widgets[s.key]
            if isinstance(w, QCheckBox):
                w.setChecked(bool(s.default))
            elif isinstance(w, QComboBox):
                w.setCurrentText(str(s.default))
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setValue(s.default)
