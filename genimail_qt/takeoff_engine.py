from dataclasses import dataclass
from typing import Iterable

from genimail.constants import (
    INCHES_PER_FOOT,
    TAKEOFF_DEFAULT_COATS,
    TAKEOFF_DEFAULT_DOOR_HEIGHT_FEET,
    TAKEOFF_DEFAULT_DOOR_WIDTH_FEET,
    TAKEOFF_DOOR_ESTIMATE_LINEAR_FEET,
    TAKEOFF_OPENING_RECT_FIELD_COUNT,
)
from genimail.domain.helpers import parse_length_to_inches

try:
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    HAS_SHAPELY = True
except Exception:
    HAS_SHAPELY = False


@dataclass(frozen=True)
class TakeoffResult:
    linear_feet: float
    wall_height_feet: float
    gross_area_sqft: float
    opening_area_sqft: float
    net_area_sqft: float
    coats: int
    paint_area_sqft: float
    door_count: int
    floor_area_sqft: float = 0.0
    perimeter_feet: float = 0.0
    centroid: tuple[float, float] | None = None


def parse_length_to_feet(raw: str, default_unit: str = "ft") -> float:
    inches = parse_length_to_inches(raw, default_unit=default_unit)
    return inches / INCHES_PER_FOOT


def estimate_door_count(linear_feet: float) -> int:
    if linear_feet <= 0:
        return 0
    return max(1, round(linear_feet / TAKEOFF_DOOR_ESTIMATE_LINEAR_FEET))


def _ensure_shapely() -> None:
    if not HAS_SHAPELY:
        raise RuntimeError("Shapely is required for advanced takeoff geometry. Install with: pip install shapely")


def compute_takeoff(
    *,
    linear_feet: float,
    wall_height_feet: float,
    door_count: int = 0,
    door_width_feet: float = TAKEOFF_DEFAULT_DOOR_WIDTH_FEET,
    door_height_feet: float = TAKEOFF_DEFAULT_DOOR_HEIGHT_FEET,
    window_area_sqft: float = 0.0,
    coats: int = TAKEOFF_DEFAULT_COATS,
) -> TakeoffResult:
    linear = max(0.0, float(linear_feet))
    wall_height = max(0.0, float(wall_height_feet))
    doors = max(0, int(door_count))
    openings = max(0.0, float(window_area_sqft)) + (doors * max(0.0, door_width_feet) * max(0.0, door_height_feet))
    gross = linear * wall_height
    net = max(0.0, gross - openings)
    coats_count = max(1, int(coats))
    paint_area = net * coats_count
    return TakeoffResult(
        linear_feet=linear,
        wall_height_feet=wall_height,
        gross_area_sqft=gross,
        opening_area_sqft=openings,
        net_area_sqft=net,
        coats=coats_count,
        paint_area_sqft=paint_area,
        door_count=doors,
        perimeter_feet=linear,
    )


def compute_floor_plan(
    points: Iterable[tuple[float, float]],
    *,
    scale_factor: float = 1.0,
    coats: int = TAKEOFF_DEFAULT_COATS,
) -> TakeoffResult:
    """Compute area and perimeter from an ordered polygon point sequence."""
    _ensure_shapely()

    point_list = list(points or [])
    coats_count = max(1, int(coats))
    if len(point_list) < 3:
        return TakeoffResult(
            linear_feet=0.0,
            wall_height_feet=0.0,
            gross_area_sqft=0.0,
            opening_area_sqft=0.0,
            net_area_sqft=0.0,
            coats=coats_count,
            paint_area_sqft=0.0,
            door_count=0,
        )

    scale = max(0.0, float(scale_factor))
    if scale == 0.0:
        scale = 1.0
    scaled_points = [(float(x) * scale, float(y) * scale) for x, y in point_list]
    polygon = Polygon(scaled_points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        return TakeoffResult(
            linear_feet=0.0,
            wall_height_feet=0.0,
            gross_area_sqft=0.0,
            opening_area_sqft=0.0,
            net_area_sqft=0.0,
            coats=coats_count,
            paint_area_sqft=0.0,
            door_count=0,
        )

    area = max(0.0, float(polygon.area))
    perimeter = max(0.0, float(polygon.length))
    centroid = (float(polygon.centroid.x), float(polygon.centroid.y))
    return TakeoffResult(
        linear_feet=perimeter,
        wall_height_feet=0.0,
        gross_area_sqft=area,
        opening_area_sqft=0.0,
        net_area_sqft=area,
        coats=coats_count,
        paint_area_sqft=area * coats_count,
        door_count=estimate_door_count(perimeter),
        floor_area_sqft=area,
        perimeter_feet=perimeter,
        centroid=centroid,
    )


def compute_wall_elevation(
    *,
    wall_length_feet: float,
    wall_height_feet: float,
    openings: Iterable[tuple[float, float, float, float]] | None = None,
    coats: int = TAKEOFF_DEFAULT_COATS,
) -> TakeoffResult:
    """Compute wall net paint area by clipping rectangular openings to wall bounds."""
    _ensure_shapely()

    linear = max(0.0, float(wall_length_feet))
    height = max(0.0, float(wall_height_feet))
    coats_count = max(1, int(coats))
    gross = linear * height
    if gross <= 0:
        return TakeoffResult(
            linear_feet=linear,
            wall_height_feet=height,
            gross_area_sqft=0.0,
            opening_area_sqft=0.0,
            net_area_sqft=0.0,
            coats=coats_count,
            paint_area_sqft=0.0,
            door_count=0,
            perimeter_feet=linear,
        )

    wall_polygon = box(0, 0, linear, height)
    clipped_openings = []
    for opening in openings or []:
        if len(opening) != TAKEOFF_OPENING_RECT_FIELD_COUNT:
            continue
        x, y, width, opening_height = (float(opening[0]), float(opening[1]), float(opening[2]), float(opening[3]))
        width = max(0.0, width)
        opening_height = max(0.0, opening_height)
        if width == 0.0 or opening_height == 0.0:
            continue
        opening_polygon = box(x, y, x + width, y + opening_height).intersection(wall_polygon)
        if not opening_polygon.is_empty:
            clipped_openings.append(opening_polygon)

    opening_area = 0.0
    if clipped_openings:
        opening_area = max(0.0, float(unary_union(clipped_openings).area))

    net = max(0.0, gross - opening_area)
    return TakeoffResult(
        linear_feet=linear,
        wall_height_feet=height,
        gross_area_sqft=gross,
        opening_area_sqft=opening_area,
        net_area_sqft=net,
        coats=coats_count,
        paint_area_sqft=net * coats_count,
        door_count=0,
        perimeter_feet=linear,
    )
