from genimail_qt.takeoff_engine import compute_takeoff, estimate_door_count, parse_length_to_feet


def test_parse_length_to_feet_basic():
    assert abs(parse_length_to_feet("8ft") - 8.0) < 1e-6
    assert abs(parse_length_to_feet("96in") - 8.0) < 1e-6


def test_compute_takeoff_area_math():
    result = compute_takeoff(
        linear_feet=120.0,
        wall_height_feet=8.0,
        door_count=2,
        window_area_sqft=20.0,
        coats=2,
    )
    assert round(result.gross_area_sqft, 2) == 960.0
    assert round(result.opening_area_sqft, 2) == round((2 * 3.0 * 6.6667) + 20.0, 2)
    assert result.net_area_sqft < result.gross_area_sqft
    assert round(result.paint_area_sqft, 2) == round(result.net_area_sqft * 2, 2)


def test_estimate_door_count_non_negative():
    assert estimate_door_count(0) == 0
    assert estimate_door_count(40) >= 1
