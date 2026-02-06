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
    assert GeniMailQtWindow._load_company_queries(fake_dict) == [
        {"domain": "airmiles", "label": ""},
        {"domain": "airmiles.ca", "label": ""},
    ]

    fake_list = _FakeWindow({"companies": [" airmiles ", "airmiles.ca", "airmiles"]})
    assert GeniMailQtWindow._load_company_queries(fake_list) == [
        {"domain": "airmiles", "label": ""},
        {"domain": "airmiles.ca", "label": ""},
    ]


def test_load_company_queries_reads_new_dict_list_format():
    fake = _FakeWindow(
        {
            "companies": [
                {"domain": "acme.com", "label": "Acme Corp"},
                {"domain": " test.org ", "label": ""},
                {"domain": "acme.com", "label": "Duplicate"},
            ]
        }
    )
    assert GeniMailQtWindow._load_company_queries(fake) == [
        {"domain": "acme.com", "label": "Acme Corp"},
        {"domain": "test.org", "label": ""},
    ]


def test_save_company_queries_persists_dict_list():
    fake = _FakeWindow({})
    GeniMailQtWindow._save_company_queries(
        fake,
        [
            {"domain": "airmiles", "label": "Air Miles"},
            {"domain": "airmiles.ca", "label": ""},
            {"domain": "airmiles", "label": "Duplicate"},
        ],
    )
    assert fake.config.payload["companies"] == [
        {"domain": "airmiles", "label": "Air Miles"},
        {"domain": "airmiles.ca", "label": ""},
    ]


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
        received_domains = []

        def __init__(self, _parent, _existing_entries, all_domains=None):
            self.changed = True
            self.entries = [{"domain": "other.com", "label": "Other"}]
            _Dialog.received_domains = list(all_domains or [])

        def exec(self):
            return 0

    class _Cache:
        @staticmethod
        def get_all_domains():
            return [{"domain": "acme.com"}, {"domain": "other.com"}]

    class _Probe:
        def __init__(self):
            self.company_filter_domain = "acme.com"
            self.cleared = []
            self.saved_entries = []
            self.cache = _Cache()

        @staticmethod
        def _normalize_company_query(value):
            return company_module.CompanyMixin._normalize_company_query(value)

        def _load_company_queries(self):
            return [
                {"domain": "acme.com", "label": ""},
                {"domain": "other.com", "label": ""},
            ]

        def _save_company_queries(self, entries):
            self.saved_entries = list(entries)

        def _refresh_company_sidebar(self):
            self.company_filter_domain = None

        def _clear_company_filter(self, force_reload=False):
            self.cleared.append(force_reload)

    monkeypatch.setattr(company_module, "CompanyTabManagerDialog", _Dialog)
    probe = _Probe()

    company_module.CompanyMixin._open_company_manager(probe)

    assert probe.saved_entries == [{"domain": "other.com", "label": "Other"}]
    assert _Dialog.received_domains == ["acme.com", "other.com"]
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


def test_company_load_token_prevents_stale_results():
    from genimail_qt.mixins.email_list import EmailListMixin

    class _Probe:
        def __init__(self):
            self._company_load_token = 2
            self.company_filter_domain = "acme.com"
            self.company_query_inflight = {"acme.com"}
            self.company_query_cache = {}
            self.company_result_messages = ["stale"]
            self.company_folder_filter = "all"
            self.filtered_messages = []
            self.apply_calls = 0

        def _apply_company_folder_filter(self):
            self.apply_calls += 1

        @staticmethod
        def _set_status(_text):
            pass

    probe = _Probe()
    payload = {
        "token": 1,
        "query": "acme.com",
        "messages": [{"id": "fresh"}],
        "errors": [],
        "fetched_at": time.time(),
    }

    EmailListMixin._on_company_messages_loaded(probe, payload)

    assert probe.company_query_cache["acme.com"]["messages"] == [{"id": "fresh"}]
    assert probe.apply_calls == 0
    assert probe.company_result_messages == ["stale"]


def test_reset_company_state_clears_all_fields():
    from genimail_qt.mixins.company import CompanyMixin

    class _Probe:
        def __init__(self):
            self.company_filter_domain = "acme.com"
            self.company_result_messages = [{"id": "1"}]
            self.company_folder_filter = "sentitems"
            self.company_query_cache = {"acme.com": {"messages": []}}
            self.company_query_inflight = {"acme.com"}
            self._company_search_override = {"query": "acme.com"}
            self.tab_sync_calls = 0
            self.folder_sync_calls = 0
            self.visible_states = []
            self.badge_updates = 0

        def _sync_company_tab_checks(self):
            self.tab_sync_calls += 1

        def _sync_company_folder_filter_checks(self):
            self.folder_sync_calls += 1

        def _set_company_folder_filter_visible(self, visible):
            self.visible_states.append(bool(visible))

        def _update_company_filter_badge(self):
            self.badge_updates += 1

    probe = _Probe()
    CompanyMixin._reset_company_state(probe, clear_cache=True)

    assert probe.company_filter_domain is None
    assert probe.company_result_messages == []
    assert probe.company_folder_filter == "all"
    assert probe.company_query_cache == {}
    assert probe.company_query_inflight == set()
    assert probe._company_search_override is None
    assert probe.tab_sync_calls == 1
    assert probe.folder_sync_calls == 1
    assert probe.visible_states == [False]
    assert probe.badge_updates == 1


def test_company_search_falls_back_to_local_on_failure():
    from genimail_qt.mixins.email_list import EmailListMixin

    class _SearchInput:
        @staticmethod
        def text():
            return "invoice"

    class _Workers:
        @staticmethod
        def submit(_fn, _on_result, on_error):
            on_error("search failed")

    class _Probe:
        def __init__(self):
            self.graph = object()
            self.search_input = _SearchInput()
            self.workers = _Workers()
            self.company_filter_domain = "acme.com"
            self.company_result_messages = [
                {
                    "id": "1",
                    "subject": "Invoice due",
                    "bodyPreview": "Please pay",
                    "from": {"emailAddress": {"name": "Acme Billing", "address": "billing@acme.com"}},
                },
                {
                    "id": "2",
                    "subject": "Weekly status",
                    "bodyPreview": "No invoice",
                    "from": {"emailAddress": {"name": "Acme Ops", "address": "ops@acme.com"}},
                },
            ]
            self.company_folder_filter = "all"
            self.filtered_messages = []
            self.current_messages = []
            self._company_load_token = 0
            self._company_search_override = {"query": "acme.com", "search_text": "invoice", "messages": [{"id": "stale"}]}
            self.apply_calls = 0
            self.status = ""

        @staticmethod
        def _show_message_list():
            pass

        def _set_status(self, text):
            self.status = text

        @staticmethod
        def _on_company_search_loaded(_payload):
            pass

        def _on_company_search_error(self, query, search_text, token, trace_text):
            EmailListMixin._on_company_search_error(self, query, search_text, token, trace_text)

        @staticmethod
        def _message_matches_search(msg, text):
            return EmailListMixin._message_matches_search(msg, text)

        def _apply_company_folder_filter(self):
            self.apply_calls += 1
            search_text = (self.search_input.text() or "").strip().lower()
            source = list(self.company_result_messages)
            if search_text:
                source = [msg for msg in source if self._message_matches_search(msg, search_text)]
            self.current_messages = source
            self.filtered_messages = source

    probe = _Probe()
    EmailListMixin._load_company_messages_with_search(probe, "acme.com", "invoice")

    assert probe.apply_calls == 1
    assert [msg["id"] for msg in probe.filtered_messages] == ["1", "2"]
    assert probe._company_search_override is None
    assert "locally filtered" in probe.status.lower()
