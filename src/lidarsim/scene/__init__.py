"""Scene primitive intersection and footprint estimation APIs."""

from .footprint import TargetFootprint, estimate_rectangle_plane_footprint
from .targets import TargetIntersection, evaluate_target_footprints, intersect_rectangle_plane

__all__ = [
    "TargetFootprint",
    "TargetIntersection",
    "estimate_rectangle_plane_footprint",
    "evaluate_target_footprints",
    "intersect_rectangle_plane",
]
