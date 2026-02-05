from genimail_qt import window as window_module
from genimail_qt.window import GeniMailQtWindow


class _FakeGraph:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def download_attachment(self, message_id, attachment_id):
        self.calls.append((message_id, attachment_id))
        return self.payload


class _FakeWindow:
    def __init__(self, graph):
        self.graph = graph


def test_normalize_cid_value_handles_prefix_and_angle_brackets():
    assert window_module._normalize_cid_value("cid:<Banner-123>") == "banner-123"
    assert window_module._normalize_cid_value("<b@c>") == "b@c"
    assert window_module._normalize_cid_value("") == ""


def test_replace_cid_sources_with_data_urls_swaps_known_ids():
    html = '<img src="cid:banner-1"><div style="background:url(cid:logo-2)">x</div>'
    replaced = window_module._replace_cid_sources_with_data_urls(
        html,
        {
            "banner-1": "data:image/png;base64,AAA",
            "logo-2": "data:image/jpeg;base64,BBB",
        },
    )
    assert "cid:banner-1" not in replaced
    assert "cid:logo-2" not in replaced
    assert "data:image/png;base64,AAA" in replaced
    assert "data:image/jpeg;base64,BBB" in replaced


def test_build_inline_cid_data_urls_filters_valid_inline_entries():
    attachments = [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "contentId": "<banner>",
            "contentType": "image/png",
            "contentBytes": "AAA",
        },
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "contentId": "",
            "contentType": "image/png",
            "contentBytes": "BBB",
        },
    ]
    fake = _FakeWindow(None)
    result = GeniMailQtWindow._build_inline_cid_data_urls(fake, attachments)
    assert result == {"banner": "data:image/png;base64,AAA"}


def test_hydrate_inline_attachment_bytes_downloads_missing_inline_payload():
    graph = _FakeGraph({"contentBytes": "AAA", "contentType": "image/png"})
    fake = _FakeWindow(graph)
    attachments = [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": "att-1",
            "isInline": True,
            "contentId": "<banner>",
            "contentBytes": "",
        }
    ]

    hydrated = GeniMailQtWindow._hydrate_inline_attachment_bytes(fake, "msg-1", attachments)

    assert graph.calls == [("msg-1", "att-1")]
    assert hydrated[0]["contentBytes"] == "AAA"
    assert hydrated[0]["contentType"] == "image/png"
