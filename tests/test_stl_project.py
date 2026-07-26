from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.cli import main
from lidarsim.errors import ConfigValidationError
from lidarsim.results import build_phase2_optical_train_report


ASSET_ID = "test:scene_target"
MATERIAL_REF = "custom:diffuse_gray_020"


def _target_sidecar(
    mesh_name: str,
    *,
    translation_x_m: float = 10.0,
    front_face: bool = True,
    role: str = "target",
    material_ref: str = MATERIAL_REF,
    parent_frame: str = "world",
) -> dict:
    half_sqrt = math.sqrt(0.5)
    # Local +Z를 world -X(front) 또는 +X(back)로 회전한다.
    quaternion = (
        [half_sqrt, 0.0, -half_sqrt, 0.0]
        if front_face
        else [half_sqrt, 0.0, half_sqrt, 0.0]
    )
    return {
        "schema_version": 1,
        "asset_id": ASSET_ID,
        "mesh": {
            "file": mesh_name,
            "format": "stl",
            "binary_preferred": True,
            "unit_scale_m": 1.0,
        },
        "role": role,
        "placement": {
            "parent_frame": parent_frame,
            "translation_m": [translation_x_m, 0.0, 0.0],
            "quaternion_wxyz": quaternion,
        },
        "material": {"default_material_ref": material_ref},
        "validation": {
            "require_closed_mesh": False,
            "normal_policy": "validate",
            "expected_bounds_m": None,
        },
    }


def _install_plane_asset(
    copied_project: Path,
    write_binary_stl,
    *,
    translation_x_m: float = 10.0,
    front_face: bool = True,
    role: str = "target",
    material_ref: str = MATERIAL_REF,
    parent_frame: str = "world",
) -> Path:
    mesh_dir = copied_project.parent.parent / "assets" / "meshes"
    mesh_path = write_binary_stl(
        mesh_dir / "scene_target.stl",
        [
            [(-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, 2.0, 0.0)],
            [(-2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)],
        ],
    )
    sidecar_path = mesh_dir / "scene_target.stl.yaml"
    sidecar_path.write_text(
        yaml.safe_dump(
            _target_sidecar(
                mesh_path.name,
                translation_x_m=translation_x_m,
                front_face=front_face,
                role=role,
                material_ref=material_ref,
                parent_frame=parent_frame,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return sidecar_path


def _set_stl_only_scenario(copied_project: Path, *, legacy_path: bool = False) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    geometry = (
        {"type": "stl_asset", "metadata_file": "assets/meshes/scene_target.stl.yaml"}
        if legacy_path
        else {"type": "stl_asset", "asset_ref": ASSET_ID}
    )
    scenario["scene"]["targets"] = [
        {
            "id": "target_plane",
            "geometry": geometry,
            "material_ref": MATERIAL_REF,
        }
    ]
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )


def _append_stl_target(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scene"]["targets"].append(
        {
            "id": "mesh_target",
            "geometry": {"type": "stl_asset", "asset_ref": ASSET_ID},
            "material_ref": MATERIAL_REF,
        }
    )
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )


def test_stl_asset_project_report_has_rotated_closest_hit_and_strict_schema(
    copied_project: Path,
    write_binary_stl,
) -> None:
    _install_plane_asset(copied_project, write_binary_stl)
    _set_stl_only_scenario(copied_project)
    project = load_project(copied_project)

    report = build_phase2_optical_train_report(
        project,
        created_at=datetime(2026, 7, 26, tzinfo=UTC),
    )
    item = report.stl_intersections[0]

    assert item["asset_id"] == ASSET_ID
    assert item["metadata_file"] == "assets/meshes/scene_target.stl.yaml"
    assert item["hit"] is True
    assert item["status"] == "hit"
    assert item["visibility_status"] == "visible_nearest"
    assert item["contributes_to_center_ray_visibility"] is True
    assert item["footprint_status"] == "not_evaluated"
    assert item["radiometry_status"] == "not_evaluated"
    assert item["intersection"]["distance_m"] == pytest.approx(10.0)
    np.testing.assert_allclose(
        item["intersection"]["point_m"],
        [10.0, 0.0, 0.0],
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        item["intersection"]["geometric_normal"],
        [-1.0, 0.0, 0.0],
        atol=1.0e-12,
    )
    assert item["intersection"]["front_face"] is True
    assert item["intersection"]["barycentric_convention"] == (
        "weights_for_vertices_v0_v1_v2"
    )
    assert report.target_footprints == ()
    assert report.receiver_return["returns"] == []
    assert report.summary["overall_status"] == "warning"
    assert report.summary["target_hit_count"] == 1
    assert report.summary["rectangle_target_hit_count"] == 0
    assert report.summary["stl_target_hit_count"] == 1
    assert report.summary["visible_geometry_type"] == "stl_asset"
    assert report.scene_energy_ledger["status"] == "warning"
    assert report.scene_energy_ledger["power_accounting_status"] == (
        "partial_not_evaluated"
    )

    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="STL M1 integration report",
    )


def test_legacy_metadata_file_is_unambiguous_project_root_relative(
    copied_project: Path,
    write_binary_stl,
) -> None:
    _install_plane_asset(copied_project, write_binary_stl)
    _set_stl_only_scenario(copied_project, legacy_path=True)

    project = load_project(copied_project)

    assert project.active_scenario["scene"]["targets"][0]["geometry"][
        "metadata_file"
    ] == "assets/meshes/scene_target.stl.yaml"


@pytest.mark.parametrize(
    ("case", "expected_text"),
    [
        ("unregistered", "정확히 한 STL sidecar"),
        ("wrong_role", "role='target'"),
        ("material_mismatch", "일치하지 않습니다"),
        ("non_world_parent", "parent_frame='world'"),
    ],
)
def test_stl_target_semantic_gate_rejects_invalid_asset_contract(
    copied_project: Path,
    write_binary_stl,
    case: str,
    expected_text: str,
) -> None:
    material_ref = MATERIAL_REF
    role = "target"
    parent_frame = "world"
    if case == "wrong_role":
        role = "mount"
    elif case == "material_mismatch":
        alternative_path = (
            copied_project.parent.parent
            / "catalog"
            / "materials"
            / "custom"
            / "diffuse_gray_alt.yaml"
        )
        material = yaml.safe_load(
            (
                copied_project.parent.parent
                / "catalog"
                / "materials"
                / "custom"
                / "diffuse_gray_020.yaml"
            ).read_text(encoding="utf-8")
        )
        material["id"] = "custom:diffuse_gray_alt"
        alternative_path.write_text(
            yaml.safe_dump(material, sort_keys=False),
            encoding="utf-8",
        )
        material_ref = "custom:diffuse_gray_alt"
    elif case == "non_world_parent":
        parent_frame = "assembly"

    _install_plane_asset(
        copied_project,
        write_binary_stl,
        role=role,
        material_ref=material_ref,
        parent_frame=parent_frame,
    )
    _set_stl_only_scenario(copied_project)
    if case == "unregistered":
        scenario_path = copied_project.parent / "baseline_1550nm.yaml"
        scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        scenario["scene"]["targets"][0]["geometry"]["asset_ref"] = "test:missing"
        scenario_path.write_text(
            yaml.safe_dump(scenario, sort_keys=False),
            encoding="utf-8",
        )

    with pytest.raises(ConfigValidationError, match=expected_text):
        load_project(copied_project)


def test_one_sided_stl_backface_is_reported_but_not_visible(
    copied_project: Path,
    write_binary_stl,
) -> None:
    _install_plane_asset(copied_project, write_binary_stl, front_face=False)
    _set_stl_only_scenario(copied_project)

    report = build_phase2_optical_train_report(load_project(copied_project))
    item = report.stl_intersections[0]

    assert item["hit"] is False
    assert item["status"] == "backface_culled"
    assert item["miss_reason"] == "backface_culled"
    assert item["intersection"]["hit"] is True
    assert item["intersection"]["front_face"] is False
    assert item["contributes_to_center_ray_visibility"] is False
    assert report.reciprocal_return["power_status"] == "not_evaluated"
    assert report.reciprocal_return["return_power"] is None
    assert report.summary["power_at_return_mirror_w"] is None
    assert report.summary["power_at_fiber_plane_w"] is None


@pytest.mark.parametrize(
    ("mesh_x_m", "visible_type", "power_status"),
    [
        (12.0, "rectangle_plane", "complete"),
        (8.0, "stl_asset", "partial_not_evaluated"),
    ],
)
def test_mixed_rectangle_and_stl_use_global_nearest_visibility(
    copied_project: Path,
    write_binary_stl,
    mesh_x_m: float,
    visible_type: str,
    power_status: str,
) -> None:
    _install_plane_asset(
        copied_project,
        write_binary_stl,
        translation_x_m=mesh_x_m,
    )
    _append_stl_target(copied_project)

    report = build_phase2_optical_train_report(load_project(copied_project))

    assert report.summary["visible_geometry_type"] == visible_type
    assert report.scene_energy_ledger["power_accounting_status"] == power_status
    if visible_type == "rectangle_plane":
        assert report.target_footprints[0]["visibility_status"] == "visible_nearest"
        assert report.target_footprints[0]["estimated_power_on_target_w"] > 0.0
        assert report.stl_intersections[0]["visibility_status"] == (
            "occluded_by_nearer_target"
        )
        assert report.scene_energy_ledger["status"] == "pass"
    else:
        assert report.target_footprints[0]["visibility_status"] == (
            "occluded_by_nearer_target"
        )
        assert report.target_footprints[0]["estimated_power_on_target_w"] == 0.0
        assert report.stl_intersections[0]["visibility_status"] == "visible_nearest"
        assert report.scene_energy_ledger["status"] == "warning"
        assert report.reciprocal_return["power_status"] == "not_evaluated"
        assert report.reciprocal_return["return_power"] is None
        assert report.summary["power_at_return_mirror_w"] is None
        assert report.summary["power_at_return_collimator_w"] is None
        assert report.summary["power_at_fiber_plane_w"] is None


def test_upstream_termination_marks_stl_intersection_not_evaluated(
    copied_project: Path,
    write_binary_stl,
) -> None:
    _install_plane_asset(copied_project, write_binary_stl)
    _set_stl_only_scenario(copied_project)
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["optical_assembly"]["elements"][1]["placement"][
        "transverse_offset_m"
    ] = ["20 mm", "0 mm"]
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )

    report = build_phase2_optical_train_report(load_project(copied_project))

    assert report.stl_intersections[0]["status"] == "not_evaluated"
    assert report.stl_intersections[0]["intersection"] is None
    assert report.summary["stl_closest_hit_status"] == "warning"
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="terminated STL M1 report",
    )


def test_optical_train_cli_writes_stl_closest_hit_report(
    copied_project: Path,
    write_binary_stl,
    tmp_path: Path,
    capsys,
) -> None:
    _install_plane_asset(copied_project, write_binary_stl)
    _set_stl_only_scenario(copied_project)
    output_path = tmp_path / "stl_phase2.yaml"

    exit_code = main(
        [
            "optical-train",
            str(copied_project),
            "--output",
            str(output_path),
        ]
    )
    output = capsys.readouterr()
    loaded = yaml.safe_load(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert loaded["schema_version"] == 4
    assert loaded["stl_intersections"][0]["status"] == "hit"
    assert loaded["summary"]["stl_target_hit_count"] == 1
    assert "stl_hits=1" in output.out
    assert "visible=target_plane/stl_asset" in output.out
