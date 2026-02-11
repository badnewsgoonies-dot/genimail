from genimail.services.mail_sync import MailSyncService, collect_new_unread


class DummyCache:
    def __init__(self, delta=None):
        self.delta = delta
        self.delta_links = {}
        if delta is not None:
            self.delta_links["inbox"] = delta
        self.saved_delta = None
        self.deleted_ids = []
        self.saved_messages = []
        self.cleared_delta_links = []

    def get_delta_link(self, folder_id):
        return self.delta_links.get(folder_id)

    def save_delta_link(self, folder_id, delta_link):
        self.saved_delta = (folder_id, delta_link)
        self.delta_links[folder_id] = delta_link
        if folder_id == "inbox":
            self.delta = delta_link

    def clear_delta_link(self, folder_id):
        self.cleared_delta_links.append(folder_id)
        self.delta_links.pop(folder_id, None)

    def clear_delta_links(self):
        self.cleared_delta_links.append("*")
        self.delta_links.clear()

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


class FolderAwareGraph:
    def __init__(self):
        self.get_messages_calls = []
        self.get_delta_calls = []
        self.fail_folders = set()
        self.messages_by_folder = {
            "inbox": [{"id": "in-1", "isRead": False}],
            "sentitems": [{"id": "sent-1", "isRead": True}],
            "junkemail": [{"id": "junk-1", "isRead": False}],
        }
        self.deleted_by_folder = {
            "inbox": ["deleted-1"],
            "sentitems": [],
            "junkemail": ["deleted-2"],
        }

    def get_messages(self, folder_id="inbox", top=10):
        _ = top
        self.get_messages_calls.append(folder_id)
        return list(self.messages_by_folder.get(folder_id, [])), None

    def get_messages_delta(self, folder_id="inbox", delta_link=None):
        self.get_delta_calls.append((folder_id, delta_link))
        if folder_id in self.fail_folders:
            raise RuntimeError(f"delta unavailable for {folder_id}")
        if delta_link is None:
            return [], f"delta-{folder_id}", []
        return (
            list(self.messages_by_folder.get(folder_id, [])),
            f"delta-next-{folder_id}",
            list(self.deleted_by_folder.get(folder_id, [])),
        )


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
    assert cache.cleared_delta_links == ["inbox"]


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


def test_initialize_delta_tokens_handles_partial_folder_failures():
    cache = DummyCache(delta=None)
    graph = FolderAwareGraph()
    graph.fail_folders = {"junkemail"}
    service = MailSyncService(graph, cache)

    payload = service.initialize_delta_tokens(["sentitems", "junkemail"], primary_folder_id="inbox")

    assert payload["folder_ids"] == ["inbox", "sentitems", "junkemail"]
    assert payload["ready"] == ["inbox", "sentitems"]
    assert len(payload["errors"]) == 1
    assert "junkemail" in payload["errors"][0]


def test_sync_delta_for_folders_returns_primary_and_aggregate_results():
    cache = DummyCache(delta="existing")
    cache.delta_links.update({"sentitems": "existing", "junkemail": "existing"})
    graph = FolderAwareGraph()
    service = MailSyncService(graph, cache)

    payload = service.sync_delta_for_folders(["sentitems", "junkemail"], fallback_top=10, primary_folder_id="inbox")

    assert payload["folder_ids"] == ["inbox", "sentitems", "junkemail"]
    assert [msg["id"] for msg in payload["messages"]] == ["in-1"]
    assert payload["deleted_ids"] == ["deleted-1"]
    assert [msg["id"] for msg in payload["all_messages"]] == ["in-1", "sent-1", "junk-1"]
    assert payload["all_deleted_ids"] == ["deleted-1", "deleted-2"]
    assert payload["errors"] == []


def test_sync_delta_for_folders_continues_when_one_folder_fails():
    cache = DummyCache(delta="existing")
    cache.delta_links.update({"sentitems": "existing", "junkemail": "existing"})
    graph = FolderAwareGraph()
    graph.fail_folders = {"sentitems"}
    service = MailSyncService(graph, cache)

    payload = service.sync_delta_for_folders(["sentitems", "junkemail"], fallback_top=10, primary_folder_id="inbox")

    assert [msg["id"] for msg in payload["messages"]] == ["in-1"]
    assert [msg["id"] for msg in payload["all_messages"]] == ["in-1", "junk-1"]
    assert payload["all_deleted_ids"] == ["deleted-1", "deleted-2"]
    assert len(payload["errors"]) == 1
    assert "sentitems" in payload["errors"][0]
