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
