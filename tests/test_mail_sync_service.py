from genimail.services.mail_sync import MailSyncService, collect_new_unread


class DummyCache:
    def __init__(self, delta=None):
        self.delta = delta
        self.saved_delta = None
        self.deleted_ids = []
        self.saved_messages = []

    def get_delta_link(self, folder_id):
        return self.delta

    def save_delta_link(self, folder_id, delta_link):
        self.saved_delta = (folder_id, delta_link)
        self.delta = delta_link

    def delete_messages(self, message_ids):
        self.deleted_ids.extend(message_ids)

    def save_messages(self, messages, folder_id):
        self.saved_messages.append((folder_id, list(messages)))


class DummyGraph:
    def __init__(self):
        self.messages = [{"id": "m1", "isRead": False}]
        self.delta_response = (self.messages, "delta-next", ["m0"])
        self.init_delta = "delta-init"
        self.get_messages_calls = 0
        self.get_delta_calls = 0

    def get_messages(self, folder_id="inbox", top=10):
        self.get_messages_calls += 1
        return self.messages, None

    def get_messages_delta(self, folder_id="inbox", delta_link=None):
        self.get_delta_calls += 1
        if delta_link is None:
            return [], self.init_delta, []
        return self.delta_response


def test_initialize_delta_token_uses_cached_value():
    cache = DummyCache(delta="existing")
    graph = DummyGraph()
    service = MailSyncService(graph, cache)

    assert service.initialize_delta_token("inbox") == "existing"
    assert graph.get_delta_calls == 0


def test_initialize_delta_token_fetches_when_missing():
    cache = DummyCache(delta=None)
    graph = DummyGraph()
    service = MailSyncService(graph, cache)

    assert service.initialize_delta_token("inbox") == "delta-init"
    assert cache.saved_delta == ("inbox", "delta-init")


def test_sync_delta_once_with_delta_updates_cache_and_deletes():
    cache = DummyCache(delta="existing")
    graph = DummyGraph()
    service = MailSyncService(graph, cache)

    messages, deleted = service.sync_delta_once("inbox")

    assert messages == graph.messages
    assert deleted == ["m0"]
    assert cache.saved_delta == ("inbox", "delta-next")
    assert cache.deleted_ids == ["m0"]
    assert cache.saved_messages == [("inbox", graph.messages)]


def test_sync_delta_once_falls_back_when_delta_expired():
    cache = DummyCache(delta="expired")
    graph = DummyGraph()
    graph.delta_response = (None, None, None)
    service = MailSyncService(graph, cache)

    messages, deleted = service.sync_delta_once("inbox")

    assert messages == graph.messages
    assert deleted == []
    assert graph.get_messages_calls == 1


def test_collect_new_unread_tracks_known_ids():
    known_ids = {"a"}
    messages = [
        {"id": "a", "isRead": False},
        {"id": "b", "isRead": True},
        {"id": "c", "isRead": False},
        {"id": None, "isRead": False},
    ]

    new_unread = collect_new_unread(messages, known_ids)

    assert [m["id"] for m in new_unread] == ["c"]
    assert known_ids == {"a", "b", "c"}
