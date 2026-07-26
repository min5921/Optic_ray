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
    ProjectDraft,
    ProjectDraftEntry,
    ProjectDraftPreview,
    SimulationParameterEdits,
    SimulationVariantResult,
    VariantIdentity,
    VariantProvenance,
    create_simulation_variant,
    preview_project_draft,
)

if TYPE_CHECKING:
    from .runner import UiSimulationRun, UiVariantSimulationRun


def __getattr__(name: str) -> Any:
    """Visualization import 중 runner 역참조를 피하면서 기존 public API를 유지한다."""

    if name in {
        "UiSimulationRun",
        "UiVariantSimulationRun",
        "run_ui_simulation",
        "run_ui_variant_transaction",
    }:
        from .runner import (
            UiSimulationRun,
            UiVariantSimulationRun,
            run_ui_simulation,
            run_ui_variant_transaction,
        )

        return {
            "UiSimulationRun": UiSimulationRun,
            "UiVariantSimulationRun": UiVariantSimulationRun,
            "run_ui_simulation": run_ui_simulation,
            "run_ui_variant_transaction": run_ui_variant_transaction,
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
    "ProjectDraft",
    "ProjectDraftEntry",
    "ProjectDraftPreview",
    "SimulationParameterEdits",
    "SimulationVariantResult",
    "VariantIdentity",
    "VariantProvenance",
    "UiSimulationRun",
    "UiVariantSimulationRun",
    "build_viewport_scene",
    "build_interactive_viewport_figure",
    "create_placement_variant",
    "create_simulation_variant",
    "preview_project_draft",
    "run_ui_simulation",
    "run_ui_variant_transaction",
    "preview_mirror_target_mate",
    "write_workspace_dashboard_html",
]
