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

__all__ = [
    "FootprintOverlay",
    "GuideLine",
    "PlacementConstraint",
    "PlacementEdit",
    "RaySegment",
    "ViewportComponent",
    "ViewportPort",
    "ViewportScene",
    "build_viewport_scene",
    "write_workspace_dashboard_html",
]
