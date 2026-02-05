import pytest

from genimail_qt.takeoff_engine import (
    HAS_SHAPELY,
    compute_floor_plan,
    compute_takeoff,
    compute_wall_elevation,
    estimate_door_count,
    parse_length_to_feet,
)


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


def test_compute_floor_plan_square():
    if not HAS_SHAPELY:
        pytest.skip("shapely not installed")

    result = compute_floor_plan([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert round(result.floor_area_sqft, 2) == 100.0
    assert round(result.perimeter_feet, 2) == 40.0
    assert result.centroid == (5.0, 5.0)


def test_compute_wall_elevation_overlapping_openings():
    if not HAS_SHAPELY:
        pytest.skip("shapely not installed")

    result = compute_wall_elevation(
        wall_length_feet=10.0,
        wall_height_feet=8.0,
        openings=[
            (1.0, 1.0, 2.0, 2.0),
            (2.0, 2.0, 2.0, 2.0),
        ],
    )
    assert round(result.gross_area_sqft, 2) == 80.0
    assert round(result.opening_area_sqft, 2) == 7.0
    assert round(result.net_area_sqft, 2) == 73.0
