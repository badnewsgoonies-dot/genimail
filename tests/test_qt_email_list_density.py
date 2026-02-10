from genimail_qt.constants import (
    EMAIL_LIST_DENSITY_COMFORTABLE,
    EMAIL_LIST_DENSITY_COMPACT,
    EMAIL_LIST_DENSITY_CONFIG_KEY,
)
from genimail_qt.mixins import email_list as email_list_module
from genimail_qt.mixins.email_list import EmailListMixin, _normalize_density_mode


class _Config:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class _Viewport:
    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1


class _ListWidget:
    def __init__(self):
        self.layouts = 0
        self._viewport = _Viewport()
        self.delegate = None

    def doItemsLayout(self):
        self.layouts += 1

    def viewport(self):
        return self._viewport

    def setItemDelegate(self, delegate):
        self.delegate = delegate


class _ToggleBtn:
    def __init__(self):
        self.checked = False
        self.block_calls = []

    def blockSignals(self, blocked):
        self.block_calls.append(bool(blocked))

    def setChecked(self, checked):
        self.checked = bool(checked)


def test_normalize_density_mode_defaults_to_comfortable():
    assert _normalize_density_mode(None) == EMAIL_LIST_DENSITY_COMFORTABLE
    assert _normalize_density_mode("") == EMAIL_LIST_DENSITY_COMFORTABLE
    assert _normalize_density_mode("invalid") == EMAIL_LIST_DENSITY_COMFORTABLE
    assert _normalize_density_mode(" COMPACT ") == EMAIL_LIST_DENSITY_COMPACT


def test_get_email_list_density_mode_reads_and_normalizes_config():
    class _Probe(EmailListMixin):
        pass

    probe = _Probe()
    probe.config = _Config({EMAIL_LIST_DENSITY_CONFIG_KEY: "CoMpAcT"})

    assert EmailListMixin._get_email_list_density_mode(probe) == EMAIL_LIST_DENSITY_COMPACT
    assert probe._email_list_density == EMAIL_LIST_DENSITY_COMPACT


def test_set_email_list_density_mode_persists_and_refreshes():
    class _Delegate:
        def __init__(self):
            self.mode = None

        def set_density_mode(self, mode):
            self.mode = mode

    class _Probe(EmailListMixin):
        pass

    probe = _Probe()
    probe.config = _Config()
    probe.message_list = _ListWidget()
    probe._company_color_delegate = _Delegate()
    probe.email_density_compact_btn = _ToggleBtn()
    probe.email_density_comfortable_btn = _ToggleBtn()

    EmailListMixin._set_email_list_density_mode(probe, EMAIL_LIST_DENSITY_COMPACT, persist=True)

    assert probe._email_list_density == EMAIL_LIST_DENSITY_COMPACT
    assert probe._company_color_delegate.mode == EMAIL_LIST_DENSITY_COMPACT
    assert probe.message_list.layouts == 1
    assert probe.message_list.viewport().updates == 1
    assert probe.config.get(EMAIL_LIST_DENSITY_CONFIG_KEY) == EMAIL_LIST_DENSITY_COMPACT
    assert probe.email_density_compact_btn.checked is True
    assert probe.email_density_comfortable_btn.checked is False


def test_ensure_company_color_delegate_applies_theme_color_and_density(monkeypatch):
    class _Delegate:
        def __init__(self, parent=None):
            self.parent = parent
            self.color_map = None
            self.theme_mode = None
            self.density_mode = None

        def set_color_map(self, color_map):
            self.color_map = dict(color_map or {})

        def set_theme_mode(self, mode):
            self.theme_mode = mode

        def set_density_mode(self, mode):
            self.density_mode = mode

    monkeypatch.setattr(email_list_module, "CompanyColorDelegate", _Delegate)

    class _Probe(EmailListMixin):
        pass

    probe = _Probe()
    probe.config = _Config({EMAIL_LIST_DENSITY_CONFIG_KEY: EMAIL_LIST_DENSITY_COMPACT})
    probe.message_list = _ListWidget()
    probe._company_color_map = {"acme.com": "#123456"}
    probe._theme_mode = "dark"

    EmailListMixin._ensure_company_color_delegate(probe)

    delegate = probe._company_color_delegate
    assert isinstance(delegate, _Delegate)
    assert delegate.parent is probe.message_list
    assert delegate.color_map == {"acme.com": "#123456"}
    assert delegate.theme_mode == "dark"
    assert delegate.density_mode == EMAIL_LIST_DENSITY_COMPACT
