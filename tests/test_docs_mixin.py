import os
import shutil
import tempfile

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
    # Stub out methods that need Qt
    opened_paths = []
    probe._open_doc_file = lambda path: opened_paths.append(path)

    DocsMixin._new_doc_from_template(probe)

    created = [f for f in os.listdir(str(quotes)) if f.startswith("NewDoc_")]
    assert len(created) == 1
    assert created[0].endswith(".doc")
    assert len(opened_paths) == 1


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

    def clear(self):
        self.items = []

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def setVisible(self, v):
        self._visible = v


class _FakeLabel:
    def __init__(self):
        self._visible = True

    def setVisible(self, v):
        self._visible = v


def test_refresh_doc_list_finds_docs_in_folder(tmp_path, monkeypatch):
    (tmp_path / "a.docx").write_text("data")
    (tmp_path / "b.doc").write_text("data")
    (tmp_path / "c.txt").write_text("data")

    monkeypatch.setattr("genimail_qt.mixins.docs.QUOTE_DIR", str(tmp_path))
    # Patch QListWidgetItem to our fake so we can inspect data
    monkeypatch.setattr("genimail_qt.mixins.docs.QListWidgetItem", _FakeListItem)

    probe = _make_probe()
    probe._doc_list = _FakeListWidget()
    probe._doc_empty_label = _FakeLabel()

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
    probe._doc_empty_label = _FakeLabel()

    DocsMixin._refresh_doc_list(probe)

    assert probe._doc_list.count() == 0
    assert probe._doc_list._visible is False
    assert probe._doc_empty_label._visible is True
