import pytest

from genimail.infra import graph_client


def test_graph_client_requires_dependencies(monkeypatch):
    monkeypatch.setattr(graph_client, "msal", None)
    monkeypatch.setattr(graph_client, "requests", None)

    with pytest.raises(RuntimeError):
        graph_client.GraphClient()


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, json_error=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self._json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise graph_client.requests.exceptions.HTTPError(f"status={self.status_code}")

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def test_request_retries_auth_after_401(monkeypatch):
    client = graph_client.GraphClient.__new__(graph_client.GraphClient)
    responses = [_FakeResponse(401), _FakeResponse(200, {"ok": True})]
    calls = {"count": 0}

    class _Session:
        @staticmethod
        def request(*_args, **_kwargs):
            response = responses[calls["count"]]
            calls["count"] += 1
            return response

    auth_calls = {"count": 0}

    def _authenticate():
        auth_calls["count"] += 1
        return True

    client.session = _Session()
    client._headers = lambda: {"Authorization": "Bearer token"}
    client.authenticate = _authenticate
    client.request_timeout = (1, 1)
    client.get_retries = 0

    response = client._request("GET", "https://example.invalid")
    assert response.status_code == 200
    assert auth_calls["count"] == 1
    assert calls["count"] == 2


def test_request_retries_get_on_timeout():
    client = graph_client.GraphClient.__new__(graph_client.GraphClient)
    calls = {"count": 0}

    class _Session:
        @staticmethod
        def request(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise graph_client.requests.exceptions.Timeout("slow")
            return _FakeResponse(200, {"ok": True})

    client.session = _Session()
    client._headers = lambda: {"Authorization": "Bearer token"}
    client.authenticate = lambda: False
    client.request_timeout = (1, 1)
    client.get_retries = 1

    response = client._request("GET", "https://example.invalid")
    assert response.status_code == 200
    assert calls["count"] == 2


def test_request_allow_410_returns_response():
    client = graph_client.GraphClient.__new__(graph_client.GraphClient)

    class _Session:
        @staticmethod
        def request(*_args, **_kwargs):
            return _FakeResponse(410)

    client.session = _Session()
    client._headers = lambda: {"Authorization": "Bearer token"}
    client.authenticate = lambda: False
    client.request_timeout = (1, 1)
    client.get_retries = 0

    response = client._request("GET", "https://example.invalid", allow_410=True)
    assert response.status_code == 410


def test_request_retries_on_429_retry_after(monkeypatch):
    client = graph_client.GraphClient.__new__(graph_client.GraphClient)
    responses = [
        _FakeResponse(429, headers={"Retry-After": "2"}),
        _FakeResponse(200, {"ok": True}),
    ]
    calls = {"count": 0}
    sleeps = []

    class _Session:
        @staticmethod
        def request(*_args, **_kwargs):
            response = responses[calls["count"]]
            calls["count"] += 1
            return response

    monkeypatch.setattr(graph_client.time, "sleep", lambda sec: sleeps.append(sec))
    client.session = _Session()
    client._headers = lambda: {"Authorization": "Bearer token"}
    client.authenticate = lambda: False
    client.request_timeout = (1, 1)
    client.get_retries = 0
    client.rate_limit_retries = 1
    client.max_retry_after_sec = 30

    response = client._request("GET", "https://example.invalid")
    assert response.status_code == 200
    assert calls["count"] == 2
    assert sleeps == [2]


def test_get_raises_for_invalid_json_payload():
    client = graph_client.GraphClient.__new__(graph_client.GraphClient)

    class _Session:
        @staticmethod
        def request(*_args, **_kwargs):
            return _FakeResponse(200, json_error=ValueError("bad json"))

    client.session = _Session()
    client._headers = lambda: {"Authorization": "Bearer token"}
    client.authenticate = lambda: False
    client.request_timeout = (1, 1)
    client.get_retries = 0
    client.rate_limit_retries = 0

    with pytest.raises(RuntimeError, match="Invalid JSON response"):
        client._get("https://example.invalid")


def test_get_messages_delta_detects_pagination_cycle():
    client = graph_client.GraphClient.__new__(graph_client.GraphClient)
    client.max_delta_pages = 20
    seen = {"count": 0}

    class _Session:
        @staticmethod
        def request(*_args, **_kwargs):
            seen["count"] += 1
            return _FakeResponse(
                200,
                {
                    "value": [{"id": f"m{seen['count']}", "subject": "x"}],
                    "@odata.nextLink": "https://example.invalid/loop",
                },
            )

    client.session = _Session()
    client._headers = lambda: {"Authorization": "Bearer token"}
    client.authenticate = lambda: False
    client.request_timeout = (1, 1)
    client.get_retries = 0
    client.rate_limit_retries = 0

    with pytest.raises(RuntimeError, match="pagination cycle"):
        client.get_messages_delta(folder_id="inbox")
