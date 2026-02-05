from collections.abc import Callable

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QWidget

from genimail_qt.constants import (
    TOAST_DEFAULT_DURATION_MS,
    TOAST_LAYOUT_MARGINS,
    TOAST_LAYOUT_SPACING,
    TOAST_MARGIN_PX,
    TOAST_TOP_OFFSET_PX,
)


class Toaster:
    def __init__(self, parent: QMainWindow, get_top_offset: Callable[[], int]) -> None:
        self.parent = parent
        self.get_top_offset = get_top_offset
        self._toast_frame = None
        self._toast_label = None
        self._toast_action = None
        self._toast_timer = QTimer(parent)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.hide)

    def build(self, container: QWidget) -> None:
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
        self._toast_frame.installEventFilter(self.parent)
        self._toast_label.installEventFilter(self.parent)
        self._set_kind("info")
        self.reposition()

    def _set_kind(self, kind: str) -> None:
        if self._toast_frame is None:
            return
        self._toast_frame.setProperty("toastKind", kind)
        self._toast_frame.style().unpolish(self._toast_frame)
        self._toast_frame.style().polish(self._toast_frame)

    def reposition(self) -> None:
        if self._toast_frame is None:
            return
        container = self.parent.centralWidget()
        if not container:
            return
        self._toast_frame.adjustSize()
        top_offset = self.get_top_offset() + TOAST_TOP_OFFSET_PX
        x = max(TOAST_MARGIN_PX, container.width() - self._toast_frame.width() - TOAST_MARGIN_PX)
        y = max(TOAST_MARGIN_PX, top_offset)
        self._toast_frame.move(x, y)

    def show(
        self,
        message: str,
        kind: str = "info",
        duration_ms: int = TOAST_DEFAULT_DURATION_MS,
        action: Callable[[], None] | None = None,
    ) -> None:
        if self._toast_frame is None or self._toast_label is None:
            return
        self._set_kind(kind)
        self._toast_label.setText(message)
        self._toast_action = action
        self._toast_frame.adjustSize()
        self.reposition()
        self._toast_frame.show()
        self._toast_frame.raise_()
        self._toast_timer.start(duration_ms)

    def hide(self) -> None:
        if self._toast_frame is not None:
            self._toast_frame.hide()
        self._toast_action = None

    def event_filter(self, obj, event: QEvent) -> bool:
        if obj in (self._toast_frame, self._toast_label):
            if event.type() == QEvent.MouseButtonPress and callable(self._toast_action):
                action = self._toast_action
                self.hide()
                action()
                return True
        return False


__all__ = ["Toaster"]
