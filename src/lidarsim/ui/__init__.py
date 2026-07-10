"""User-facing UI and optical workspace helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from .runner import UiSimulationRun


def __getattr__(name: str) -> Any:
    """Visualization import 중 runner 역참조를 피하면서 기존 public API를 유지한다."""

    if name in {"UiSimulationRun", "run_ui_simulation"}:
        from .runner import UiSimulationRun, run_ui_simulation

        return {
            "UiSimulationRun": UiSimulationRun,
            "run_ui_simulation": run_ui_simulation,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
