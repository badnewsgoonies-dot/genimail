import pytest

from genimail.infra import graph_client


def test_graph_client_requires_dependencies(monkeypatch):
    monkeypatch.setattr(graph_client, "msal", None)
    monkeypatch.setattr(graph_client, "requests", None)

    with pytest.raises(RuntimeError):
        graph_client.GraphClient()
