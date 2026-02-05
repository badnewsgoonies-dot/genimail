from genimail_qt.webview_utils import is_js_noise_message, is_local_console_source


def test_is_js_noise_message_filters_known_site_warnings():
    assert is_js_noise_message(
        "The resource https://example.com/x was preloaded using link preload but not used within a few seconds."
    )
    assert is_js_noise_message("Uncaught ReferenceError: sj_evt is not defined")
    assert is_js_noise_message("Permissions policy violation: unload is not allowed in this document.")


def test_is_js_noise_message_keeps_unknown_messages():
    assert not is_js_noise_message("TypeError: Cannot read properties of undefined")


def test_is_local_console_source_identifies_local_sources():
    assert is_local_console_source("about:blank")
    assert is_local_console_source("file:///tmp/preview.html")
    assert is_local_console_source("qrc:/qtwebchannel/qwebchannel.js")


def test_is_local_console_source_ignores_remote_sources():
    assert not is_local_console_source("https://www.bing.com")
