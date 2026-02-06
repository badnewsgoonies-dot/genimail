import time

from genimail_qt.window import GeniMailQtWindow


class _FakeConfig:
    def __init__(self, payload):
        self.payload = dict(payload)

    def get(self, key, default=None):
        return self.payload.get(key, default)

    def set(self, key, value):
        self.payload[key] = value


class _FakeWindow:
    def __init__(self, payload):
        self.config = _FakeConfig(payload)


def test_parse_company_query_uses_smart_rules():
    assert GeniMailQtWindow._parse_company_query("notifications@airmiles.ca") == ("email", "notifications@airmiles.ca")
    assert GeniMailQtWindow._parse_company_query("airmiles.ca") == ("domain", "airmiles.ca")
    assert GeniMailQtWindow._parse_company_query("airmiles") == ("text", "airmiles")


def test_message_matches_company_filter_rules():
    msg = {"from": {"emailAddress": {"name": "Airmiles Support", "address": "notifications@airmiles.ca"}}}

    assert GeniMailQtWindow._message_matches_company_filter(msg, "notifications@airmiles.ca")
    assert GeniMailQtWindow._message_matches_company_filter(msg, "airmiles.ca")
    assert GeniMailQtWindow._message_matches_company_filter(msg, "airmiles")
    assert not GeniMailQtWindow._message_matches_company_filter(msg, "billing@airmiles.ca")
    assert not GeniMailQtWindow._message_matches_company_filter(msg, "example.com")


def test_load_company_queries_supports_legacy_dict_and_new_list():
    fake_dict = _FakeWindow({"companies": {"airmiles": "airmiles", "airmiles.ca": "airmiles.ca"}})
    assert GeniMailQtWindow._load_company_queries(fake_dict) == ["airmiles", "airmiles.ca"]

    fake_list = _FakeWindow({"companies": [" airmiles ", "airmiles.ca", "airmiles"]})
    assert GeniMailQtWindow._load_company_queries(fake_list) == ["airmiles", "airmiles.ca"]


def test_save_company_queries_persists_list():
    fake = _FakeWindow({})
    GeniMailQtWindow._save_company_queries(fake, ["airmiles", "airmiles.ca", "airmiles"])
    assert fake.config.payload["companies"] == ["airmiles", "airmiles.ca"]


def test_folder_key_from_folder_prefers_well_known_name():
    folder = {"displayName": "Boite de reception", "wellKnownName": "inbox"}
    assert GeniMailQtWindow._folder_key_from_folder(folder) == "inbox"


def test_folder_key_from_folder_maps_common_aliases():
    assert GeniMailQtWindow._folder_key_from_folder({"displayName": "Sent"}) == "sentitems"
    assert GeniMailQtWindow._folder_key_from_folder({"displayName": "Deleted"}) == "deleteditems"
    assert GeniMailQtWindow._folder_key_from_folder({"displayName": "Junk"}) == "junkemail"


def test_cached_empty_company_results_are_applied_before_ttl_return():
    from genimail_qt.mixins.email_list import EmailListMixin

    class _Probe:
        def __init__(self):
            self.graph = object()
            self.company_query_cache = {
                "acme.com": {
                    "messages": [],
                    "fetched_at": time.time(),
                }
            }
            self.company_query_inflight = set()
            self.company_result_messages = [{"id": "stale"}]
            self.company_folder_filter = "all"
            self.filtered_messages = [{"id": "stale"}]
            self.apply_calls = 0

        def _apply_company_folder_filter(self):
            self.apply_calls += 1
            self.filtered_messages = list(self.company_result_messages)

        def _set_status(self, _text):
            pass

    probe = _Probe()
    EmailListMixin._load_company_messages_all_folders(probe, "acme.com")

    assert probe.apply_calls == 1
    assert probe.company_result_messages == []
    assert probe.filtered_messages == []


def test_open_company_manager_clears_with_reload_when_active_tab_removed(monkeypatch):
    from genimail_qt.mixins import company as company_module

    class _Dialog:
        def __init__(self, _parent, _existing_queries):
            self.changed = True
            self.tabs = ["other.com"]

        def exec(self):
            return 0

    class _Probe:
        def __init__(self):
            self.company_filter_domain = "acme.com"
            self.cleared = []
            self.saved_tabs = []

        def _load_company_queries(self):
            return ["acme.com", "other.com"]

        def _save_company_queries(self, tabs):
            self.saved_tabs = list(tabs)

        def _refresh_company_sidebar(self):
            self.company_filter_domain = None

        def _clear_company_filter(self, force_reload=False):
            self.cleared.append(force_reload)

    monkeypatch.setattr(company_module, "CompanyTabManagerDialog", _Dialog)
    probe = _Probe()

    company_module.CompanyMixin._open_company_manager(probe)

    assert probe.saved_tabs == ["other.com"]
    assert probe.cleared == [True]


def test_messages_worker_falls_back_to_local_filter_when_graph_search_fails():
    from genimail_qt.mixins.email_list import EmailListMixin

    class _Graph:
        def get_messages(self, folder_id="inbox", top=50, search=None, filter_str=None):
            _ = top, filter_str
            if search:
                raise RuntimeError("search unsupported")
            return (
                [
                    {
                        "id": "1",
                        "subject": "Invoice",
                        "bodyPreview": "Payment due",
                        "from": {"emailAddress": {"name": "Acme", "address": "billing@acme.com"}},
                    },
                    {
                        "id": "2",
                        "subject": "Status",
                        "bodyPreview": "Nothing due",
                        "from": {"emailAddress": {"name": "Other", "address": "noreply@example.com"}},
                    },
                ],
                None,
            )

    class _Probe:
        graph = _Graph()

        @staticmethod
        def _message_matches_search(msg, text):
            return EmailListMixin._message_matches_search(msg, text)

    payload = EmailListMixin._messages_worker(_Probe(), "inbox", "invoice", 7)

    assert payload["token"] == 7
    assert payload["folder_id"] == "inbox"
    assert [msg["id"] for msg in payload["messages"]] == ["1"]


def test_company_inflight_key_cleared_on_success_and_error():
    """Inflight set is cleaned up by the wrapper callbacks so a stuck key cannot block reloads."""
    from genimail_qt.mixins.email_list import EmailListMixin

    class _FakeWorkers:
        def __init__(self):
            self.last_on_result = None
            self.last_on_error = None

        def submit(self, _fn, on_result, on_error=None):
            self.last_on_result = on_result
            self.last_on_error = on_error

    class _Probe:
        def __init__(self):
            self.graph = object()
            self.company_query_cache = {}
            self.company_query_inflight = set()
            self.company_result_messages = []
            self.company_folder_filter = "all"
            self.company_folder_sources = []
            self.company_filter_domain = "acme.com"
            self.current_folder_id = "inbox"
            self.current_messages = []
            self.filtered_messages = []
            self.workers = _FakeWorkers()

        def _show_message_list(self):
            pass

        class _List:
            @staticmethod
            def count():
                return 0

            @staticmethod
            def clear():
                pass

        message_list = _List()

        def _clear_detail_view(self, _msg=""):
            pass

        def _apply_company_folder_filter(self):
            self.filtered_messages = list(self.company_result_messages)

        def _set_status(self, _text):
            pass

    # -- success path --
    probe = _Probe()
    EmailListMixin._load_company_messages_all_folders(probe, "acme.com")
    assert "acme.com" in probe.company_query_inflight

    probe.workers.last_on_result({
        "query": "acme.com", "messages": [], "errors": [], "fetched_at": time.time(),
    })
    assert "acme.com" not in probe.company_query_inflight

    # -- error path --
    probe2 = _Probe()
    EmailListMixin._load_company_messages_all_folders(probe2, "acme.com")
    assert "acme.com" in probe2.company_query_inflight

    probe2.workers.last_on_error("Traceback: boom")
    assert "acme.com" not in probe2.company_query_inflight


def test_on_messages_loaded_ignores_stale_payload_token():
    from genimail_qt.mixins.email_list import EmailListMixin

    class _Probe:
        def __init__(self):
            self._message_load_token = 2
            self.current_folder_id = "inbox"
            self.company_result_messages = []
            self.current_messages = ["stale"]
            self.filtered_messages = []
            self.known_ids = set()
            self.refresh_calls = 0
            self.render_calls = 0
            self.status = ""

        @staticmethod
        def _folder_key_for_id(_folder_id):
            return "inbox"

        @staticmethod
        def _with_folder_meta(msg, folder_id, folder_key, folder_label=None):
            return EmailListMixin._with_folder_meta(msg, folder_id, folder_key, folder_label)

        def _refresh_company_sidebar(self):
            self.refresh_calls += 1

        def _render_message_list(self):
            self.render_calls += 1

        def _set_status(self, text):
            self.status = text

        class _List:
            @staticmethod
            def count():
                return 0

        message_list = _List()

        @staticmethod
        def _show_message_list():
            pass

        @staticmethod
        def _clear_detail_view(_msg):
            pass

    probe = _Probe()
    payload = {"token": 1, "folder_id": "inbox", "messages": [{"id": "new"}]}

    EmailListMixin._on_messages_loaded(probe, payload)

    assert probe.current_messages == ["stale"]
    assert probe.refresh_calls == 0
    assert probe.render_calls == 0
