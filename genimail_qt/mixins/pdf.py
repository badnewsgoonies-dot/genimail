import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QVBoxLayout, QWidget

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    HAS_QTPDF = True
except Exception:
    QPdfDocument = None
    QPdfView = None
    HAS_QTPDF = False

from genimail.paths import PDF_DIR
from genimail_qt.webview_page import FilteredWebEnginePage


class PdfMixin:
    def _open_pdf_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", PDF_DIR, "PDF Files (*.pdf);;All Files (*.*)")
        if not path:
            return
        self._open_pdf_file(path, activate=True)

    def _open_pdf_file(self, path, activate=False):
        normalized = os.path.abspath(path)
        if not os.path.isfile(normalized):
            QMessageBox.warning(self, "PDF Not Found", f"Could not find PDF:\n{normalized}")
            return
        existing_index = self._find_pdf_tab_index(normalized)
        if existing_index is not None:
            self.pdf_tabs.setCurrentIndex(existing_index)
            if activate:
                self.workspace_tabs.setCurrentWidget(self.pdf_tab)
            return

        for idx in reversed(range(self.pdf_tabs.count())):
            widget = self.pdf_tabs.widget(idx)
            if widget is not None and widget.property("is_placeholder"):
                self.pdf_tabs.removeTab(idx)
                widget.deleteLater()

        try:
            view = self._create_pdf_widget(normalized)
        except Exception as exc:
            QMessageBox.critical(self, "PDF Load Error", f"Could not open PDF:\n{normalized}\n\n{exc}")
            return

        view.setProperty("pdf_path", normalized.lower())
        tab_label = os.path.basename(normalized)
        self.pdf_tabs.addTab(view, tab_label)
        self.pdf_tabs.setCurrentWidget(view)
        if activate:
            self.workspace_tabs.setCurrentWidget(self.pdf_tab)
        self._set_status(f"Opened PDF: {tab_label}")

    def _create_pdf_widget(self, normalized_path):
        errors = []
        if HAS_QTPDF:
            try:
                return self._create_qtpdf_widget(normalized_path)
            except Exception as exc:
                errors.append(f"QtPdf: {exc}")

        try:
            return self._create_webengine_pdf_widget(normalized_path)
        except Exception as exc:
            errors.append(f"WebEngine: {exc}")

        detail = "; ".join(errors) if errors else "No PDF renderer available."
        raise RuntimeError(detail)

    def _create_qtpdf_widget(self, normalized_path):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        document = QPdfDocument(container)
        load_error = document.load(normalized_path)
        if load_error != QPdfDocument.Error.None_:
            raise RuntimeError(f"QtPdf load failed: {load_error.name}")

        view = QPdfView(container)
        view.setDocument(document)
        view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        view.setPageMode(QPdfView.PageMode.MultiPage)
        layout.addWidget(view, 1)

        container._pdf_document = document
        container._pdf_view = view
        return container

    def _create_webengine_pdf_widget(self, normalized_path):
        view = self._create_web_view("pdf")
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        view.setUrl(QUrl.fromLocalFile(normalized_path))
        return view

    def _create_web_view(self, surface_name):
        view = QWebEngineView()
        page = FilteredWebEnginePage(surface_name, view)
        view.setPage(page)
        self._web_page_sources[page] = surface_name
        self._bind_web_downloads(view)
        return view

    def _bind_web_downloads(self, view):
        profile = view.page().profile()
        profile_id = id(profile)
        if profile_id in self._download_profile_ids:
            return
        profile.downloadRequested.connect(self._on_web_download_requested)
        self._download_profile_ids.add(profile_id)

    def _on_web_download_requested(self, download):
        page = download.page()
        source = self._web_page_sources.get(page, "web")
        message_id = (self.current_message or {}).get("id") if source == "email" else None
        if message_id:
            download.setProperty("message_id", message_id)
        download.setProperty("download_source", source)

        os.makedirs(PDF_DIR, exist_ok=True)
        suggested_name = download.downloadFileName() or "download.bin"
        target_path = self._unique_output_path(PDF_DIR, suggested_name)
        download.setDownloadDirectory(os.path.dirname(target_path))
        download.setDownloadFileName(os.path.basename(target_path))
        download.stateChanged.connect(lambda state, dl=download: self._on_web_download_state_changed(dl, state))
        download.accept()
        self._set_status(f"Downloading {os.path.basename(target_path)}...")

    def _on_web_download_state_changed(self, download, state):
        if state != QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            return
        directory = download.downloadDirectory() or ""
        filename = download.downloadFileName() or ""
        path = os.path.join(directory, filename) if directory and filename else ""
        message_id = download.property("message_id")
        if path and message_id:
            downloads = self.cloud_pdf_downloads.get(message_id, [])
            existing_paths = {entry.get("path") for entry in downloads if entry.get("path")}
            if path not in existing_paths:
                downloads.append({"path": path, "from_cache": False})
                self.cloud_pdf_downloads[message_id] = downloads
            if (self.current_message or {}).get("id") == message_id:
                self._update_cloud_download_list(message_id)
        if path:
            self._set_status(f"Downloaded {os.path.basename(path)}")
            self._show_toast(
                f"Download complete · {os.path.basename(path)}",
                kind="success",
                action=lambda p=path: self._open_download_path(p),
            )

    def _find_pdf_tab_index(self, path):
        normalized = path.lower()
        for idx in range(self.pdf_tabs.count()):
            widget = self.pdf_tabs.widget(idx)
            if widget is None:
                continue
            if widget.property("pdf_path") == normalized:
                return idx
        return None

    def _on_pdf_tab_close_requested(self, index):
        widget = self.pdf_tabs.widget(index)
        if widget is not None:
            self.pdf_tabs.removeTab(index)
            widget.deleteLater()
        if self.pdf_tabs.count() == 0:
            self._add_pdf_placeholder_tab()

    def _close_current_pdf_tab(self):
        idx = self.pdf_tabs.currentIndex()
        if idx >= 0:
            self._on_pdf_tab_close_requested(idx)

    def _add_pdf_placeholder_tab(self):
        placeholder = QLabel("Open a PDF to view it here.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setProperty("is_placeholder", True)
        self.pdf_tabs.addTab(placeholder, "Current PDF")

    @staticmethod
    def _unique_output_path(directory, filename):
        if not directory:
            return filename
        name = os.path.basename(filename or "download.bin")
        candidate = os.path.join(directory, name)
        if not os.path.exists(candidate):
            return candidate
        base, ext = os.path.splitext(name)
        index = 1
        while True:
            candidate = os.path.join(directory, f"{base}-{index}{ext}")
            if not os.path.exists(candidate):
                return candidate
            index += 1


__all__ = ["PdfMixin"]
