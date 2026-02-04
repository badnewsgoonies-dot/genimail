from dataclasses import dataclass

from pdf_viewer import parse_length_to_inches


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


def parse_length_to_feet(raw: str, default_unit: str = "ft") -> float:
    inches = parse_length_to_inches(raw, default_unit=default_unit)
    return inches / 12.0


def estimate_door_count(linear_feet: float) -> int:
    if linear_feet <= 0:
        return 0
    return max(1, round(linear_feet / 42.0))


def compute_takeoff(
    *,
    linear_feet: float,
    wall_height_feet: float,
    door_count: int = 0,
    door_width_feet: float = 3.0,
    door_height_feet: float = 6.6667,
    window_area_sqft: float = 0.0,
    coats: int = 1,
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
    )
