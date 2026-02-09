from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QApplication

import genimail_qt.pdf_graphics_view as pdf_graphics_view
from genimail_qt.pdf_graphics_view import PdfGraphicsView


class _FakeEvent:
    def __init__(self, button=Qt.LeftButton):
        self._button = button
        self._accepted = False

    def button(self):
        return self._button

    def pos(self):
        return QPointF(0.0, 0.0)

    def accept(self):
        self._accepted = True

    @property
    def accepted(self):
        return self._accepted


class _FakePixmapItem:
    def __init__(self, rect):
        self._rect = rect

    def boundingRect(self):
        return self._rect


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_mouse_press_ignores_clicks_outside_page_bounds(monkeypatch):
    _ensure_app()
    view = PdfGraphicsView()
    emitted = []
    fallback_calls = []
    view.pointClicked.connect(lambda x_pt, y_pt: emitted.append((x_pt, y_pt)))
    view._click_enabled = True
    view._scale = 2.0
    view._pixmap_item = _FakePixmapItem(QRectF(0.0, 0.0, 100.0, 100.0))
    monkeypatch.setattr(view, "mapToScene", lambda _pos: QPointF(150.0, 150.0))
    monkeypatch.setattr(
        pdf_graphics_view.QGraphicsView,
        "mousePressEvent",
        lambda _self, event: fallback_calls.append(event),
    )
    event = _FakeEvent()

    view.mousePressEvent(event)

    assert emitted == []
    assert event.accepted is False
    assert fallback_calls == [event]


def test_mouse_press_emits_pdf_coordinates_for_click_inside_page(monkeypatch):
    _ensure_app()
    view = PdfGraphicsView()
    emitted = []
    fallback_calls = []
    view.pointClicked.connect(lambda x_pt, y_pt: emitted.append((x_pt, y_pt)))
    view._click_enabled = True
    view._scale = 2.0
    view._pixmap_item = _FakePixmapItem(QRectF(0.0, 0.0, 100.0, 100.0))
    monkeypatch.setattr(view, "mapToScene", lambda _pos: QPointF(20.0, 40.0))
    monkeypatch.setattr(
        pdf_graphics_view.QGraphicsView,
        "mousePressEvent",
        lambda _self, event: fallback_calls.append(event),
    )
    event = _FakeEvent()

    view.mousePressEvent(event)

    assert emitted == [(10.0, 20.0)]
    assert event.accepted is True
    assert fallback_calls == []
