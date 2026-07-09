"""User-facing UI and optical workspace helpers."""

from .assembly import (
    FootprintOverlay,
    GuideLine,
    PlacementConstraint,
    PlacementEdit,
    RaySegment,
    ViewportComponent,
    ViewportPort,
    ViewportScene,
    build_viewport_scene,
)
from .dashboard import write_workspace_dashboard_html
from .placement_editor import PlacementVariantResult, create_placement_variant

__all__ = [
    "FootprintOverlay",
    "GuideLine",
    "PlacementConstraint",
    "PlacementEdit",
    "RaySegment",
    "ViewportComponent",
    "ViewportPort",
    "ViewportScene",
    "PlacementVariantResult",
    "build_viewport_scene",
    "create_placement_variant",
    "write_workspace_dashboard_html",
]
