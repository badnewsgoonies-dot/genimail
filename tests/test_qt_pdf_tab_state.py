import genimail_qt.mixins.pdf as pdf_module
from genimail_qt.mixins.pdf import PdfMixin, SavedRoom


class _FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FakeToolGroup:
    def __init__(self, tool_id):
        self._tool_id = tool_id

    def checkedId(self):
        return self._tool_id


class _FakePdfGraphicsView:
    def __init__(self, doc_key, page_count=1, current_page=0):
        self.doc_key = doc_key
        self.page_count = page_count
        self.current_page = current_page
        self.click_enabled_calls = []
        self.closed = False
        self.deleted = False

    def set_click_enabled(self, enabled):
        self.click_enabled_calls.append(enabled)

    def close_document(self):
        self.closed = True

    def deleteLater(self):
        self.deleted = True


class _FakeTabWidget:
    def __init__(self, widgets):
        self._widgets = list(widgets)

    def widget(self, index):
        if 0 <= index < len(self._widgets):
            return self._widgets[index]
        return None

    def removeTab(self, index):
        self._widgets.pop(index)

    def count(self):
        return len(self._widgets)


class _Probe(PdfMixin):
    def __init__(self, widgets, tool_id):
        self.pdf_tabs = _FakeTabWidget(widgets)
        self._pdf_tool_group = _FakeToolGroup(tool_id)
        self._pdf_cal_status = _FakeLabel()
        self._pdf_tab_states = {}
        self._poly_points = []
        self._saved_rooms = []
        self._cal_factor = 1.0
        self._has_cal = False
        self._cal_start = None

        self.page_updates = []
        self.measure_label_updates = 0
        self.rooms_list_rebuilds = 0
        self.totals_updates = 0
        self.overlay_redraws = 0
        self.loaded_calibration_keys = []
        self.placeholder_added = 0

    def _update_pdf_page_label(self, current, total):
        self.page_updates.append((current, total))

    def _update_measurement_labels(self):
        self.measure_label_updates += 1

    def _rebuild_rooms_list(self):
        self.rooms_list_rebuilds += 1

    def _update_totals(self):
        self.totals_updates += 1

    def _redraw_all_room_overlays(self):
        self.overlay_redraws += 1

    def _load_calibration(self, doc_key):
        self.loaded_calibration_keys.append(doc_key)
        self._has_cal = False
        self._cal_factor = 1.0

    def _add_pdf_placeholder_tab(self):
        self.placeholder_added += 1


def test_on_pdf_tab_changed_saves_previous_and_restores_new_state(monkeypatch):
    monkeypatch.setattr(pdf_module, "PdfGraphicsView", _FakePdfGraphicsView)
    view_a = _FakePdfGraphicsView("doc:a", page_count=5, current_page=2)
    view_b = _FakePdfGraphicsView("doc:b", page_count=3, current_page=0)
    probe = _Probe([view_a, view_b], tool_id=2)
    probe._pdf_last_active_view = view_a
    probe._poly_points = [(1.0, 2.0)]
    probe._saved_rooms = [SavedRoom(3, 12.0, 90.0, 30.0, points=[(1.0, 2.0)], page_index=2)]
    probe._cal_factor = 4.0
    probe._has_cal = True
    probe._cal_start = (9.0, 9.0)
    probe._pdf_tab_states["doc:b"] = {
        "poly_points": [(8.0, 8.0), (9.0, 9.0)],
        "saved_rooms": ["room-b"],
        "cal_factor": 2.25,
        "has_cal": True,
        "cal_start": (1.0, 1.0),
    }

    PdfMixin._on_pdf_tab_changed(probe, 1)

    assert probe._pdf_tab_states["doc:a"]["poly_points"] == [(1.0, 2.0)]
    assert probe._pdf_tab_states["doc:a"]["cal_factor"] == 4.0
    assert probe._pdf_tab_states["doc:a"]["has_cal"] is True
    assert probe._pdf_tab_states["doc:a"]["cal_start"] == (9.0, 9.0)
    assert probe._poly_points == [(8.0, 8.0), (9.0, 9.0)]
    assert probe._saved_rooms == ["room-b"]
    assert probe._cal_factor == 2.25
    assert probe._has_cal is True
    assert probe._cal_start == (1.0, 1.0)
    assert probe._pdf_last_active_view is view_b
    assert probe.page_updates[-1] == (0, 3)
    assert view_b.click_enabled_calls == [True]
    assert probe._pdf_cal_status.text == "Cal: x2.2500"


def test_on_pdf_tab_changed_initializes_new_tab_state_when_missing(monkeypatch):
    monkeypatch.setattr(pdf_module, "PdfGraphicsView", _FakePdfGraphicsView)
    view_a = _FakePdfGraphicsView("doc:a")
    view_b = _FakePdfGraphicsView("doc:new", page_count=7, current_page=4)
    probe = _Probe([view_a, view_b], tool_id=0)
    probe._pdf_last_active_view = view_a
    probe._poly_points = [(2.0, 3.0)]
    probe._saved_rooms = [SavedRoom(3, 9.0, 72.0, 20.0)]
    probe._cal_factor = 3.0
    probe._has_cal = True
    probe._cal_start = (5.0, 5.0)

    PdfMixin._on_pdf_tab_changed(probe, 1)

    assert probe.loaded_calibration_keys == ["doc:new"]
    assert probe._poly_points == []
    assert probe._saved_rooms == []
    assert probe._has_cal is False
    assert probe._cal_factor == 1.0
    assert view_b.click_enabled_calls == [False]
    assert probe._pdf_cal_status.text == "Not calibrated"
    assert probe.page_updates[-1] == (4, 7)


def test_on_pdf_tab_close_requested_removes_tab_state_and_closes_document(monkeypatch):
    monkeypatch.setattr(pdf_module, "PdfGraphicsView", _FakePdfGraphicsView)
    view_a = _FakePdfGraphicsView("doc:a")
    view_b = _FakePdfGraphicsView("doc:b")
    probe = _Probe([view_a, view_b], tool_id=2)
    probe._pdf_tab_states = {"doc:a": {"poly_points": [1]}, "doc:b": {"poly_points": [2]}}

    PdfMixin._on_pdf_tab_close_requested(probe, 0)

    assert "doc:a" not in probe._pdf_tab_states
    assert "doc:b" in probe._pdf_tab_states
    assert view_a.closed is True
    assert view_a.deleted is True
    assert probe.pdf_tabs.count() == 1
    assert probe.placeholder_added == 0
