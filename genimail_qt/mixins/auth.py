import os

from PySide6.QtWidgets import QMessageBox

from genimail.constants import APP_NAME, DEFAULT_CLIENT_ID, EMAIL_DELTA_FALLBACK_TOP
from genimail.domain.helpers import token_cache_path_for_client_id
from genimail.infra.graph_client import GraphClient
from genimail.services.mail_sync import MailSyncService, collect_new_unread


class AuthPollMixin:
    def _resolve_inbox_id(self):
        """Return the actual Graph API folder ID for Inbox.

        After ``_populate_folders`` runs, ``company_folder_sources`` contains
        an entry with ``key="inbox"`` whose ``id`` is the real Graph API ID
        (e.g. ``"AAMkAD..."``) .  Before that list is populated we fall back
        to the well-known name ``"inbox"`` which the Graph API also accepts.
        """
        for source in self.company_folder_sources or []:
            if (source or {}).get("key") == "inbox":
                real_id = (source.get("id") or "").strip()
                if real_id:
                    return real_id
        return "inbox"

    def _collect_sync_folder_ids(self):
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

        add(self._resolve_inbox_id())
        for source in self.company_folder_sources or []:
            add((source or {}).get("id") or (source or {}).get("key"))
        add(self.current_folder_id)
        return ordered

    def _auto_connect_on_startup(self):
        if self.graph is not None:
            return
        if not hasattr(self, "connect_btn"):
            return
        if self.connect_btn.isEnabled():
            self._start_authentication()

    def _start_authentication(self):
        self.connect_btn.setEnabled(False)
        self._set_status("Authenticating...")
        self.workers.submit(self._auth_worker_task, self._on_authenticated)

    def _reconnect(self):
        self._poll_timer.stop()
        self._poll_in_flight = False
        if self.graph is not None:
            self.graph.clear_cached_tokens()
        else:
            client_id = (self.config.get("client_id") or "").strip() or DEFAULT_CLIENT_ID
            cache_path = token_cache_path_for_client_id(client_id)
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                except OSError:
                    pass
        self.graph = None
        self.sync_service = None
        self.current_messages = []
        self.filtered_messages = []
        self.message_cache.clear()
        self.attachment_cache.clear()
        self.known_ids.clear()
        self._reset_company_state(clear_cache=True)
        self.current_message = None
        self.message_list.clear()
        self._show_message_list()
        self._clear_detail_view("Reconnect to load mail.")
        self.message_header.setText("Disconnected")
        self._set_status("Reconnecting...")
        self._start_authentication()

    def _auth_worker_task(self):
        def on_device_code(flow):
            code = flow.get("user_code", "???")
            self.auth_code_received.emit(code)

        client_id = (self.config.get("client_id") or "").strip() or None
        graph = GraphClient(client_id=client_id, on_device_code=on_device_code)
        if not graph.authenticate():
            raise RuntimeError("Authentication failed.")
        profile = graph.get_profile()
        folders = graph.get_folders()
        return {"graph": graph, "profile": profile, "folders": folders}

    def _show_auth_code_dialog(self, code):
        QMessageBox.information(
            self,
            "Microsoft Sign In",
            "Open microsoft.com/devicelogin and enter this code:\n\n"
            f"{code}\n\n"
            "Finish sign-in in your browser.",
        )

    def _on_authenticated(self, result):
        self.graph = result["graph"]
        self.sync_service = MailSyncService(self.graph, self.cache)
        profile = result.get("profile") or {}
        self.current_user_email = profile.get("mail") or profile.get("userPrincipalName") or ""
        self.connect_btn.setEnabled(True)
        self.setWindowTitle(f"{APP_NAME} - {self.current_user_email}")
        self._set_status(f"Connected as {self.current_user_email}")
        self._populate_folders(result.get("folders") or [])
        self._refresh_company_sidebar()
        self._migrate_full_cache_sync()
        self._start_polling()

    def _migrate_full_cache_sync(self):
        """One-time migration: clear delta links so the next delta init
        re-downloads all messages into the SQLite cache.

        Previous versions discarded the messages fetched during delta
        initialization.  Clearing the stored links forces a fresh full
        fetch that now gets saved properly.
        """
        migration_key = "migration_full_cache_sync_v1"
        if self.config.get(migration_key):
            return
        try:
            self.cache.clear_delta_links()
        except Exception as exc:
            print(f"[MIGRATION] failed to clear delta links: {exc}")
        self.config.set(migration_key, True)

    def _start_polling(self):
        if not self.sync_service:
            return
        self._set_status("Connected. Sync active.")
        self.workers.submit(self._init_delta_token_worker, self._on_delta_token_ready, self._on_poll_error)
        self._poll_timer.start()

    def _init_delta_token_worker(self):
        return self.sync_service.initialize_delta_tokens(
            folder_ids=self._collect_sync_folder_ids(),
            primary_folder_id=self._resolve_inbox_id(),
        )

    def _on_delta_token_ready(self, payload):
        if not isinstance(payload, dict):
            self._set_status("Connected. Delta sync ready.")
            return

        ready = payload.get("ready") or []
        folders = payload.get("folder_ids") or []
        errors = payload.get("errors") or []
        if errors:
            self._set_status(f"Connected. Delta sync ready for {len(ready)}/{len(folders)} folders.")
            print("[DELTA] initialization warnings:")
            for line in errors:
                print(f"[DELTA] {line}")
            self._poll_once()
            return

        self._set_status(f"Connected. Delta sync ready ({len(ready)} folder(s)).")

        # Immediate catchup sync so the cache is fresh for company tabs
        # instead of waiting for the first 30-second poll timer tick.
        self._poll_once()

    def _poll_once(self):
        if not self.sync_service:
            return
        if not self._poll_lock.acquire(blocking=False):
            return
        if self._poll_in_flight:
            self._poll_lock.release()
            return
        self._poll_in_flight = True
        self.workers.submit(self._poll_worker, self._on_poll_result, self._on_poll_error)

    def _poll_worker(self):
        return self.sync_service.sync_delta_for_folders(
            folder_ids=self._collect_sync_folder_ids(),
            fallback_top=EMAIL_DELTA_FALLBACK_TOP,
            primary_folder_id=self._resolve_inbox_id(),
        )

    def _on_poll_result(self, payload):
        self._poll_in_flight = False
        self._poll_lock.release()

        all_updates = payload.get("all_messages") or []
        all_deleted_ids = payload.get("all_deleted_ids") or []
        updates_by_folder = payload.get("updates_by_folder") or {}
        deleted_by_folder = payload.get("deleted_by_folder") or {}
        errors = payload.get("errors") or []
        if errors:
            print("[SYNC] partial folder errors:")
            for line in errors:
                print(f"[SYNC] {line}")

        # Track new unread across ALL folders for notification badge.
        new_unread = collect_new_unread(all_updates, self.known_ids)
        for msg_id in all_deleted_ids:
            self.known_ids.discard(msg_id)

        # Company filter mode: don't update the message list (separate UI path).
        if self.company_filter_domain:
            if new_unread:
                self._set_status(f"{len(new_unread)} new unread message(s)")
            elif all_updates or all_deleted_ids:
                self._set_status("Connected. Sync up to date.")
            return

        # Resolve which folder's updates to apply to the active message list.
        active_updates = updates_by_folder.get(self.current_folder_id, [])
        active_deletes = deleted_by_folder.get(self.current_folder_id, [])

        if active_deletes:
            deleted_set = set(active_deletes)
            self.current_messages = [msg for msg in self.current_messages if msg.get("id") not in deleted_set]
            for msg_id in deleted_set:
                self.message_cache.pop(msg_id, None)
                self.attachment_cache.pop(msg_id, None)

        if active_updates or active_deletes:
            index_by_id = {msg.get("id"): idx for idx, msg in enumerate(self.current_messages) if msg.get("id")}
            for msg in active_updates:
                msg_id = msg.get("id")
                if not msg_id:
                    continue
                idx = index_by_id.get(msg_id)
                if idx is None:
                    self.current_messages.insert(0, msg)
                else:
                    self.current_messages[idx] = msg
            self._render_message_list()
            if self.message_list.count() == 0:
                self._show_message_list()
                self._clear_detail_view("No messages in this folder.")
            self._ensure_detail_message_visible()

        if new_unread:
            self._set_status(f"{len(new_unread)} new unread message(s)")
        else:
            self._set_status("Connected. Sync up to date.")

        self._prune_known_ids()

    def _prune_known_ids(self, max_size=5000):
        """Prevent known_ids from growing without bound.

        Once the set exceeds *max_size*, trim it back to just the IDs that
        are currently visible in ``current_messages``.  This keeps
        ``collect_new_unread`` accurate for the active view while releasing
        memory from messages that scrolled out of scope long ago.
        """
        if len(self.known_ids) <= max_size:
            return
        active_ids = {msg.get("id") for msg in self.current_messages if msg.get("id")}
        self.known_ids = active_ids

    def _on_poll_error(self, trace_text):
        self._poll_in_flight = False
        if self._poll_lock.locked():
            self._poll_lock.release()
        self._set_status("Sync warning. Retrying...")
        print(trace_text)


__all__ = ["AuthPollMixin"]
