"""Company-scoped email search and filtering mixin.

Extracted from ``email_list.py`` to keep individual files under 500 lines.
This mixin is mixed in alongside ``EmailListMixin`` and relies on attributes
that ``EmailListMixin`` (and other mixins) initialise on the window.
"""

import time

from genimail.constants import (
    EMAIL_COMPANY_CACHE_TTL_SEC,
    EMAIL_COMPANY_FETCH_PER_FOLDER,
    EMAIL_COMPANY_MEMORY_CACHE_MAX,
)


class CompanySearchMixin:
    # ------------------------------------------------------------------
    # Company: load all folders
    # ------------------------------------------------------------------

    def _load_company_messages_all_folders(self, company_query):
        if not self.graph:
            return
        query_key = (company_query or "").strip().lower()
        if not query_key:
            return

        self._company_search_override = None
        cache_messages = CompanySearchMixin._load_company_messages_from_cache(self, query_key)
        showing_cache = bool(cache_messages)
        if showing_cache:
            self.company_result_messages = cache_messages
            self.company_folder_filter = self.company_folder_filter or "all"
            self._apply_company_folder_filter()
            self._set_status(f'Loaded {len(self.filtered_messages)} cached message(s) for "{query_key}".')

        cached = self.company_query_cache.get(query_key)
        now = time.time()
        if cached and not showing_cache:
            cached_messages = list(cached.get("messages") or [])
            self.company_result_messages = cached_messages
            self.company_folder_filter = self.company_folder_filter or "all"
            self._apply_company_folder_filter()

            cache_age = now - float(cached.get("fetched_at") or 0)
            if cache_age <= EMAIL_COMPANY_CACHE_TTL_SEC:
                self._set_status(
                    f'Loaded {len(self.filtered_messages)} cached message(s) for "{query_key}".'
                )
                return
            self._set_status(f"Refreshing {query_key} across folders...")
        elif cached and showing_cache:
            cache_age = now - float(cached.get("fetched_at") or 0)
            if cache_age <= EMAIL_COMPANY_CACHE_TTL_SEC:
                return
            self._set_status(f"Refreshing {query_key} across folders...")
        elif showing_cache:
            self._set_status(f"Refreshing {query_key} across folders...")
        else:
            self._set_status(f"Loading {query_key} across folders...")

        if query_key in self.company_query_inflight:
            return

        self.company_query_inflight.add(query_key)
        self._company_load_token = getattr(self, "_company_load_token", 0) + 1
        load_token = self._company_load_token
        if not cached and not showing_cache:
            self._show_message_list()
            self._set_messages([])
            self._clear_detail_view(f'Loading messages for "{query_key}"...')
        self._set_company_tabs_enabled(False)
        self.workers.submit(
            lambda q=query_key, token=load_token: self._company_messages_worker(q, token),
            self._on_company_messages_loaded,
            lambda trace_text, q=query_key: self._on_company_messages_error(q, trace_text),
        )

    # ------------------------------------------------------------------
    # Company: background workers
    # ------------------------------------------------------------------

    def _company_messages_worker(self, company_query, token=None):
        deduped = {}
        errors = []
        fallback_count = 0
        sources = list(self.company_folder_sources or [])
        if not sources:
            sources = [{"id": self.current_folder_id, "key": self._folder_key_for_id(self.current_folder_id), "label": "Current"}]

        search_hint, filter_hint = self._company_query_hints(company_query)

        for source in sources:
            folder_id = source.get("id")
            folder_key = source.get("key") or self._folder_key_for_id(folder_id)
            folder_label = source.get("label") or folder_key
            try:
                page, _ = self.graph.get_messages(
                    folder_id=folder_id,
                    top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    search=search_hint,
                    filter_str=filter_hint,
                )
            except Exception:
                try:
                    page, _ = self.graph.get_messages(
                        folder_id=folder_id,
                        top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    )
                    fallback_count += 1
                except Exception as exc:
                    errors.append(f"{folder_label}: {exc}")
                    continue

            if page and hasattr(self, "cache") and hasattr(self.cache, "save_messages"):
                try:
                    self.cache.save_messages(page, folder_id)
                except Exception as exc:
                    print(f"[CACHE] unable to save company page for {folder_label}: {exc}")

            try:
                for msg in page or []:
                    msg_with_folder = self._with_folder_meta(msg, folder_id, folder_key, folder_label)
                    if not self._message_matches_company_filter(msg_with_folder, company_query):
                        continue
                    msg_id = msg_with_folder.get("id")
                    if not msg_id:
                        continue
                    existing = deduped.get(msg_id)
                    if existing is None or msg_with_folder.get("receivedDateTime", "") > existing.get("receivedDateTime", ""):
                        deduped[msg_id] = msg_with_folder
            except Exception as exc:
                errors.append(f"{folder_label}: {exc}")

        messages = sorted(deduped.values(), key=lambda msg: msg.get("receivedDateTime", ""), reverse=True)
        return {"query": company_query, "messages": messages, "errors": errors, "fallback_count": fallback_count, "fetched_at": time.time(), "token": token}

    def _load_company_messages_from_cache(self, company_query, search_text=None):
        if not hasattr(self, "cache") or not hasattr(self.cache, "search_company_messages"):
            return []
        try:
            cached_rows = self.cache.search_company_messages(company_query, search_text=search_text) or []
        except Exception as exc:
            print(f"[CACHE] company query failed for {company_query}: {exc}")
            return []

        sources_by_id = {
            (source.get("id") or "").strip().lower(): source
            for source in (self.company_folder_sources or [])
            if (source.get("id") or "").strip()
        }
        deduped = {}
        for msg in cached_rows:
            if not self._message_matches_company_filter(msg, company_query):
                continue
            folder_id = (msg.get("_folder_id") or "").strip() or self.current_folder_id
            source = sources_by_id.get(folder_id.strip().lower()) or {}
            folder_key = source.get("key") or self._folder_key_for_id(folder_id)
            folder_label = source.get("label") or folder_key
            enriched = self._with_folder_meta(msg, folder_id, folder_key, folder_label)
            msg_id = enriched.get("id")
            if not msg_id:
                continue
            existing = deduped.get(msg_id)
            if existing is None or enriched.get("receivedDateTime", "") > existing.get("receivedDateTime", ""):
                deduped[msg_id] = enriched

        return sorted(deduped.values(), key=lambda item: item.get("receivedDateTime", ""), reverse=True)

    # ------------------------------------------------------------------
    # Company: search within company filter
    # ------------------------------------------------------------------

    def _load_company_messages_with_search(self, company_query, search_text):
        query_key = (company_query or "").strip().lower()
        search_key = (search_text or "").strip().lower()
        if not query_key:
            return
        if not search_key:
            self._apply_company_folder_filter()
            return

        self._company_search_override = None
        if not self.company_result_messages:
            cache_messages = CompanySearchMixin._load_company_messages_from_cache(self, query_key, search_key)
            if cache_messages:
                self.company_result_messages = cache_messages

        self.company_folder_filter = self.company_folder_filter or "all"
        self._show_message_list()
        self._apply_company_folder_filter()
        local_count = len(self.filtered_messages)

        if not self.graph:
            self._set_status(f'Found {local_count} local message(s) for "{query_key}".')
            return

        self._company_load_token = getattr(self, "_company_load_token", 0) + 1
        load_token = self._company_load_token
        if local_count:
            self._set_status(f'Found {local_count} local message(s). Refining "{query_key}" search...')
        else:
            self._set_status(f'Searching "{search_key}" in "{query_key}"...')
        self.workers.submit(
            lambda q=query_key, text=search_key, token=load_token: self._company_search_worker(q, text, token),
            self._on_company_search_loaded,
            lambda trace_text, q=query_key, text=search_key, token=load_token: self._on_company_search_error(
                q, text, token, trace_text
            ),
        )

    def _company_search_worker(self, company_query, search_text, token):
        deduped = {}
        errors = []
        fallback_count = 0
        sources = list(self.company_folder_sources or [])
        if not sources:
            sources = [{"id": self.current_folder_id, "key": self._folder_key_for_id(self.current_folder_id), "label": "Current"}]

        combined_search = f"{company_query} {search_text}".strip()
        for source in sources:
            folder_id = source.get("id")
            folder_key = source.get("key") or self._folder_key_for_id(folder_id)
            folder_label = source.get("label") or folder_key
            try:
                page, _ = self.graph.get_messages(
                    folder_id=folder_id,
                    top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    search=combined_search,
                )
            except Exception:
                try:
                    page, _ = self.graph.get_messages(
                        folder_id=folder_id,
                        top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    )
                    fallback_count += 1
                except Exception as exc:
                    errors.append(f"{folder_label}: {exc}")
                    continue

            if page and hasattr(self, "cache") and hasattr(self.cache, "save_messages"):
                try:
                    self.cache.save_messages(page, folder_id)
                except Exception as exc:
                    print(f"[CACHE] unable to save company search page for {folder_label}: {exc}")

            try:
                for msg in page or []:
                    msg_with_folder = self._with_folder_meta(msg, folder_id, folder_key, folder_label)
                    if not self._message_matches_company_filter(msg_with_folder, company_query):
                        continue
                    if not self._message_matches_search(msg_with_folder, search_text):
                        continue
                    msg_id = msg_with_folder.get("id")
                    if not msg_id:
                        continue
                    existing = deduped.get(msg_id)
                    if existing is None or msg_with_folder.get("receivedDateTime", "") > existing.get("receivedDateTime", ""):
                        deduped[msg_id] = msg_with_folder
            except Exception as exc:
                errors.append(f"{folder_label}: {exc}")

        messages = sorted(deduped.values(), key=lambda msg: msg.get("receivedDateTime", ""), reverse=True)
        return {
            "query": company_query,
            "search_text": search_text,
            "messages": messages,
            "errors": errors,
            "fallback_count": fallback_count,
            "fetched_at": time.time(),
            "token": token,
        }

    # ------------------------------------------------------------------
    # Company: callbacks
    # ------------------------------------------------------------------

    def _on_company_search_loaded(self, payload):
        token = payload.get("token")
        current_token = getattr(self, "_company_load_token", None)
        if token is not None and current_token is not None and token != current_token:
            return

        query = (payload.get("query") or "").strip().lower()
        if query != (self.company_filter_domain or "").strip().lower():
            return

        payload_search = (payload.get("search_text") or "").strip().lower()
        current_search = (self.search_input.text() or "").strip().lower()
        if not current_search:
            self._company_search_override = None
            self._apply_company_folder_filter()
            return
        if payload_search != current_search:
            self._company_search_override = None
            return

        self._company_search_override = {
            "query": query,
            "search_text": payload_search,
            "messages": list(payload.get("messages") or []),
            "fetched_at": float(payload.get("fetched_at") or time.time()),
        }
        self._apply_company_folder_filter()
        self._ensure_detail_message_visible()

        errors = payload.get("errors") or []
        fallback_count = payload.get("fallback_count") or 0
        msg_count = len(self.filtered_messages)
        if errors:
            self._set_status(
                f'Found {msg_count} message(s) for "{query}" with partial folder search errors.'
            )
        elif fallback_count:
            self._set_status(
                f'Found {msg_count} message(s) for "{query}" ({fallback_count} folder(s) used local filtering).'
            )
        else:
            self._set_status(f'Found {msg_count} message(s) for "{query}" matching "{payload_search}".')

    def _on_company_search_error(self, query, search_text, token, trace_text):
        current_token = getattr(self, "_company_load_token", None)
        if token is not None and current_token is not None and token != current_token:
            return
        if (query or "").strip().lower() != (self.company_filter_domain or "").strip().lower():
            return
        if (search_text or "").strip().lower() != (self.search_input.text() or "").strip().lower():
            return

        self._company_search_override = None
        self._set_status(f'Search unavailable right now. Showing locally filtered results for "{query}".')
        print(trace_text)

    def _on_company_messages_loaded(self, payload):
        query = (payload.get("query") or "").strip().lower()
        self.company_query_inflight.discard(query)
        self._set_company_tabs_enabled(True)
        self.company_query_cache[query] = {
            "messages": list(payload.get("messages") or []),
            "errors": list(payload.get("errors") or []),
            "fetched_at": float(payload.get("fetched_at") or time.time()),
        }
        self._evict_company_cache()

        token = payload.get("token")
        current_token = getattr(self, "_company_load_token", None)
        if token is not None and current_token is not None and token != current_token:
            return

        if query != (self.company_filter_domain or "").strip().lower():
            return

        self.company_result_messages = payload.get("messages") or []
        self._company_search_override = None
        self.company_folder_filter = self.company_folder_filter or "all"
        self._apply_company_folder_filter()

        errors = payload.get("errors") or []
        fallback_count = payload.get("fallback_count") or 0
        msg_count = len(self.filtered_messages)
        if errors:
            self._set_status(
                f'Loaded {msg_count} message(s) for "{query}" with partial folder errors.'
            )
        elif fallback_count:
            self._set_status(
                f'Loaded {msg_count} message(s) for "{query}" ({fallback_count} folder(s) used local filtering).'
            )
        else:
            self._set_status(f'Loaded {msg_count} message(s) for "{query}" across folders.')

    def _on_company_messages_error(self, query, trace_text):
        self.company_query_inflight.discard((query or "").strip().lower())
        self._set_company_tabs_enabled(True)
        if (query or "").strip().lower() != (self.company_filter_domain or "").strip().lower():
            return
        self._set_status(f'Unable to refresh "{query}" right now.')
        print(trace_text)

    # ------------------------------------------------------------------
    # Company: helpers
    # ------------------------------------------------------------------

    def _evict_company_cache(self):
        """Remove oldest entries when cache exceeds max size."""
        cache = self.company_query_cache
        if len(cache) <= EMAIL_COMPANY_MEMORY_CACHE_MAX:
            return
        by_age = sorted(cache.items(), key=lambda kv: float(kv[1].get("fetched_at") or 0))
        while len(cache) > EMAIL_COMPANY_MEMORY_CACHE_MAX and by_age:
            oldest_key, _ = by_age.pop(0)
            cache.pop(oldest_key, None)

    def _company_query_hints(self, query):
        kind, value = self._parse_company_query(query)
        if not value:
            return None, None
        if kind == "email":
            safe_value = value.replace("'", "''")
            return None, f"from/emailAddress/address eq '{safe_value}'"
        return value, None

    def _apply_company_folder_filter(self):
        search_text = (self.search_input.text() or "").strip().lower()
        source_messages = list(self.company_result_messages or [])
        using_override = False
        if search_text:
            override = getattr(self, "_company_search_override", None) or {}
            if (
                (override.get("query") or "").strip().lower() == (self.company_filter_domain or "").strip().lower()
                and (override.get("search_text") or "").strip().lower() == search_text
            ):
                source_messages = list(override.get("messages") or [])
                using_override = True
        else:
            self._company_search_override = None

        folder_filter = (self.company_folder_filter or "all").strip().lower() or "all"
        if folder_filter != "all":
            source_messages = [msg for msg in source_messages if (msg.get("_folder_key") or "").strip().lower() == folder_filter]

        # Only apply local search filter for base results; override messages
        # are already filtered by the search worker.
        if search_text and not using_override:
            source_messages = [msg for msg in source_messages if self._message_matches_search(msg, search_text)]

        self._set_messages(source_messages)
        if self.message_list.count() > 0:
            self.message_list.setCurrentRow(0)
            self._show_message_list()
        else:
            self._show_message_list()
            self._clear_detail_view("No messages match this company filter.")
        self._ensure_detail_message_visible()


__all__ = ["CompanySearchMixin"]
