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
from .simulation_variant import (
    AssemblyElementEdits,
    SimulationParameterEdits,
    SimulationVariantResult,
    create_simulation_variant,
)
from .runner import UiSimulationRun, run_ui_simulation

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
    "AssemblyElementEdits",
    "SimulationParameterEdits",
    "SimulationVariantResult",
    "UiSimulationRun",
    "build_viewport_scene",
    "create_placement_variant",
    "create_simulation_variant",
    "run_ui_simulation",
    "write_workspace_dashboard_html",
]
