from genimail.infra.graph_client import GRAPH_BASE, GraphClient


def test_send_mail_posts_sendmail_for_standard_send():
    client = GraphClient.__new__(GraphClient)
    calls = []
    client._post = lambda url, data: calls.append((url, data))

    client.send_mail(
        ["to@example.com"],
        ["cc@example.com"],
        "Subject",
        "Body",
        attachments=[{"name": "a.txt"}],
    )

    assert len(calls) == 1
    url, payload = calls[0]
    assert url == f"{GRAPH_BASE}/me/sendMail"
    assert payload["saveToSentItems"] is True
    assert payload["message"]["toRecipients"][0]["emailAddress"]["address"] == "to@example.com"
    assert payload["message"]["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"
    assert payload["message"]["attachments"] == [{"name": "a.txt"}]


def test_send_mail_reply_mode_still_posts_sendmail():
    client = GraphClient.__new__(GraphClient)
    calls = []
    client._post = lambda url, data: calls.append((url, data))

    client.send_mail(
        ["reply@example.com"],
        [],
        "Re: Subject",
        "Reply body",
        reply_to_id="orig-message-id",
        reply_mode="reply_all",
    )

    assert len(calls) == 1
    assert calls[0][0] == f"{GRAPH_BASE}/me/sendMail"
