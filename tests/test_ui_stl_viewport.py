from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.ui import build_interactive_viewport_figure, build_viewport_scene
from lidarsim.ui.assembly.viewport_data import _display_triangle_indices
from lidarsim.visualization import render_viewport_scene


def _write_stl_target_project(
    copied_project: Path,
    write_binary_stl,
    *,
    y_offset_m: float = 0.0,
) -> Path:
    root = copied_project.parent.parent
    mesh_dir = root / "assets" / "meshes"
    mesh_path = write_binary_stl(
        mesh_dir / "viewport_plane.stl",
        [
            [
                (10.0, y_offset_m - 1.0, -1.0),
                (10.0, y_offset_m - 1.0, 1.0),
                (10.0, y_offset_m + 1.0, 1.0),
            ],
            [
                (10.0, y_offset_m - 1.0, -1.0),
                (10.0, y_offset_m + 1.0, 1.0),
                (10.0, y_offset_m + 1.0, -1.0),
            ],
        ],
    )
    metadata = {
        "schema_version": 1,
        "asset_id": "test:viewport_plane",
        "mesh": {
            "file": mesh_path.name,
            "format": "stl",
            "binary_preferred": True,
            "unit_scale_m": 1.0,
        },
        "role": "target",
        "placement": {
            "parent_frame": "world",
            "translation_m": [0.0, 0.0, 0.0],
            "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
        },
        "material": {"default_material_ref": "custom:diffuse_gray_020"},
        "validation": {
            "require_closed_mesh": False,
            "normal_policy": "validate",
            "expected_bounds_m": None,
        },
    }
    (mesh_dir / "viewport_plane.stl.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False),
        encoding="utf-8",
    )

    scenario_path = root / "configs" / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scene"]["targets"][0]["geometry"] = {
        "type": "stl_asset",
        "asset_ref": "test:viewport_plane",
    }
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )
    return copied_project


def test_stl_viewport_uses_world_mesh_and_actual_report_hit(
    copied_project: Path,
    write_binary_stl,
) -> None:
    project_path = _write_stl_target_project(copied_project, write_binary_stl)
    project = load_project(project_path)
    report = build_phase2_optical_train_report(project)

    scene = build_viewport_scene(project, report=report)

    assert scene.schema_version == 2
    assert scene.footprints == ()
    assert len(scene.meshes) == 1
    mesh = scene.meshes[0]
    assert mesh.target_id == "target_plane"
    assert mesh.asset_id == "test:viewport_plane"
    assert mesh.source_triangle_count == 2
    assert mesh.display_triangle_count == 2
    assert mesh.display_triangle_indices == (0, 1)
    assert not mesh.decimated
    assert mesh.geometry_semantics == "geometry_only_not_optical_scatterers"

    assert len(scene.mesh_hits) == 1
    hit = scene.mesh_hits[0]
    assert hit.point_m == pytest.approx([10.0, 0.0, 0.0])
    assert hit.geometric_normal == pytest.approx([-1.0, 0.0, 0.0])
    assert hit.normal_end_m[0] < hit.point_m[0]
    assert hit.distance_m == pytest.approx(10.0)
    assert hit.contributes_to_center_ray_visibility
    assert hit.geometry_only

    stl_rays = [ray for ray in scene.rays if ray.status == "stl_target_hit_geometry_only"]
    assert len(stl_rays) == 1
    assert stl_rays[0].end_m == pytest.approx(hit.point_m)
    assert stl_rays[0].power_w is None
    assert stl_rays[0].radius_end_m is None
    assert any("footprint" in warning and "표시하지 않습니다" in warning for warning in scene.warnings)

    SchemaStore.load(project_path.parent.parent / "schemas").validate(
        scene.to_dict(),
        "viewport_scene.schema.json",
        source="M1 STL viewport",
    )


def test_stl_mesh_and_hit_have_plotly_and_matplotlib_overlays(
    copied_project: Path,
    write_binary_stl,
    tmp_path: Path,
) -> None:
    project_path = _write_stl_target_project(copied_project, write_binary_stl)
    project = load_project(project_path)
    scene = build_viewport_scene(project)

    figure = build_interactive_viewport_figure(scene)
    mesh_traces = [trace for trace in figure.data if trace.type == "mesh3d"]
    hit_traces = [trace for trace in figure.data if "STL closest hit + normal" in trace.name]
    assert len(mesh_traces) == 1
    assert len(mesh_traces[0].i) == scene.meshes[0].display_triangle_count
    assert len(hit_traces) == 1
    assert hit_traces[0].x[0] == pytest.approx(scene.mesh_hits[0].point_m[0])
    assert hit_traces[0].x[1] == pytest.approx(scene.mesh_hits[0].normal_end_m[0])

    output = render_viewport_scene(scene, tmp_path / "m1_stl_workspace.png", dpi=72)
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 10_000


def test_display_decimation_is_deterministic_and_preserves_reported_hit() -> None:
    first = _display_triangle_indices(10_000, limit=7, preserve=(4_321,))
    second = _display_triangle_indices(10_000, limit=7, preserve=(4_321,))

    assert first == second
    assert len(first) == 7
    assert first == tuple(sorted(first))
    assert 4_321 in first
    assert len(set(first)) == len(first)


def test_stl_miss_shows_mesh_without_fake_hit_ray_or_footprint(
    copied_project: Path,
    write_binary_stl,
) -> None:
    project_path = _write_stl_target_project(
        copied_project,
        write_binary_stl,
        y_offset_m=5.0,
    )
    project = load_project(project_path)
    report = build_phase2_optical_train_report(project)
    record = report.stl_intersections[0]
    scene = build_viewport_scene(project, report=report)

    assert record["hit"] is False
    assert record["status"] == "no_hit"
    assert len(scene.meshes) == 1
    assert scene.mesh_hits == ()
    assert scene.footprints == ()
    assert not any(ray.status == "stl_target_hit_geometry_only" for ray in scene.rays)


def test_rectangle_baseline_keeps_empty_mesh_contract_and_existing_footprint(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)

    assert scene.meshes == ()
    assert scene.mesh_hits == ()
    assert len(scene.footprints) == 1
    assert any(ray.status == "target_hit" for ray in scene.rays)
    assert not any(ray.status == "stl_target_hit_geometry_only" for ray in scene.rays)
