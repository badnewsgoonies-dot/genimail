import math

import pytest

from pdf_viewer import _LRU, format_inches, parse_length_to_inches


@pytest.mark.parametrize(
    ("raw", "default_unit", "expected"),
    [
        ("12", "in", 12.0),
        ("2", "ft", 24.0),
        ("10ft", "in", 120.0),
        ("10'6\"", "in", 126.0),
        ("10 ft 6 in", "in", 126.0),
        ("2500mm", "in", 2500 / 25.4),
        ("2m 30cm", "in", (2 * 39.37007874015748) + (30 / 2.54)),
        ("+3.5in", "in", 3.5),
    ],
)
def test_parse_length_to_inches_valid_inputs(raw, default_unit, expected):
    assert parse_length_to_inches(raw, default_unit=default_unit) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "abc", "10in garbage"])
def test_parse_length_to_inches_invalid_inputs(raw):
    with pytest.raises(ValueError):
        parse_length_to_inches(raw)


def test_format_inches_common_rendering():
    assert format_inches(None) == ""
    assert format_inches(math.nan) == ""
    assert format_inches(0.0) == '0"'
    assert format_inches(12.0) == "1'"
    assert format_inches(126.0) == "10' 6\""
    assert format_inches(-0.5) == '-0.5"'
    assert format_inches(11.99) == "1'"


def test_lru_eviction_and_recency():
    cache = _LRU(max_items=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)

    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3

    cache.clear()
    assert cache.get("a") is None
