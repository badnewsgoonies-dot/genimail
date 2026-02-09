from types import SimpleNamespace

import genimail_qt.mixins.pdf as pdf_module
from genimail_qt.mixins.pdf import PdfMixin, SavedRoom


class _FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FakeLineEdit:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value


class _FakeListWidget:
    def __init__(self):
        self.items = []

    def clear(self):
        self.items = []

    def addItem(self, text):
        self.items.append(text)

    def currentRow(self):
        return -1


class _FakeClipboard:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FakeToaster:
    def __init__(self):
        self.calls = []

    def show(self, message, kind=None, action=None):
        self.calls.append({"message": message, "kind": kind, "action": action})


class _FakePdfView:
    def __init__(self, page=0):
        self.current_page = page
        self.clear_calls = 0
        self.vertex_calls = []
        self.edge_calls = []

    def clear_overlays(self):
        self.clear_calls += 1

    def add_vertex_dot(self, x_pt, y_pt):
        self.vertex_calls.append((x_pt, y_pt))

    def add_edge_line(self, x0, y0, x1, y1):
        self.edge_calls.append((x0, y0, x1, y1))


class _Probe(PdfMixin):
    def __init__(self):
        self._view = _FakePdfView(page=3)
        self._poly_points = []
        self._saved_rooms = []
        self._cal_factor = 1.0
        self._cal_start = None
        self._has_cal = False

        self._pdf_wall_height_input = _FakeLineEdit("8ft")
        self._pdf_points_label = _FakeLabel()
        self._pdf_total_perim_label = _FakeLabel()
        self._pdf_total_wall_label = _FakeLabel()
        self._pdf_total_floor_label = _FakeLabel()
        self._pdf_rooms_list = _FakeListWidget()
        self.toaster = _FakeToaster()

    def _current_pdf_view(self):
        return self._view


def test_on_pdf_close_shape_saves_room_resets_polygon_and_updates_totals(monkeypatch):
    probe = _Probe()
    probe._cal_factor = 12.0
    probe._poly_points = [(72.0, 0.0), (72.0, 72.0), (0.0, 72.0)]
    captured = {}

    def _fake_compute_floor_plan(points_feet, scale_factor=1.0):
        captured["points_feet"] = list(points_feet)
        captured["scale_factor"] = scale_factor
        return SimpleNamespace(perimeter_feet=30.0, floor_area_sqft=45.0)

    monkeypatch.setattr(pdf_module, "compute_floor_plan", _fake_compute_floor_plan)
    monkeypatch.setattr(pdf_module, "parse_length_to_feet", lambda _value: 9.0)

    PdfMixin._on_pdf_close_shape(probe)

    assert captured["points_feet"] == [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert captured["scale_factor"] == 1.0
    assert probe._poly_points == []
    assert len(probe._saved_rooms) == 1
    room = probe._saved_rooms[0]
    assert room.points_count == 3
    assert room.perimeter_feet == 30.0
    assert room.wall_sqft == 270.0
    assert room.floor_sqft == 45.0
    assert room.page_index == 3
    assert room.points == [(72.0, 0.0), (72.0, 72.0), (0.0, 72.0)]
    assert room.is_wall is False
    assert probe._pdf_points_label.text == "Points: 0"
    assert probe._pdf_total_perim_label.text == "Perimeter: 30.0 ft"
    assert probe._pdf_total_wall_label.text == "Wall Sqft: 270"
    assert probe._pdf_total_floor_label.text == "Floor Sqft: 45"
    assert probe._pdf_rooms_list.items == ["1. 30.0 lf | 270 wall | 45 floor"]


def test_on_pdf_close_wall_computes_linear_feet_for_open_polyline(monkeypatch):
    probe = _Probe()
    probe._cal_factor = 12.0
    probe._poly_points = [(0.0, 0.0), (72.0, 0.0), (72.0, 72.0)]
    monkeypatch.setattr(pdf_module, "parse_length_to_feet", lambda _value: 10.0)

    PdfMixin._on_pdf_close_wall(probe)

    assert probe._poly_points == []
    assert len(probe._saved_rooms) == 1
    room = probe._saved_rooms[0]
    assert room.perimeter_feet == 2.0
    assert room.wall_sqft == 20.0
    assert room.floor_sqft == 0.0
    assert room.is_wall is True
    assert room.points == [(0.0, 0.0), (72.0, 0.0), (72.0, 72.0)]
    assert probe._pdf_rooms_list.items == ["1. Wall 2.0 lf | 20 sqft"]
    assert probe._pdf_total_perim_label.text == "Perimeter: 2.0 ft"
    assert probe._pdf_total_wall_label.text == "Wall Sqft: 20"
    assert probe._pdf_total_floor_label.text == "Floor Sqft: 0"


def test_on_pdf_clear_all_rooms_clears_state_and_overlays():
    probe = _Probe()
    probe._poly_points = [(10.0, 20.0)]
    probe._saved_rooms = [
        SavedRoom(
            points_count=3,
            perimeter_feet=12.0,
            wall_sqft=96.0,
            floor_sqft=35.0,
            points=[(1.0, 2.0), (3.0, 4.0), (2.0, 6.0)],
            page_index=3,
        )
    ]
    PdfMixin._rebuild_rooms_list(probe)
    PdfMixin._update_totals(probe)
    PdfMixin._update_measurement_labels(probe)

    PdfMixin._on_pdf_clear_all_rooms(probe)

    assert probe._saved_rooms == []
    assert probe._poly_points == []
    assert probe._view.clear_calls == 1
    assert probe._pdf_rooms_list.items == []
    assert probe._pdf_points_label.text == "Points: 0"
    assert probe._pdf_total_perim_label.text == "Perimeter: —"
    assert probe._pdf_total_wall_label.text == "Wall Sqft: —"
    assert probe._pdf_total_floor_label.text == "Floor Sqft: —"


def test_on_pdf_copy_totals_writes_expected_clipboard_payload(monkeypatch):
    probe = _Probe()
    probe._saved_rooms = [
        SavedRoom(
            points_count=4,
            perimeter_feet=10.0,
            wall_sqft=80.0,
            floor_sqft=30.0,
            points=[(0.0, 0.0)],
            page_index=1,
        ),
        SavedRoom(
            points_count=3,
            perimeter_feet=15.5,
            wall_sqft=124.0,
            floor_sqft=0.0,
            points=[(0.0, 0.0)],
            page_index=2,
            is_wall=True,
        ),
    ]
    fake_clipboard = _FakeClipboard()
    monkeypatch.setattr(pdf_module.QApplication, "clipboard", lambda: fake_clipboard)

    PdfMixin._on_pdf_copy_totals(probe)

    assert fake_clipboard.text == "\n".join(
        [
            "Rooms: 2",
            "  1. 10.0 lf | 80 wall sqft | 30 floor sqft",
            "  2. 15.5 lf | 124 wall sqft | 0 floor sqft",
            "Totals:",
            "  Perimeter: 25.5 ft",
            "  Wall Sqft: 204",
            "  Floor Sqft: 30",
        ]
    )
    assert probe.toaster.calls and probe.toaster.calls[-1]["kind"] == "success"
