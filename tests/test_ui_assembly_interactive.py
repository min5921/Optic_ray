from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from lidarsim.config import load_project
from lidarsim.optics import reflect_vector
from lidarsim.ui import (
    AssemblyElementEdits,
    SimulationParameterEdits,
    build_interactive_viewport_figure,
    build_viewport_scene,
    create_simulation_variant,
    preview_mirror_target_mate,
)
from lidarsim.ui.app import _selection_event_element_id


def test_baseline_mirror_target_mate_is_already_aligned(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    preview = preview_mirror_target_mate(project)

    assert preview.status == "aligned"
    assert preview.can_apply is True
    assert preview.current_residual_angle_rad == pytest.approx(0.0, abs=1.0e-12)
    assert preview.recommended_quaternion_wxyz == pytest.approx((1.0, 0.0, 0.0, 0.0))
    assert preview.recommended_scanner_rotation_axis_world == pytest.approx((0.0, 1.0, 0.0))
    reflected = reflect_vector(
        preview.incident_direction,
        preview.required_surface_normal_world,
    )
    assert reflected == pytest.approx(preview.desired_reflected_direction, abs=1.0e-12)


def test_mirror_target_mate_applies_reproducible_absolute_pose(
    copied_project: Path,
) -> None:
    output_dir = copied_project.parent / "ui_runs"
    moved_target = create_simulation_variant(
        project_path=copied_project,
        scenario_id="moved_target",
        scenario_output=output_dir / "moved_target.yaml",
        project_output=output_dir / "moved_target_project.yaml",
        parameter_edits=SimulationParameterEdits(
            target_id="target_plane",
            target_center_m=("10 m", "1 m", "0 m"),
            scanner_static_command_angle_rad="2 deg",
        ),
    )
    moved_project = load_project(moved_target.project_path)
    preview = preview_mirror_target_mate(moved_project)

    assert preview.status == "adjustment_required"
    assert math.degrees(preview.current_residual_angle_rad) > 1.0
    assert preview.required_rotation_angle_rad > 0.0

    aligned_variant = create_simulation_variant(
        project_path=moved_target.project_path,
        scenario_id="mirror_mated",
        scenario_output=output_dir / "mirror_mated.yaml",
        project_output=output_dir / "mirror_mated_project.yaml",
        parameter_edits=SimulationParameterEdits(
            scanner_rotation_axis_world=preview.recommended_scanner_rotation_axis_world,
        ),
        element_edits=AssemblyElementEdits(
            element_id=preview.mirror_element_id,
            translation_m=preview.recommended_translation_m,
            quaternion_wxyz=preview.recommended_quaternion_wxyz,
        ),
    )
    aligned_project = load_project(aligned_variant.project_path)
    aligned_preview = preview_mirror_target_mate(aligned_project)

    assert aligned_preview.status == "aligned"
    assert aligned_preview.current_residual_angle_rad == pytest.approx(0.0, abs=1.0e-8)
    assert aligned_project.active_scenario["scanner"]["rotation_axis_world"] == pytest.approx(
        preview.recommended_scanner_rotation_axis_world
    )
    assert np.asarray(aligned_preview.current_reflected_direction) == pytest.approx(
        aligned_preview.desired_reflected_direction,
        abs=1.0e-10,
    )


def test_interactive_viewport_contains_selectable_components_and_mate_overlay(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)
    preview = preview_mirror_target_mate(project)

    figure = build_interactive_viewport_figure(
        scene,
        selected_element_id="scan_mirror",
        mirror_mate_preview=preview,
    )

    component_trace = figure.data[0]
    assert [item[0] for item in component_trace.customdata] == [
        component.element_id for component in scene.components
    ]
    selected_index = [component.element_id for component in scene.components].index("scan_mirror")
    assert component_trace.marker.size[selected_index] == 15
    assert figure.layout.scene.dragmode == "orbit"
    assert any(trace.name == "Mate preview" for trace in figure.data)
    assert any(trace.name == "Recommended normal" for trace in figure.data)


def test_plotly_selection_payload_resolves_component_id() -> None:
    event = {"selection": {"points": [{"customdata": ["scan_mirror"]}]}}

    assert _selection_event_element_id(event) == "scan_mirror"
    assert _selection_event_element_id({"selection": {"points": []}}) is None
