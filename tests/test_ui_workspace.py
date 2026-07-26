from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigValidationError
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.ui import (
    SimulationParameterEdits,
    build_viewport_scene,
    create_simulation_variant,
)
from lidarsim.ui.assembly.plotly_viewport import _footprint_coordinates
from lidarsim.visualization import render_viewport_scene
from lidarsim.visualization.workspace import _footprint_polygon


def test_viewport_scene_contains_optical_bench_objects(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    scene = build_viewport_scene(project)

    component_ids = {component.element_id for component in scene.components}
    assert {"source", "collimator", "scan_mirror", "target_plane", "receiver"} <= component_ids
    assert len(scene.ports) >= 3
    assert any(guide.guide_type == "component_local_frame" for guide in scene.guides)
    assert any(guide.guide_type == "port_axis" for guide in scene.guides)
    assert any(guide.guide_type == "mirror_normal" for guide in scene.guides)
    assert any(guide.guide_type == "target_plane_edge" for guide in scene.guides)
    assert any(guide.guide_type == "receiver_fov" for guide in scene.guides)
    assert any(ray.status == "target_hit" for ray in scene.rays)
    assert len(scene.footprints) == 1


def test_viewport_scene_round_trips_as_yaml(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)

    payload = yaml.safe_load(yaml.safe_dump(scene.to_dict(), sort_keys=False))

    assert payload["project_id"] == "optic_ray_default"
    assert payload["schema_version"] == 1
    assert payload["scenario_id"] == "baseline_1550nm"
    assert payload["model_scope"] == "source_to_static_mirror_rectangle_target_lambertian_virtual_aperture"
    assert payload["placement_edits"] == []
    assert payload["constraints"] == []


def test_viewport_scene_is_strict_schema_valid(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    payload = build_viewport_scene(project).to_dict()
    schemas = SchemaStore.load(project_root / "schemas")

    schemas.validate(
        payload,
        "viewport_scene.schema.json",
        source="test viewport scene",
    )
    payload["components"][0]["typo_origin"] = [0.0, 0.0, 0.0]
    with pytest.raises(ConfigValidationError, match="Additional properties"):
        schemas.validate(
            payload,
            "viewport_scene.schema.json",
            source="invalid viewport scene",
        )


def test_viewport_component_frames_match_physical_directions(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)
    components = {component.element_id: component for component in scene.components}

    target_rotation = np.asarray(
        components["target_plane"].rotation_world_from_component,
        dtype=np.float64,
    )
    receiver_rotation = np.asarray(
        components["receiver"].rotation_world_from_component,
        dtype=np.float64,
    )

    assert target_rotation[:, 2] == pytest.approx([-1.0, 0.0, 0.0])
    assert target_rotation[:, 0] == pytest.approx([0.0, -1.0, 0.0])
    assert target_rotation[:, 1] == pytest.approx([0.0, 0.0, 1.0])
    assert np.linalg.det(target_rotation) == pytest.approx(1.0)
    assert receiver_rotation[:, 2] == pytest.approx([1.0, 0.0, 0.0])
    assert np.linalg.det(receiver_rotation) == pytest.approx(1.0)


def test_workspace_renderer_writes_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)
    output_path = tmp_path / "workspace.png"

    result = render_viewport_scene(scene, output_path, dpi=72)

    assert result == output_path.resolve()
    payload = output_path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 10_000


def test_rotated_oblique_footprint_axes_flow_from_physics_to_both_renderers(
    copied_project: Path,
) -> None:
    incidence_angle = np.pi / 4.0
    target_normal = np.array(
        [-np.cos(incidence_angle), 0.0, np.sin(incidence_angle)],
        dtype=np.float64,
    )
    projected_incidence = np.array(
        [np.sin(incidence_angle), 0.0, np.cos(incidence_angle)],
        dtype=np.float64,
    )
    target_roll = np.pi / 3.0
    width_axis = (
        np.cos(target_roll) * np.array([0.0, 1.0, 0.0], dtype=np.float64)
        + np.sin(target_roll) * projected_incidence
    )
    output_dir = copied_project.parent / "ui_runs"
    variant = create_simulation_variant(
        project_path=copied_project,
        scenario_id="rotated_oblique_footprint",
        scenario_output=output_dir / "rotated_oblique_footprint.yaml",
        project_output=output_dir / "rotated_oblique_footprint_project.yaml",
        parameter_edits=SimulationParameterEdits(
            target_id="target_plane",
            target_normal=tuple(float(value) for value in target_normal),
            target_width_axis=tuple(float(value) for value in width_axis),
        ),
    )
    project = load_project(variant.project_path)
    report = build_phase2_optical_train_report(project)
    scene = build_viewport_scene(project, report=report)
    footprint_report = report.target_footprints[0]
    overlay = scene.footprints[0]

    schemas = SchemaStore.load(copied_project.parent.parent / "schemas")
    schemas.validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="rotated oblique phase2 report",
    )
    schemas.validate(
        scene.to_dict(),
        "viewport_scene.schema.json",
        source="rotated oblique viewport scene",
    )

    assert np.asarray(overlay.major_axis_world) == pytest.approx(
        footprint_report["projected_footprint_major_axis_world"]
    )
    assert np.asarray(overlay.minor_axis_world) == pytest.approx(
        footprint_report["projected_footprint_minor_axis_world"]
    )
    assert overlay.orientation_axis_world == overlay.major_axis_world
    assert abs(float(np.dot(overlay.major_axis_world, projected_incidence))) == pytest.approx(1.0)
    assert np.cross(overlay.major_axis_world, overlay.minor_axis_world) == pytest.approx(
        target_normal,
        abs=1.0e-12,
    )

    center = np.asarray(overlay.hit_center_m, dtype=np.float64)
    expected_major_point = (
        center + overlay.major_radius_m * np.asarray(overlay.major_axis_world)
    )
    expected_minor_point = (
        center + overlay.minor_radius_m * np.asarray(overlay.minor_axis_world)
    )
    plotly_points = _footprint_coordinates(overlay, samples=5)
    matplotlib_points = _footprint_polygon(overlay.to_dict(), samples=4)
    assert plotly_points[0] == pytest.approx(expected_major_point)
    assert plotly_points[1] == pytest.approx(expected_minor_point)
    assert matplotlib_points[0] == pytest.approx(expected_major_point)
    assert matplotlib_points[1] == pytest.approx(expected_minor_point)
