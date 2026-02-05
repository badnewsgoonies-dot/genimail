from genimail.domain.helpers import format_size, strip_html, token_cache_path_for_client_id
from genimail.domain.quotes import build_quote_context, render_quote_template_text
from genimail.infra.config_store import Config
from genimail.paths import TOKEN_CACHE_FILE


def test_helper_module_exports_work():
    assert format_size(2048) == "2.0 KB"
    assert "Hello" in strip_html("<p>Hello</p>")
    assert token_cache_path_for_client_id(None) == TOKEN_CACHE_FILE


def test_quote_render_from_module():
    context = build_quote_context(None, to_value="person@example.com", subject_value="Hallway Paint")
    rendered = render_quote_template_text("{{CLIENT_EMAIL}} | {{PROJECT_NAME}}", context)
    assert "person@example.com" in rendered
    assert "Hallway Paint" in rendered


def test_config_defaults_include_quote_paths():
    config = Config()
    assert config.get("quote_template_path")
    assert config.get("quote_output_dir")
    assert config.get("browser_engine") == "webview2"
    assert config.get("company_collapsed") is False
    assert isinstance(config.get("company_favorites"), list)
    assert isinstance(config.get("company_hidden"), list)
