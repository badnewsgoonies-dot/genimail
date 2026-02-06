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

    @staticmethod
    def _ordered_folder_ids(folder_ids, primary_folder_id="inbox"):
        ordered = []
        seen = set()

        def add(folder_id):
            value = (folder_id or "").strip()
            if not value:
                return
            key = value.lower()
            if key in seen:
                return
            seen.add(key)
            ordered.append(value)

        add(primary_folder_id)
        for folder_id in folder_ids or []:
            add(folder_id)
        return ordered

    def initialize_delta_tokens(self, folder_ids, primary_folder_id="inbox"):
        ordered_folders = self._ordered_folder_ids(folder_ids, primary_folder_id=primary_folder_id)
        ready = []
        errors = []
        for folder_id in ordered_folders:
            try:
                self.initialize_delta_token(folder_id=folder_id)
                ready.append(folder_id)
            except Exception as exc:
                errors.append(f"{folder_id}: {exc}")
        return {"folder_ids": ordered_folders, "ready": ready, "errors": errors}

    def sync_delta_for_folders(self, folder_ids, fallback_top=10, primary_folder_id="inbox"):
        ordered_folders = self._ordered_folder_ids(folder_ids, primary_folder_id=primary_folder_id)
        updates_by_folder = {}
        deleted_by_folder = {}
        errors = []

        all_messages = []
        all_deleted_ids = []
        seen_deleted = set()

        for folder_id in ordered_folders:
            try:
                messages, deleted_ids = self.sync_delta_once(folder_id=folder_id, fallback_top=fallback_top)
            except Exception as exc:
                errors.append(f"{folder_id}: {exc}")
                continue

            current_messages = list(messages or [])
            current_deleted = list(deleted_ids or [])
            updates_by_folder[folder_id] = current_messages
            deleted_by_folder[folder_id] = current_deleted
            all_messages.extend(current_messages)

            for msg_id in current_deleted:
                if not msg_id or msg_id in seen_deleted:
                    continue
                seen_deleted.add(msg_id)
                all_deleted_ids.append(msg_id)

        primary_id = (primary_folder_id or "inbox").strip() or "inbox"
        return {
            "folder_ids": ordered_folders,
            "messages": list(updates_by_folder.get(primary_id) or []),
            "deleted_ids": list(deleted_by_folder.get(primary_id) or []),
            "updates_by_folder": updates_by_folder,
            "deleted_by_folder": deleted_by_folder,
            "all_messages": all_messages,
            "all_deleted_ids": all_deleted_ids,
            "errors": errors,
        }


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
