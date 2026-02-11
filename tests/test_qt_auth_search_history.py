from genimail_qt.mixins.auth import AuthPollMixin
from genimail_qt.mixins.email_list import EmailListMixin


class _Config:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class _Model:
    def __init__(self):
        self.values = []

    def setStringList(self, values):
        self.values = list(values)


class _Completer:
    def __init__(self):
        self._model = _Model()

    def model(self):
        return self._model


def test_migrate_full_cache_sync_marks_complete_only_on_success():
    class _FailingCache:
        def clear_delta_links(self):
            raise RuntimeError("db busy")

    class _Probe(AuthPollMixin):
        pass

    probe = _Probe()
    probe.config = _Config()
    probe.cache = _FailingCache()

    AuthPollMixin._migrate_full_cache_sync(probe)
    assert probe.config.get("migration_full_cache_sync_v1") is None

    class _WorkingCache:
        def __init__(self):
            self.calls = 0

        def clear_delta_links(self):
            self.calls += 1

    probe.cache = _WorkingCache()
    AuthPollMixin._migrate_full_cache_sync(probe)
    assert probe.config.get("migration_full_cache_sync_v1") is True
    assert probe.cache.calls == 1


def test_load_search_history_ignores_non_string_entries():
    class _Probe(EmailListMixin):
        pass

    probe = _Probe()
    probe.config = _Config({"search_history": ["Invoice", 123, " invoice ", None, "Acme"]})
    probe._search_completer = _Completer()

    EmailListMixin._load_search_history(probe)
    assert probe._search_completer.model().values == ["Invoice", "Acme"]


def test_record_search_history_ignores_non_string_existing_values():
    class _Probe(EmailListMixin):
        def __init__(self):
            self.load_calls = 0

        def _load_search_history(self):
            self.load_calls += 1

    probe = _Probe()
    probe.config = _Config({"search_history": [123, "Beta", None, "BETA"]})

    EmailListMixin._record_search_history(probe, "Alpha")

    assert probe.config.get("search_history") == ["Alpha", "Beta"]
    assert probe.load_calls == 1


def test_start_polling_routes_init_errors_to_delta_handler():
    class _Workers:
        def __init__(self):
            self.calls = []

        def submit(self, fn, on_result, on_error=None):
            self.calls.append((fn, on_result, on_error))

    class _Timer:
        def __init__(self):
            self.start_calls = 0

        def start(self):
            self.start_calls += 1

    class _Sync:
        pass

    class _Probe(AuthPollMixin):
        def __init__(self):
            self.sync_service = _Sync()
            self.workers = _Workers()
            self._poll_timer = _Timer()
            self._poll_generation = 0
            self._poll_in_flight = True
            self.statuses = []

        def _set_status(self, text):
            self.statuses.append(text)

    probe = _Probe()
    AuthPollMixin._start_polling(probe)

    assert probe._poll_generation == 1
    assert probe._poll_in_flight is False
    assert probe._poll_timer.start_calls == 1
    assert len(probe.workers.calls) == 1
    _, _, error_handler = probe.workers.calls[0]
    assert error_handler.__func__.__name__ == "_on_delta_token_error"


def test_poll_result_always_resets_in_flight_when_callback_raises():
    class _List:
        @staticmethod
        def count():
            return 1

    class _Probe(AuthPollMixin):
        def __init__(self):
            self._poll_generation = 2
            self._poll_in_flight = True
            self.known_ids = set()
            self.company_filter_domain = None
            self.current_folder_id = "inbox"
            self.current_messages = []
            self.message_cache = {}
            self.attachment_cache = {}
            self.message_list = _List()

        @staticmethod
        def _set_status(_text):
            pass

        @staticmethod
        def _show_message_list():
            pass

        @staticmethod
        def _clear_detail_view(_text=None):
            pass

        @staticmethod
        def _ensure_detail_message_visible():
            pass

        @staticmethod
        def _prune_known_ids():
            pass

        @staticmethod
        def _render_message_list():
            raise RuntimeError("render failed")

    probe = _Probe()
    payload = {
        "_poll_generation": 2,
        "all_messages": [{"id": "m1", "isRead": True}],
        "all_deleted_ids": [],
        "updates_by_folder": {"inbox": [{"id": "m1", "isRead": True}]},
        "deleted_by_folder": {"inbox": []},
        "errors": [],
    }

    try:
        AuthPollMixin._on_poll_result(probe, payload)
    except RuntimeError:
        pass

    assert probe._poll_in_flight is False


def test_poll_result_ignores_stale_generation_payload():
    class _Probe(AuthPollMixin):
        def __init__(self):
            self._poll_generation = 3
            self._poll_in_flight = True
            self.current_messages = [{"id": "old"}]

    probe = _Probe()
    AuthPollMixin._on_poll_result(probe, {"_poll_generation": 2, "all_messages": [{"id": "new"}]})

    assert probe.current_messages == [{"id": "old"}]
    assert probe._poll_in_flight is False
