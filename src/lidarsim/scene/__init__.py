"""Scene primitive intersection and footprint estimation APIs."""

from .footprint import TargetFootprint, estimate_rectangle_plane_footprint
from .mesh import (
    RayMeshIntersection,
    TriangleMesh,
    build_world_triangle_mesh,
    intersect_ray_mesh,
    intersect_ray_triangle_mesh,
    world_triangle_mesh_from_asset,
)
from .mesh_targets import (
    StlTargetIntersection,
    evaluate_stl_target_intersections,
    resolve_mixed_target_visibility,
    resolve_project_stl_asset,
)
from .targets import (
    TargetIntersection,
    evaluate_target_footprints,
    intersect_rectangle_plane,
    rectangle_plane_axes,
)

__all__ = [
    "TargetFootprint",
    "TargetIntersection",
    "StlTargetIntersection",
    "RayMeshIntersection",
    "TriangleMesh",
    "build_world_triangle_mesh",
    "estimate_rectangle_plane_footprint",
    "evaluate_target_footprints",
    "evaluate_stl_target_intersections",
    "intersect_ray_mesh",
    "intersect_ray_triangle_mesh",
    "intersect_rectangle_plane",
    "rectangle_plane_axes",
    "resolve_mixed_target_visibility",
    "resolve_project_stl_asset",
    "world_triangle_mesh_from_asset",
]
