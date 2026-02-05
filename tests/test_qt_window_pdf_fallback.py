import pytest

from genimail_qt.mixins import pdf as pdf_module
from genimail_qt.window import GeniMailQtWindow


class _FakeWindow:
    def __init__(self, qt_result=None, web_result=None, qt_error=None, web_error=None):
        self.calls = []
        self.qt_result = qt_result
        self.web_result = web_result
        self.qt_error = qt_error
        self.web_error = web_error

    def _create_qtpdf_widget(self, path):
        self.calls.append(("qt", path))
        if self.qt_error:
            raise self.qt_error
        return self.qt_result

    def _create_webengine_pdf_widget(self, path):
        self.calls.append(("web", path))
        if self.web_error:
            raise self.web_error
        return self.web_result


def test_create_pdf_widget_prefers_qtpdf(monkeypatch):
    monkeypatch.setattr(pdf_module, "HAS_QTPDF", True)
    fake = _FakeWindow(qt_result="qt-view", web_result="web-view")

    result = GeniMailQtWindow._create_pdf_widget(fake, "sample.pdf")

    assert result == "qt-view"
    assert fake.calls == [("qt", "sample.pdf")]


def test_create_pdf_widget_falls_back_to_webengine(monkeypatch):
    monkeypatch.setattr(pdf_module, "HAS_QTPDF", True)
    fake = _FakeWindow(qt_error=RuntimeError("qt failed"), web_result="web-view")

    result = GeniMailQtWindow._create_pdf_widget(fake, "sample.pdf")

    assert result == "web-view"
    assert fake.calls == [("qt", "sample.pdf"), ("web", "sample.pdf")]


def test_create_pdf_widget_uses_webengine_when_qtpdf_unavailable(monkeypatch):
    monkeypatch.setattr(pdf_module, "HAS_QTPDF", False)
    fake = _FakeWindow(qt_result="qt-view", web_result="web-view")

    result = GeniMailQtWindow._create_pdf_widget(fake, "sample.pdf")

    assert result == "web-view"
    assert fake.calls == [("web", "sample.pdf")]


def test_create_pdf_widget_raises_when_all_renderers_fail(monkeypatch):
    monkeypatch.setattr(pdf_module, "HAS_QTPDF", True)
    fake = _FakeWindow(
        qt_error=RuntimeError("qt failed"),
        web_error=RuntimeError("web failed"),
    )

    with pytest.raises(RuntimeError) as exc:
        GeniMailQtWindow._create_pdf_widget(fake, "sample.pdf")

    assert "QtPdf" in str(exc.value)
    assert "WebEngine" in str(exc.value)
