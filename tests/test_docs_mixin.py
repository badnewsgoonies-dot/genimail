import os

from genimail_qt.mixins.docs import DocsMixin, _MAX_RECENT


class _Config:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def _make_probe(config_values=None):
    class _Probe(DocsMixin):
        pass

    probe = _Probe()
    probe.config = _Config(config_values)
    return probe


# ------------------------------------------------------------------
# _add_to_recent
# ------------------------------------------------------------------


def test_add_to_recent_stores_path(tmp_path):
    probe = _make_probe()
    path = str(tmp_path / "test.docx")
    DocsMixin._add_to_recent(probe, path)
    recent = probe.config.get("docs_recent_files")
    assert len(recent) == 1
    assert os.path.normpath(path) in recent[0]


def test_add_to_recent_moves_duplicate_to_front(tmp_path):
    a = str(tmp_path / "a.docx")
    b = str(tmp_path / "b.docx")
    probe = _make_probe({"docs_recent_files": [a, b]})
    DocsMixin._add_to_recent(probe, b)
    recent = probe.config.get("docs_recent_files")
    assert recent[0] == os.path.normpath(os.path.abspath(b))
    assert len(recent) == 2


def test_add_to_recent_caps_at_max(tmp_path):
    existing = [str(tmp_path / f"file{i}.docx") for i in range(_MAX_RECENT)]
    probe = _make_probe({"docs_recent_files": existing})
    new_path = str(tmp_path / "new.docx")
    DocsMixin._add_to_recent(probe, new_path)
    recent = probe.config.get("docs_recent_files")
    assert len(recent) == _MAX_RECENT
    assert os.path.normpath(os.path.abspath(new_path)) == recent[0]


def test_add_to_recent_handles_corrupt_config(tmp_path):
    probe = _make_probe({"docs_recent_files": "not a list"})
    path = str(tmp_path / "test.docx")
    DocsMixin._add_to_recent(probe, path)
    recent = probe.config.get("docs_recent_files")
    assert isinstance(recent, list)
    assert len(recent) == 1


# ------------------------------------------------------------------
# _get_recent_files
# ------------------------------------------------------------------


def test_get_recent_files_filters_missing(tmp_path):
    existing = tmp_path / "exists.docx"
    existing.write_text("data")
    missing = str(tmp_path / "gone.docx")
    probe = _make_probe({"docs_recent_files": [str(existing), missing]})
    result = DocsMixin._get_recent_files(probe)
    assert result == [str(existing)]


def test_get_recent_files_filters_non_string_entries(tmp_path):
    existing = tmp_path / "ok.docx"
    existing.write_text("data")
    probe = _make_probe({"docs_recent_files": [str(existing), 123, None]})
    result = DocsMixin._get_recent_files(probe)
    assert result == [str(existing)]


# ------------------------------------------------------------------
# _new_doc_from_template (filesystem operation, no Qt)
# ------------------------------------------------------------------


def test_new_doc_from_template_copies_file(tmp_path, monkeypatch):
    template = tmp_path / "template.doc"
    template.write_text("Hello {{CLIENT_NAME}}")
    quotes = tmp_path / "quotes_out"
    quotes.mkdir()

    monkeypatch.setattr("genimail_qt.mixins.docs.DEFAULT_QUOTE_TEMPLATE_FILE", str(template))
    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(quotes))

    probe = _make_probe()
    # Stub out preview method that needs Qt
    opened_paths = []
    probe._open_doc_preview = lambda path, activate=False: opened_paths.append(path)

    DocsMixin._new_doc_from_template(probe)

    created = [f for f in os.listdir(str(quotes)) if f.startswith("NewDoc_")]
    assert len(created) == 1
    assert created[0].endswith(".doc")
    assert len(opened_paths) == 1


# ------------------------------------------------------------------
# _open_doc_preview (state management, no Qt widget)
# ------------------------------------------------------------------


def test_open_doc_preview_sets_path(tmp_path, monkeypatch):
    doc = tmp_path / "test.docx"
    doc.write_text("data")

    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(tmp_path))

    probe = _make_probe()
    # Stub the QAxWidget and label
    class _FakeAx:
        def __init__(self):
            self.control_path = None
        def setControl(self, path):
            self.control_path = path
            return True
        def show(self):
            pass
        def hide(self):
            pass
        def clear(self):
            self.control_path = None

    class _FakeLabel:
        def hide(self): pass
        def show(self): pass
        def setVisible(self, v): pass

    class _FakeList:
        def clear(self): pass
        def addItem(self, item): pass
        def count(self): return 0
        def setVisible(self, v): pass
        def blockSignals(self, b): pass

    class _FakeLayout:
        def insertWidget(self, idx, w, stretch=0): pass

    ax = _FakeAx()
    probe._doc_preview = ax
    probe._doc_preview_layout = _FakeLayout()
    probe._doc_preview_placeholder = _FakeLabel()
    probe._doc_list = _FakeList()
    probe._doc_empty_label = _FakeLabel()

    monkeypatch.setattr("genimail_qt.mixins.docs.QListWidgetItem", lambda text="": type("FI", (), {"setData": lambda s, r, v: None, "data": lambda s, r: None, "flags": lambda s: 0xFF, "setFlags": lambda s, f: None})())

    DocsMixin._open_doc_preview(probe, str(doc))

    assert probe._doc_preview_path == os.path.abspath(str(doc))
    assert ax.control_path == os.path.abspath(str(doc))


def test_close_doc_preview_clears_state(tmp_path):
    probe = _make_probe()

    class _FakeAx:
        def __init__(self):
            self.cleared = False
        def clear(self):
            self.cleared = True
        def hide(self):
            pass

    class _FakeLabel:
        def __init__(self):
            self.visible = False
        def show(self):
            self.visible = True

    probe._doc_preview = _FakeAx()
    probe._doc_preview_placeholder = _FakeLabel()
    probe._doc_preview_path = "C:\\some\\file.docx"

    DocsMixin._close_doc_preview(probe)

    assert probe._doc_preview_path is None
    assert probe._doc_preview.cleared is True
    assert probe._doc_preview_placeholder.visible is True


def test_open_doc_preview_falls_back_without_layout(tmp_path, monkeypatch):
    """When _doc_preview_layout doesn't exist, falls back to open_document_file."""
    doc = tmp_path / "test.docx"
    doc.write_text("data")

    opened = []
    monkeypatch.setattr("genimail_qt.mixins.docs.open_document_file", lambda p: opened.append(p) or True)

    probe = _make_probe()
    # No _doc_preview_layout attribute — simulates calling before tab is built

    DocsMixin._open_doc_preview(probe, str(doc))

    assert len(opened) == 1


# ------------------------------------------------------------------
# _refresh_doc_list (needs QListWidget stub)
# ------------------------------------------------------------------


class _FakeListItem:
    def __init__(self, text=""):
        self._text = text
        self._data = {}
        self._flags = 0xFF

    def setData(self, role, value):
        self._data[role] = value

    def data(self, role):
        return self._data.get(role)

    def flags(self):
        return self._flags

    def setFlags(self, f):
        self._flags = f


class _FakeListWidget:
    def __init__(self):
        self.items = []
        self._visible = True
        self._current_item = None

    def clear(self):
        self.items = []

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def setVisible(self, v):
        self._visible = v

    def blockSignals(self, b):
        pass

    def setCurrentItem(self, item):
        self._current_item = item

    def currentItem(self):
        return self._current_item


class _FakeLabelVis:
    def __init__(self):
        self._visible = True

    def setVisible(self, v):
        self._visible = v


def test_refresh_doc_list_finds_docs_in_folder(tmp_path, monkeypatch):
    (tmp_path / "a.docx").write_text("data")
    (tmp_path / "b.doc").write_text("data")
    (tmp_path / "c.txt").write_text("data")

    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(tmp_path))
    monkeypatch.setattr("genimail_qt.mixins.docs.QListWidgetItem", _FakeListItem)

    probe = _make_probe()
    probe._doc_list = _FakeListWidget()
    probe._doc_empty_label = _FakeLabelVis()

    DocsMixin._refresh_doc_list(probe)

    paths = [item._data.get(256) for item in probe._doc_list.items if item._data.get(256)]
    basenames = [os.path.basename(p) for p in paths]
    assert "a.docx" in basenames
    assert "b.doc" in basenames
    assert "c.txt" not in basenames
    assert probe._doc_list._visible is True
    assert probe._doc_empty_label._visible is False


def test_refresh_doc_list_shows_empty_label_when_no_docs(tmp_path, monkeypatch):
    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(tmp_path))
    monkeypatch.setattr("genimail_qt.mixins.docs.QListWidgetItem", _FakeListItem)

    probe = _make_probe()
    probe._doc_list = _FakeListWidget()
    probe._doc_empty_label = _FakeLabelVis()

    DocsMixin._refresh_doc_list(probe)

    assert probe._doc_list.count() == 0
    assert probe._doc_list._visible is False
    assert probe._doc_empty_label._visible is True


def test_refresh_doc_list_preserves_selected_path(tmp_path, monkeypatch):
    a_path = tmp_path / "a.docx"
    b_path = tmp_path / "b.docx"
    a_path.write_text("a")
    b_path.write_text("b")

    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(tmp_path))
    monkeypatch.setattr("genimail_qt.mixins.docs.QListWidgetItem", _FakeListItem)

    probe = _make_probe()
    probe._doc_list = _FakeListWidget()
    probe._doc_empty_label = _FakeLabelVis()

    DocsMixin._refresh_doc_list(probe, selected_path=str(b_path))

    selected = probe._doc_list.currentItem()
    assert selected is not None
    assert os.path.normpath(selected.data(256)) == os.path.normpath(str(b_path))


# ------------------------------------------------------------------
# setControl failure fallback
# ------------------------------------------------------------------


def test_open_doc_preview_falls_back_on_setcontrol_failure(tmp_path, monkeypatch):
    """When setControl() returns False, falls back to open_document_file."""
    doc = tmp_path / "bad.docx"
    doc.write_text("data")

    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(tmp_path))

    opened = []
    monkeypatch.setattr("genimail_qt.mixins.docs.open_document_file", lambda p: opened.append(p) or True)

    class _FailAx:
        def setControl(self, path):
            return False
        def show(self): pass
        def hide(self): pass
        def clear(self): pass

    class _FakeLabel:
        def hide(self): pass
        def show(self): pass

    class _FakeLayout:
        def insertWidget(self, idx, w, stretch=0): pass

    probe = _make_probe()
    probe._doc_preview = _FailAx()
    probe._doc_preview_layout = _FakeLayout()
    probe._doc_preview_placeholder = _FakeLabel()

    DocsMixin._open_doc_preview(probe, str(doc))

    assert len(opened) == 1
    assert probe._doc_preview_path is None  # should not be set on failure


# ------------------------------------------------------------------
# Attachment routing (.doc/.docx → _open_doc_preview)
# ------------------------------------------------------------------


def test_attachment_routes_docx_to_preview(tmp_path, monkeypatch):
    """_on_open_attachment_ready routes .docx to _open_doc_preview."""
    from genimail_qt.mixins.attachments import EmailAttachmentMixin

    monkeypatch.setattr("genimail_qt.mixins.attachments.PDF_DIR", str(tmp_path))

    class _Probe(EmailAttachmentMixin):
        pass

    probe = _Probe()
    preview_calls = []
    pdf_calls = []

    probe._open_doc_preview = lambda path, activate=False: preview_calls.append(path)
    probe._open_pdf_file = lambda path, activate=False: pdf_calls.append(path)
    probe._set_status = lambda msg: None
    probe._unique_output_path = staticmethod(lambda d, f: os.path.join(d, f))

    probe._on_open_attachment_ready((b"fake content", "test.docx"))

    assert len(preview_calls) == 1
    assert preview_calls[0].endswith(".docx")
    assert len(pdf_calls) == 0


def test_attachment_routes_pdf_to_pdf_viewer(tmp_path, monkeypatch):
    """_on_open_attachment_ready routes .pdf to _open_pdf_file."""
    from genimail_qt.mixins.attachments import EmailAttachmentMixin

    monkeypatch.setattr("genimail_qt.mixins.attachments.PDF_DIR", str(tmp_path))

    class _Probe(EmailAttachmentMixin):
        pass

    probe = _Probe()
    preview_calls = []
    pdf_calls = []

    probe._open_doc_preview = lambda path, activate=False: preview_calls.append(path)
    probe._open_pdf_file = lambda path, activate=False: pdf_calls.append(path)
    probe._set_status = lambda msg: None
    probe._unique_output_path = staticmethod(lambda d, f: os.path.join(d, f))

    probe._on_open_attachment_ready((b"fake content", "test.pdf"))

    assert len(pdf_calls) == 1
    assert len(preview_calls) == 0
