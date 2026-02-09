import genimail_qt.mixins.pdf as pdf_module
from genimail_qt.mixins.pdf import PdfMixin


class _FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FakeConfig:
    def __init__(self, payload=None):
        self.payload = dict(payload or {})

    def get(self, key, default=None):
        return self.payload.get(key, default)

    def set(self, key, value):
        self.payload[key] = value


class _FakePdfView:
    def __init__(self, doc_key="file:sample.pdf"):
        self.doc_key = doc_key
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
        self._pdf_cal_status = _FakeLabel()
        self._cal_factor = 1.0
        self._has_cal = False
        self._cal_start = None
        self.config = _FakeConfig()
        self._view = _FakePdfView()

    def _current_pdf_view(self):
        return self._view


def test_save_and_load_calibration_roundtrip():
    probe = _Probe()

    PdfMixin._save_calibration(probe, "file:sample.pdf", 2.5)
    assert probe.config.get("pdf_calibration") == {"file:sample.pdf": {"cal_factor": 2.5}}

    probe._cal_factor = 1.0
    probe._has_cal = False
    PdfMixin._load_calibration(probe, "file:sample.pdf")

    assert probe._has_cal is True
    assert probe._cal_factor == 2.5
    assert probe._pdf_cal_status.text == "Cal: x2.5000"


def test_load_calibration_invalid_entry_falls_back_to_not_calibrated():
    probe = _Probe()
    probe.config = _FakeConfig({"pdf_calibration": {"file:sample.pdf": {"cal_factor": "not-a-number"}}})

    PdfMixin._load_calibration(probe, "file:sample.pdf")

    assert probe._has_cal is False
    assert probe._cal_factor == 1.0
    assert probe._pdf_cal_status.text == "Not calibrated"


def test_on_cal_click_two_step_flow_updates_factor_and_persists(monkeypatch):
    probe = _Probe()
    monkeypatch.setattr(pdf_module.QInputDialog, "getText", lambda *args, **kwargs: ("10ft", True))
    monkeypatch.setattr(pdf_module, "parse_length_to_feet", lambda _raw: 10.0)

    PdfMixin._on_cal_click(probe, 0.0, 0.0)
    assert probe._cal_start == (0.0, 0.0)
    assert probe._pdf_cal_status.text == "Click second point..."

    PdfMixin._on_cal_click(probe, 72.0, 0.0)

    assert probe._cal_start is None
    assert probe._has_cal is True
    assert probe._cal_factor == 120.0
    assert probe._pdf_cal_status.text == "Cal: x120.0000"
    assert probe._view.vertex_calls == [(0.0, 0.0), (72.0, 0.0)]
    assert probe._view.edge_calls == [(0.0, 0.0, 72.0, 0.0)]
    assert probe._view.clear_calls == 2
    assert probe.config.get("pdf_calibration", {}).get("file:sample.pdf", {}).get("cal_factor") == 120.0


def test_on_cal_click_rejects_too_close_points_without_prompt(monkeypatch):
    probe = _Probe()
    monkeypatch.setattr(pdf_module.QInputDialog, "getText", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("should not prompt")))

    PdfMixin._on_cal_click(probe, 10.0, 10.0)
    PdfMixin._on_cal_click(probe, 10.2, 10.2)

    assert probe._cal_start is None
    assert probe._has_cal is False
    assert probe._cal_factor == 1.0
    assert probe._pdf_cal_status.text == "Points too close. Try again."
