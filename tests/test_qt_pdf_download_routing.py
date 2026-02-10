import os

import genimail_qt.mixins.pdf as pdf_module
from genimail_qt.mixins.pdf import PdfMixin


class _FakeToaster:
    def __init__(self):
        self.calls = []

    def show(self, message, kind=None, action=None):
        self.calls.append({"message": message, "kind": kind, "action": action})


class _FakeDownload:
    def __init__(self, directory, filename):
        self._directory = directory
        self._filename = filename

    def downloadDirectory(self):
        return self._directory

    def downloadFileName(self):
        return self._filename


class _Probe(PdfMixin):
    def __init__(self):
        self.toaster = _FakeToaster()
        self.status_messages = []
        self.preview_calls = []
        self.pdf_calls = []
        self.result_buttons = []

    def _set_status(self, message):
        self.status_messages.append(message)

    def _open_doc_preview(self, path, activate=False):
        self.preview_calls.append((path, activate))

    def _open_pdf_file(self, path, activate=False):
        self.pdf_calls.append((path, activate))

    def _add_download_result_button(self, path):
        self.result_buttons.append(path)


def test_on_web_download_state_changed_routes_docx_action_to_preview(tmp_path):
    probe = _Probe()
    download = _FakeDownload(str(tmp_path), "scope.docx")

    PdfMixin._on_web_download_state_changed(
        probe,
        download,
        pdf_module.QWebEngineDownloadRequest.DownloadState.DownloadCompleted,
    )

    path = os.path.join(str(tmp_path), "scope.docx")
    assert probe.status_messages[-1] == "Downloaded scope.docx"
    assert probe.result_buttons == [path]
    action = probe.toaster.calls[-1]["action"]
    assert callable(action)

    action()

    assert probe.preview_calls == [(path, True)]
    assert probe.pdf_calls == []


def test_on_web_download_state_changed_routes_pdf_action_to_pdf_view(tmp_path):
    probe = _Probe()
    download = _FakeDownload(str(tmp_path), "plan.pdf")

    PdfMixin._on_web_download_state_changed(
        probe,
        download,
        pdf_module.QWebEngineDownloadRequest.DownloadState.DownloadCompleted,
    )

    path = os.path.join(str(tmp_path), "plan.pdf")
    action = probe.toaster.calls[-1]["action"]
    assert callable(action)

    action()

    assert probe.pdf_calls == [(path, True)]
    assert probe.preview_calls == []
