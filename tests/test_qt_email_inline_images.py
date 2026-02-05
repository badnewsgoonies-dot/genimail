from genimail_qt.window import GeniMailQtWindow
from genimail_qt.webview_utils import (
    is_inline_attachment,
    normalize_cid_value,
    replace_cid_sources_with_data_urls,
)


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
    assert normalize_cid_value("cid:<Banner-123>") == "banner-123"
    assert normalize_cid_value("<b@c>") == "b@c"
    assert normalize_cid_value("image001.png%4001D123ABC") == "image001.png@01d123abc"
    assert normalize_cid_value("") == ""


def test_is_inline_attachment_detects_inline_flag():
    assert is_inline_attachment({"isInline": True})
    assert not is_inline_attachment({"isInline": False})
    assert not is_inline_attachment({})


def test_replace_cid_sources_with_data_urls_swaps_known_ids():
    html = '<img src="cid:banner-1"><div style="background:url(cid:logo-2)">x</div>'
    replaced = replace_cid_sources_with_data_urls(
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


def test_replace_cid_sources_with_data_urls_handles_encoded_outlook_cid():
    html = '<img src="cid:image001.png%4001D123ABC">'
    replaced = replace_cid_sources_with_data_urls(
        html,
        {"image001.png@01d123abc": "data:image/png;base64,CCC"},
    )
    assert 'src="data:image/png;base64,CCC"' in replaced


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


def test_hydrate_inline_attachment_bytes_skips_download_when_present():
    graph = _FakeGraph({"contentBytes": "NEVER_USED"})
    fake = _FakeWindow(graph)
    attachments = [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": "att-2",
            "isInline": True,
            "contentId": "<logo>",
            "contentBytes": "INLINE_DATA",
            "contentType": "image/jpeg",
        }
    ]

    hydrated = GeniMailQtWindow._hydrate_inline_attachment_bytes(fake, "msg-2", attachments)

    assert graph.calls == []
    assert hydrated[0]["contentBytes"] == "INLINE_DATA"
