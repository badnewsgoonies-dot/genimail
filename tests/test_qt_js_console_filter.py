from genimail_qt import window as window_module


def test_is_js_noise_message_filters_known_site_warnings():
    assert window_module._is_js_noise_message(
        "The resource https://example.com/x was preloaded using link preload but not used within a few seconds."
    )
    assert window_module._is_js_noise_message("Uncaught ReferenceError: sj_evt is not defined")
    assert window_module._is_js_noise_message("Permissions policy violation: unload is not allowed in this document.")


def test_is_js_noise_message_keeps_unknown_messages():
    assert not window_module._is_js_noise_message("TypeError: Cannot read properties of undefined")


def test_is_local_console_source_identifies_local_sources():
    assert window_module._is_local_console_source("about:blank")
    assert window_module._is_local_console_source("file:///tmp/preview.html")
    assert window_module._is_local_console_source("qrc:/qtwebchannel/qwebchannel.js")


def test_is_local_console_source_ignores_remote_sources():
    assert not window_module._is_local_console_source("https://www.bing.com")
