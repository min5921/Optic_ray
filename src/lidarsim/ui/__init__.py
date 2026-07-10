"""User-facing UI and optical workspace helpers."""

from .assembly import (
    DEFAULT_GUIDE_TYPES,
    FootprintOverlay,
    GuideLine,
    PlacementConstraint,
    PlacementEdit,
    RaySegment,
    ViewportComponent,
    ViewportPort,
    ViewportScene,
    MirrorTargetMatePreview,
    build_interactive_viewport_figure,
    build_viewport_scene,
    preview_mirror_target_mate,
)
from .dashboard import write_workspace_dashboard_html
from .placement_editor import PlacementVariantResult, create_placement_variant
from .simulation_variant import (
    AssemblyElementEdits,
    SimulationParameterEdits,
    SimulationVariantResult,
    create_simulation_variant,
)
from .runner import UiSimulationRun, run_ui_simulation

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
    "PlacementVariantResult",
    "AssemblyElementEdits",
    "SimulationParameterEdits",
    "SimulationVariantResult",
    "UiSimulationRun",
    "build_viewport_scene",
    "build_interactive_viewport_figure",
    "create_placement_variant",
    "create_simulation_variant",
    "run_ui_simulation",
    "preview_mirror_target_mate",
    "write_workspace_dashboard_html",
]
