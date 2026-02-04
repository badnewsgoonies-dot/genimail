class MailSyncService:
    """Coordinates Graph delta sync and cache persistence."""

    def __init__(self, graph_client, cache_store):
        self.graph = graph_client
        self.cache = cache_store

    def initialize_delta_token(self, folder_id="inbox"):
        existing = self.cache.get_delta_link(folder_id)
        if existing:
            return existing
        _, delta_link, _ = self.graph.get_messages_delta(folder_id=folder_id)
        if delta_link:
            self.cache.save_delta_link(folder_id, delta_link)
        return delta_link

    def fetch_recent_messages(self, folder_id="inbox", top=50):
        messages, _ = self.graph.get_messages(folder_id=folder_id, top=top)
        return messages or []

    def sync_delta_once(self, folder_id="inbox", fallback_top=10):
        delta_link = self.cache.get_delta_link(folder_id)
        if not delta_link:
            messages, _ = self.graph.get_messages(folder_id=folder_id, top=fallback_top)
            return messages or [], []

        messages, new_delta_link, deleted_ids = self.graph.get_messages_delta(
            folder_id=folder_id,
            delta_link=delta_link,
        )

        if messages is None:
            messages, _ = self.graph.get_messages(folder_id=folder_id, top=fallback_top)
            _, new_delta_link, _ = self.graph.get_messages_delta(folder_id=folder_id)

        if new_delta_link:
            self.cache.save_delta_link(folder_id, new_delta_link)

        deleted_ids = deleted_ids or []
        if deleted_ids:
            self.cache.delete_messages(deleted_ids)

        messages = messages or []
        if messages:
            self.cache.save_messages(messages, folder_id)

        return messages, deleted_ids


def collect_new_unread(messages, known_ids):
    """Return unread messages that are new to the known-id set."""
    new_unread = []
    for message in messages:
        message_id = message.get("id")
        if not message_id:
            continue
        if message_id in known_ids:
            continue
        known_ids.add(message_id)
        if not message.get("isRead"):
            new_unread.append(message)
    return new_unread
