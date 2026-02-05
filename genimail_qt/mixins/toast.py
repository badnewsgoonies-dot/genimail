from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from genimail_qt.constants import (
    TOAST_DEFAULT_DURATION_MS,
    TOAST_LAYOUT_MARGINS,
    TOAST_LAYOUT_SPACING,
    TOAST_MARGIN_PX,
    TOAST_TOP_OFFSET_PX,
)


class ToastMixin:
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast()

    def _build_toast(self, container):
        self._toast_frame = QFrame(container)
        self._toast_frame.setObjectName("toastFrame")
        toast_layout = QHBoxLayout(self._toast_frame)
        toast_layout.setContentsMargins(*TOAST_LAYOUT_MARGINS)
        toast_layout.setSpacing(TOAST_LAYOUT_SPACING)
        self._toast_label = QLabel("")
        self._toast_label.setObjectName("toastLabel")
        self._toast_label.setWordWrap(True)
        toast_layout.addWidget(self._toast_label, 1)
        self._toast_frame.hide()
        self._toast_frame.installEventFilter(self)
        self._toast_label.installEventFilter(self)
        self._toast_action = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)
        self._set_toast_kind("info")
        self._position_toast()

    def _set_toast_kind(self, kind):
        if not hasattr(self, "_toast_frame"):
            return
        self._toast_frame.setProperty("toastKind", kind)
        self._toast_frame.style().unpolish(self._toast_frame)
        self._toast_frame.style().polish(self._toast_frame)

    def _position_toast(self):
        if not hasattr(self, "_toast_frame"):
            return
        container = self.centralWidget()
        if not container:
            return
        self._toast_frame.adjustSize()
        top_offset = (self._top_bar.height() if hasattr(self, "_top_bar") else 0) + TOAST_TOP_OFFSET_PX
        x = max(TOAST_MARGIN_PX, container.width() - self._toast_frame.width() - TOAST_MARGIN_PX)
        y = max(TOAST_MARGIN_PX, top_offset)
        self._toast_frame.move(x, y)

    def _show_toast(self, message, kind="info", duration_ms=TOAST_DEFAULT_DURATION_MS, action=None):
        if not hasattr(self, "_toast_frame"):
            return
        self._set_toast_kind(kind)
        self._toast_label.setText(message)
        self._toast_action = action
        self._toast_frame.adjustSize()
        self._position_toast()
        self._toast_frame.show()
        self._toast_frame.raise_()
        self._toast_timer.start(duration_ms)

    def _hide_toast(self):
        if hasattr(self, "_toast_frame"):
            self._toast_frame.hide()
        self._toast_action = None

    def eventFilter(self, obj, event):
        if obj in (getattr(self, "_toast_frame", None), getattr(self, "_toast_label", None)):
            if event.type() == QEvent.MouseButtonPress and callable(getattr(self, "_toast_action", None)):
                action = self._toast_action
                self._hide_toast()
                action()
                return True
        return super().eventFilter(obj, event)


__all__ = ["ToastMixin"]
