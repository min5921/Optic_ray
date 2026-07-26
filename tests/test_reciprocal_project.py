from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigValidationError
from lidarsim.optics import propagate_transmitter_train
from lidarsim.receiver import (
    ResolvedPlaneFrame,
    evaluate_project_reciprocal_return,
    reverse_ideal_thin_lens_center_ray,
)
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.scene import evaluate_target_footprints


def test_baseline_reciprocal_project_exact_retrace_and_virtual_intermediate(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase2_optical_train_report(project)

    reciprocal = report.reciprocal_return
    path = reciprocal["path"]
    assert reciprocal["architecture"] == "reciprocal_single_mode_fiber"
    assert reciprocal["return_path"] == {
        "target_ref": "target_plane",
        "scanner_element_id": "scan_mirror",
        "collimator_element_id": "collimator",
        "fiber_element_id": "source",
        "reuse_transmit_path": True,
    }
    assert reciprocal["status"] == "pass"
    assert path is not None
    assert path["mirror_hit"]["aperture_status"] == "pass"
    assert path["collimator_hit"]["aperture_status"] == "pass"
    assert path["fiber_hit"]["intersection"]["hit"] is True
    assert path["closure"]["maximum_position_residual_m"] < 1.0e-12
    assert path["closure"]["maximum_angular_residual_rad"] < 1.0e-12
    assert reciprocal["power_status"] == "not_evaluated"
    assert reciprocal["fiber_coupling_status"] == "not_evaluated"
    assert reciprocal["detector_status"] == "not_evaluated"
    assert report.summary["power_at_virtual_aperture_w"] > 0.0
    assert report.receiver_return["power_at_virtual_aperture_w"] == pytest.approx(
        report.summary["estimated_received_power_w"]
    )

    source_port = project.catalog["custom:baseline_fiber_source"].data["ports"][0]
    collimator_ports = project.catalog["custom:ideal_collimator_f20"].data["ports"]
    assert source_port["role"] == "bidirectional"
    assert {port["role"] for port in collimator_ports} == {"bidirectional"}


def test_reverse_thin_lens_law_exactly_retraces_off_axis_forward_ray() -> None:
    focal_length_m = 0.02
    u_m = 0.001
    v_m = -0.0005
    plane = ResolvedPlaneFrame(
        origin_m=np.zeros(3, dtype=np.float64),
        normal=np.asarray([0.0, 0.0, 1.0]),
        x_axis=np.asarray([1.0, 0.0, 0.0]),
    )
    forward_after_lens = np.asarray(
        [-u_m / focal_length_m, -v_m / focal_length_m, 1.0],
        dtype=np.float64,
    )
    forward_after_lens /= np.linalg.norm(forward_after_lens)

    reverse_output = reverse_ideal_thin_lens_center_ray(
        -forward_after_lens,
        [u_m, v_m, 0.0],
        plane,
        focal_length_m=focal_length_m,
    )

    assert reverse_output == pytest.approx([0.0, 0.0, -1.0], abs=1.0e-14)


def test_target_return_perturbation_reports_closure_warning(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    train = propagate_transmitter_train(project)
    footprints = evaluate_target_footprints(project, train.final_state.state)
    visible_index = next(
        index
        for index, footprint in enumerate(footprints)
        if footprint.contributes_to_scene_energy
    )
    visible = footprints[visible_index]
    assert visible.intersection.hit_center_m is not None
    perturbed_hit = np.array(visible.intersection.hit_center_m, copy=True)
    perturbed_hit[1] += 1.0e-3
    perturbed_hit.setflags(write=False)
    perturbed_intersection = replace(
        visible.intersection,
        hit_center_m=perturbed_hit,
    )
    perturbed_footprints = list(footprints)
    perturbed_footprints[visible_index] = replace(
        visible,
        intersection=perturbed_intersection,
    )

    result = evaluate_project_reciprocal_return(
        project,
        train,
        tuple(perturbed_footprints),
    )

    assert result.path is not None
    assert result.status == "warning"
    assert result.path.closure.maximum_position_residual_m is not None
    assert result.path.closure.maximum_position_residual_m > 0.0
    assert result.path.closure.maximum_angular_residual_rad is not None
    assert result.path.closure.maximum_angular_residual_rad > 0.0
    assert result.return_path is not None
    with pytest.raises(TypeError):
        result.return_path["target_ref"] = "mutated"


def test_configured_return_target_is_not_silently_replaced_by_nearer_target(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scene"]["targets"].insert(
        0,
        {
            "id": "near_blocker",
            "geometry": {
                "type": "rectangle_plane",
                "center_m": [5.0, 0.0, 0.0],
                "normal": [-1.0, 0.0, 0.0],
                "width_axis": [0.0, -1.0, 0.0],
                "width_m": "4 m",
                "height_m": "4 m",
            },
            "material_ref": "custom:diffuse_gray_020",
        },
    )
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    project = load_project(copied_project)
    train = propagate_transmitter_train(project)
    footprints = evaluate_target_footprints(project, train.final_state.state)

    result = evaluate_project_reciprocal_return(project, train, footprints)

    assert result.status == "not_evaluated"
    assert result.target_id == "target_plane"
    assert result.path is None
    assert any("near_blocker" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    ("field", "element_id", "diagnostic_path"),
    [
        ("target_ref", "missing_target", "receiver.return_path.target_ref"),
        ("scanner_element_id", "missing_mirror", "receiver.return_path.scanner_element_id"),
        ("collimator_element_id", "source", "receiver.return_path.collimator_element_id"),
        ("fiber_element_id", "scan_mirror", "receiver.return_path.fiber_element_id"),
    ],
)
def test_wrong_reciprocal_return_element_ids_are_rejected(
    copied_project: Path,
    field: str,
    element_id: str,
    diagnostic_path: str,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["receiver"]["return_path"][field] = element_id
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as error:
        load_project(copied_project)

    assert any(
        diagnostic.path == diagnostic_path for diagnostic in error.value.diagnostics
    )


def test_reciprocal_report_schema_and_yaml_round_trip(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    payload = build_phase2_optical_train_report(project).to_dict()
    loaded = yaml.safe_load(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    )

    SchemaStore.load(project_root / "schemas").validate(
        loaded,
        "phase2_optical_train_report.schema.json",
        source="round-trip",
    )
    assert loaded["schema_version"] == 2
    assert loaded["reciprocal_return"]["status"] == "pass"
    assert loaded["analytical_checks"]["reciprocal_return"]["status"] == "pass"
    assert loaded["receiver_return"]["power_at_virtual_aperture_w"] > 0.0
