from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.ui import build_viewport_scene
from lidarsim.visualization import render_viewport_scene


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
    assert payload["scenario_id"] == "baseline_1550nm"
    assert payload["model_scope"] == "source_to_static_mirror_rectangle_target_lambertian_virtual_aperture"
    assert payload["placement_edits"] == []
    assert payload["constraints"] == []


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
