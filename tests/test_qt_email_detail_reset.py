from genimail_qt.mixins.email_list import EmailListMixin


class _FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _FakeWebView:
    def __init__(self):
        self.html = ""

    def setHtml(self, html):
        self.html = html


class _FakeAttachmentList:
    def __init__(self):
        self.clears = 0

    def clear(self):
        self.clears += 1


class _Probe(EmailListMixin):
    def __init__(self):
        self.current_message = {"id": "msg-1"}
        self.message_header = _FakeLabel()
        self.email_preview = _FakeWebView()
        self.attachment_list = _FakeAttachmentList()
        self.thumbnail_payloads = []
        self.download_clear_calls = 0

    def _render_attachment_thumbnails(self, attachments):
        self.thumbnail_payloads.append(list(attachments))

    def _clear_download_results(self):
        self.download_clear_calls += 1


def test_clear_detail_view_clears_download_results_and_attachments():
    probe = _Probe()

    EmailListMixin._clear_detail_view(probe, "No messages in this folder.")

    assert probe.current_message is None
    assert probe.message_header.text == "No messages"
    assert "No messages in this folder." in probe.email_preview.html
    assert probe.attachment_list.clears == 1
    assert probe.thumbnail_payloads == [[]]
    assert probe.download_clear_calls == 1
