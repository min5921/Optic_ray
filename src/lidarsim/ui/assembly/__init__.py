"""Optical assembly workspace data contracts."""

from .plotly_viewport import DEFAULT_GUIDE_TYPES, build_interactive_viewport_figure
from .snapping import MirrorTargetMatePreview, preview_mirror_target_mate
from .viewport_data import (
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

__all__ = [
    "DEFAULT_GUIDE_TYPES",
    "FootprintOverlay",
    "GuideLine",
    "PlacementConstraint",
    "PlacementEdit",
    "RaySegment",
    "ViewportComponent",
    "ViewportPort",
    "ViewportScene",
    "MirrorTargetMatePreview",
    "build_viewport_scene",
    "build_interactive_viewport_figure",
    "preview_mirror_target_mate",
]
