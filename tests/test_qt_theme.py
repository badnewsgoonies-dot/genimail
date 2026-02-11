import importlib.util
from pathlib import Path


_THEME_PATH = Path(__file__).resolve().parents[1] / "genimail_qt" / "theme.py"
_SPEC = importlib.util.spec_from_file_location("genimail_qt_theme_test", _THEME_PATH)
_THEME = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_THEME)

APP_STYLE = _THEME.APP_STYLE
THEME_DARK = _THEME.THEME_DARK
THEME_LIGHT = _THEME.THEME_LIGHT
normalize_theme_mode = _THEME.normalize_theme_mode
style_for_theme = _THEME.style_for_theme


def test_normalize_theme_mode_defaults_to_light():
    assert normalize_theme_mode(None) == THEME_LIGHT
    assert normalize_theme_mode("") == THEME_LIGHT
    assert normalize_theme_mode("invalid") == THEME_LIGHT


def test_normalize_theme_mode_accepts_dark_case_insensitive():
    assert normalize_theme_mode("dark") == THEME_DARK
    assert normalize_theme_mode(" DARK ") == THEME_DARK


def test_style_for_theme_light_matches_default_style():
    assert style_for_theme(THEME_LIGHT) == APP_STYLE


def test_style_for_theme_dark_includes_dark_palette_overrides():
    style = style_for_theme(THEME_DARK)
    assert "background-color: #1A1814;" in style
    assert "QPushButton#themeToggleButton:checked" in style
