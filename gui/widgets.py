from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)


class ModernStepper(QWidget):
    valueChanged = Signal(int)

    def __init__(self, minimum=1, maximum=12, value=1, parent=None):
        super().__init__(parent)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setObjectName("StepperValue")

        self.minus = QPushButton("−")
        self.plus = QPushButton("+")
        self.minus.setObjectName("StepperButton")
        self.plus.setObjectName("StepperButton")
        self.minus.setFixedWidth(34)
        self.plus.setFixedWidth(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.plus)

        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        self.spin.valueChanged.connect(self.valueChanged)

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.minus.setEnabled(enabled)
        self.plus.setEnabled(enabled)
        self.spin.setEnabled(enabled)


class ModernDoubleStepper(QWidget):
    valueChanged = Signal(float)

    def __init__(self, minimum=0.0, maximum=5.0, value=0.0, step=0.05, parent=None):
        super().__init__(parent)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setDecimals(2)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setObjectName("StepperValue")

        self.minus = QPushButton("−")
        self.plus = QPushButton("+")
        self.minus.setObjectName("StepperButton")
        self.plus.setObjectName("StepperButton")
        self.minus.setFixedWidth(32)
        self.plus.setFixedWidth(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.plus)

        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        self.spin.valueChanged.connect(self.valueChanged)

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)


class InfoBadge(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("InfoBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class NoWheelSpinBox(QSpinBox):
    """Spin box that ignores mouse-wheel changes."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Double spin box that ignores mouse-wheel changes."""

    def wheelEvent(self, event):
        event.ignore()


class CompactNumberStepper(QWidget):
    valueChanged = Signal(float)

    def __init__(
        self,
        minimum: float,
        maximum: float,
        value: float,
        step: float,
        decimals: int = 0,
        suffix: str = "",
        parent=None,
    ):
        super().__init__(parent)

        self._is_float = decimals > 0
        if self._is_float:
            self.spin = NoWheelDoubleSpinBox()
            self.spin.setDecimals(decimals)
        else:
            self.spin = NoWheelSpinBox()

        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.spin.setSuffix(suffix)
        self.spin.setKeyboardTracking(False)
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setObjectName("CompactStepperValue")

        self.minus = QPushButton("−")
        self.plus = QPushButton("+")
        for button in (self.minus, self.plus):
            button.setObjectName("CompactStepperButton")
            button.setFixedSize(28, 30)

        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        # QSpinBox emits int and QDoubleSpinBox emits float.
        # Convert both to float before forwarding through this wrapper.
        self.spin.valueChanged.connect(
            lambda new_value: self.valueChanged.emit(float(new_value))
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.plus)

        self.setMaximumWidth(160)
        self.setMinimumWidth(122)

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.spin.setEnabled(enabled)
        self.minus.setEnabled(enabled)
        self.plus.setEnabled(enabled)

    def setReadOnly(self, read_only):
        self.spin.setReadOnly(read_only)

    def blockSignals(self, block):
        self.spin.blockSignals(block)
        return super().blockSignals(block)
