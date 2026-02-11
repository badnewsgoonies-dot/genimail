import os
import threading
import time
import webbrowser
from datetime import timezone
from email.utils import parsedate_to_datetime

try:
    import msal
except ImportError:
    msal = None

try:
    import requests
except ImportError:
    requests = None

from genimail.constants import (
    AUTHORITY,
    DEFAULT_CLIENT_ID,
    GRAPH_BASE,
    HTTP_CONNECT_TIMEOUT_SEC,
    HTTP_GET_RETRIES,
    HTTP_READ_TIMEOUT_SEC,
    SCOPES,
)
from genimail.domain.helpers import token_cache_path_for_client_id
from genimail.paths import CONFIG_DIR


class GraphClient:
    """Microsoft Graph API client with MSAL authentication (device code flow)."""

    def __init__(
        self,
        client_id=None,
        on_device_code=None,
        request_timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC),
        get_retries=HTTP_GET_RETRIES,
        rate_limit_retries=3,
        max_retry_after_sec=30,
        max_delta_pages=200,
    ):
        if msal is None or requests is None:
            missing = []
            if msal is None:
                missing.append("msal")
            if requests is None:
                missing.append("requests")
            raise RuntimeError(
                f"Missing required dependencies for GraphClient: {', '.join(missing)}"
            )
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.access_token = None
        self.on_device_code = on_device_code
        self.request_timeout = request_timeout
        self.get_retries = max(0, int(get_retries or 0))
        self.rate_limit_retries = max(0, int(rate_limit_retries or 0))
        self.max_retry_after_sec = max(1, int(max_retry_after_sec or 1))
        self.max_delta_pages = max(1, int(max_delta_pages or 1))
        self.token_cache_file = token_cache_path_for_client_id(self.client_id)
        self.token_cache = msal.SerializableTokenCache()
        if os.path.exists(self.token_cache_file):
            with open(self.token_cache_file, "r", encoding="utf-8") as f:
                self.token_cache.deserialize(f.read())
        self.app = msal.PublicClientApplication(
            self.client_id, authority=AUTHORITY, token_cache=self.token_cache
        )
        self.session = requests.Session()
        self._session_lock = threading.Lock()

    def _save_cache(self):
        if self.token_cache.has_state_changed:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(self.token_cache_file, "w", encoding="utf-8") as f:
                f.write(self.token_cache.serialize())

    def clear_cached_tokens(self):
        """Remove this client's token cache file."""
        try:
            if os.path.exists(self.token_cache_file):
                os.remove(self.token_cache_file)
        except Exception:
            pass
        self.access_token = None

    def authenticate(self):
        """Authenticate, trying cached token first, then device code flow."""
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self.access_token = result["access_token"]
                self._save_cache()
                return True

        flow = self.app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise Exception(f"Could not start device flow: {flow.get('error_description', 'Unknown error')}")

        if self.on_device_code:
            self.on_device_code(flow)

        webbrowser.open(flow["verification_uri"])
        result = self.app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            self.access_token = result["access_token"]
            self._save_cache()
            return True
        return False

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    @staticmethod
    def _retry_after_to_seconds(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return 1
        try:
            return max(0, int(text))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError, OverflowError):
                return 1
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0, int(parsed.timestamp() - time.time()))

    def _sleep_for_retry_after(self, response):
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
        max_retry_after_sec = max(1, int(getattr(self, "max_retry_after_sec", 30) or 30))
        delay = min(max_retry_after_sec, self._retry_after_to_seconds(retry_after))
        time.sleep(delay)

    @staticmethod
    def _json_or_error(response, endpoint):
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Invalid JSON response from Graph endpoint: {endpoint}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected JSON shape from Graph endpoint: {endpoint}")
        return payload

    def _request(self, method, url, params=None, data=None, allow_410=False):
        auth_retried = False
        transport_retries = self.get_retries if method.upper() == "GET" else 0
        rate_limit_retries = getattr(self, "rate_limit_retries", 3)
        rate_limit_attempt = 0
        attempt = 0

        while True:
            lock = getattr(self, "_session_lock", None)
            if lock is None:
                self._session_lock = lock = threading.Lock()
            try:
                with lock:
                    resp = self.session.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=params,
                        json=data,
                        timeout=self.request_timeout,
                    )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt >= transport_retries:
                    raise
                attempt += 1
                continue

            if resp.status_code == 401 and not auth_retried and self.authenticate():
                auth_retried = True
                continue

            if allow_410 and resp.status_code == 410:
                return resp

            if resp.status_code == 429 and rate_limit_attempt < max(0, int(rate_limit_retries or 0)):
                rate_limit_attempt += 1
                self._sleep_for_retry_after(resp)
                continue

            resp.raise_for_status()
            return resp

    def _get(self, url, params=None):
        return self._json_or_error(self._request("GET", url, params=params), url)

    def _post(self, url, data):
        return self._request("POST", url, data=data)

    def _patch(self, url, data):
        return self._request("PATCH", url, data=data)

    def get_profile(self):
        return self._get(f"{GRAPH_BASE}/me")

    def get_folders(self):
        data = self._get(f"{GRAPH_BASE}/me/mailFolders", params={"$top": "50"})
        return data.get("value", [])

    def get_messages(self, folder_id="inbox", top=50, skip=0, search=None, filter_str=None):
        params = {
            "$top": str(top),
            "$skip": str(skip),
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
            "isRead,hasAttachments,bodyPreview,importance",
        }
        if search:
            params["$search"] = f'"{search}"'
        if filter_str:
            params["$filter"] = filter_str
        url = f"{GRAPH_BASE}/me/mailFolders/{folder_id}/messages"
        data = self._get(url, params=params)
        return data.get("value", []), data.get("@odata.count", None)

    def get_message(self, message_id):
        params = {
            "$select": "id,subject,from,toRecipients,ccRecipients,replyTo,"
            "receivedDateTime,isRead,hasAttachments,body,importance,bodyPreview"
        }
        return self._get(f"{GRAPH_BASE}/me/messages/{message_id}", params=params)

    def get_attachments(self, message_id):
        data = self._get(f"{GRAPH_BASE}/me/messages/{message_id}/attachments")
        return data.get("value", [])

    def download_attachment(self, message_id, attachment_id):
        return self._get(f"{GRAPH_BASE}/me/messages/{message_id}/attachments/{attachment_id}")

    def mark_read(self, message_id, is_read=True):
        self._patch(f"{GRAPH_BASE}/me/messages/{message_id}", {"isRead": is_read})

    def send_mail(
        self,
        to_list,
        cc_list,
        subject,
        body,
        attachments=None,
        reply_to_id=None,
        reply_mode=None,
    ):
        message = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": a}} for a in to_list if a.strip()],
        }
        if cc_list:
            message["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc_list if a.strip()]
        if attachments:
            message["attachments"] = attachments

        # Use sendMail for all compose modes so edited recipients/subject/body/attachments
        # are transmitted exactly as composed.
        _ = reply_to_id, reply_mode
        self._post(f"{GRAPH_BASE}/me/sendMail", {"message": message, "saveToSentItems": True})

    def move_message(self, message_id, destination_folder_id):
        self._post(f"{GRAPH_BASE}/me/messages/{message_id}/move", {"destinationId": destination_folder_id})

    def delete_message(self, message_id):
        self._request("DELETE", f"{GRAPH_BASE}/me/messages/{message_id}")

    def get_messages_delta(self, folder_id="inbox", delta_link=None):
        """Fetch messages using delta query. Returns (messages, new_delta_link, deleted_ids)."""
        if delta_link:
            url = delta_link
            params = None
        else:
            url = f"{GRAPH_BASE}/me/mailFolders/{folder_id}/messages/delta"
            params = {
                "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                "isRead,hasAttachments,bodyPreview,importance",
            }

        messages = []
        deleted_ids = []
        seen_links = set()
        max_pages = max(1, int(getattr(self, "max_delta_pages", 200) or 200))
        pages_seen = 0

        while url:
            if url in seen_links:
                raise RuntimeError("Delta pagination cycle detected.")
            seen_links.add(url)
            pages_seen += 1
            if pages_seen > max_pages:
                raise RuntimeError("Delta pagination exceeded maximum page limit.")

            resp = self._request("GET", url, params=params, allow_410=True)
            if resp.status_code == 410:
                return None, None, None
            data = self._json_or_error(resp, url)

            items = data.get("value") or []
            if not isinstance(items, list):
                raise RuntimeError("Malformed delta payload: expected list in 'value'.")
            for item in items:
                if not isinstance(item, dict):
                    continue
                msg_id = item.get("id")
                if "@removed" in item:
                    if msg_id:
                        deleted_ids.append(msg_id)
                else:
                    messages.append(item)

            next_link = data.get("@odata.nextLink")
            if next_link is not None and not isinstance(next_link, str):
                raise RuntimeError("Malformed delta payload: '@odata.nextLink' must be a string.")
            url = next_link
            params = None
            if "@odata.deltaLink" in data:
                new_delta_link = data["@odata.deltaLink"]
                if not isinstance(new_delta_link, str):
                    raise RuntimeError("Malformed delta payload: '@odata.deltaLink' must be a string.")
                return messages, new_delta_link, deleted_ids

        return messages, None, deleted_ids

    def close(self):
        session = getattr(self, "session", None)
        if session is not None:
            session.close()
            self.session = None
