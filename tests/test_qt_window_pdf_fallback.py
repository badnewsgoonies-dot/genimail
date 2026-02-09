import pytest

from genimail_qt.mixins import pdf as pdf_module
from genimail_qt.window import GeniMailQtWindow


class _Signal:
    def connect(self, fn):
        pass


class _FakePdfGraphicsView:
    """Stub for PdfGraphicsView used in test isolation."""
    pointClicked = _Signal()
    pageChanged = _Signal()

    def __init__(self):
        self._path = None

    def open_document(self, path):
        self._path = path


class _FakeSelf:
    """Minimal stub providing the methods _create_pdf_widget references."""
    def _on_pdf_point_clicked(self, x, y):
        pass

    def _on_pdf_page_changed(self, current, total):
        pass


def test_create_pdf_widget_returns_graphics_view(monkeypatch):
    """After the renderer swap, _create_pdf_widget always returns a PdfGraphicsView."""
    fake_view = _FakePdfGraphicsView()
    monkeypatch.setattr(pdf_module, "PdfGraphicsView", lambda: fake_view)

    fake_self = _FakeSelf()
    result = GeniMailQtWindow._create_pdf_widget(fake_self, "sample.pdf")

    assert result is fake_view
    assert fake_view._path == "sample.pdf"
