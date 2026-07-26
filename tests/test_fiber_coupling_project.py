from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

import lidarsim.results.optical_train as optical_train_results
from lidarsim.config import load_project
from lidarsim.config.physical import IMPLEMENTED_OUTPUTS
from lidarsim.config.schema import SchemaStore
from lidarsim.optics import propagate_transmitter_train
from lidarsim.receiver import (
    evaluate_project_fiber_coupling,
    evaluate_project_reciprocal_return,
    evaluate_project_reciprocal_return_power,
)
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.scene import evaluate_target_footprints


def _pipeline(project):
    train = propagate_transmitter_train(project)
    footprints = evaluate_target_footprints(project, train.final_state.state)
    geometry = evaluate_project_reciprocal_return(project, train, footprints)
    power = evaluate_project_reciprocal_return_power(project, footprints, geometry)
    coupling = evaluate_project_fiber_coupling(project, geometry, power)
    return geometry, power, coupling


def _scenario(copied_project: Path) -> tuple[Path, dict]:
    path = copied_project.parent / "baseline_1550nm.yaml"
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def test_baseline_r3_is_unit_efficiency_power_upper_bound(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    _, power, coupling = _pipeline(project)

    assert power.result is not None
    assert coupling.status == "pass"
    assert coupling.result is not None
    assert coupling.result.available_power_at_fiber_plane_w == pytest.approx(
        power.result.power_at_fiber_plane_w
    )
    assert coupling.result.fiber_coupling_efficiency == pytest.approx(1.0)
    assert coupling.result.power_coupled_into_fiber_w == pytest.approx(
        power.result.power_at_fiber_plane_w
    )
    assert coupling.fiber_plane_to_coupled_mode_loss_db == pytest.approx(0.0)
    assert coupling.target_to_fiber_coupled_link_loss_db == pytest.approx(
        67.44574883534182
    )
    assert coupling.coherent_field_status == "not_provided"
    assert coupling.result.coupled_field_amplitude_sqrt_w is None
    assert coupling.field_usable_for_coherent_propagation is False
    assert coupling.energy_check_status == "pass"
    assert coupling.maximum_energy_residual_w == pytest.approx(0.0, abs=1.0e-24)
    assert len(coupling.power_ledger) == 1
    entry = coupling.power_ledger[0]
    assert entry.input_power_w - entry.coupling_loss_w == pytest.approx(
        entry.output_power_w,
        abs=1.0e-24,
    )
    payload = coupling.to_dict()
    assert payload["input_power_interpretation"] == (
        "entire_r2_lambertian_scalar_power_assumed_carried_by_proxy_gaussian_mode"
    )
    assert any("upper-bound" in warning for warning in coupling.warnings)
    assert "fiber_coupling" in IMPLEMENTED_OUTPUTS


@pytest.mark.parametrize(
    ("axis_index", "lateral_m", "angle_rad"),
    [(0, 2.0e-6, 2.0e-3), (1, -3.0e-6, -3.0e-3)],
)
def test_r1_x_y_residuals_are_resolved_in_receive_frame_without_scalar_copy(
    project_root: Path,
    axis_index: int,
    lateral_m: float,
    angle_rad: float,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    geometry, power, _ = _pipeline(project)
    assert geometry.path is not None
    assert geometry.path.fiber_hit is not None
    path = geometry.path
    fiber_hit = path.fiber_hit
    frame = fiber_hit.frame
    receive_axis = -frame.normal
    receive_x = frame.x_axis
    receive_y = np.cross(receive_axis, receive_x)
    axis = receive_x if axis_index == 0 else receive_y
    point = np.array(frame.origin_m + lateral_m * axis, dtype=np.float64)
    point.setflags(write=False)
    intersection = replace(fiber_hit.intersection, point_m=point)
    shifted_hit = replace(fiber_hit, intersection=intersection)
    direction = np.asarray(receive_axis + math_tan(angle_rad) * axis, dtype=np.float64)
    direction /= np.linalg.norm(direction)
    direction.setflags(write=False)
    modified_geometry = replace(
        geometry,
        path=replace(
            path,
            fiber_hit=shifted_hit,
            fiber_bound_direction=direction,
        ),
    )

    coupling = evaluate_project_fiber_coupling(
        project,
        modified_geometry,
        power,
    )

    assert coupling.result is not None
    assert coupling.r1_lateral_offset_m is not None
    assert coupling.r1_angular_offset_rad is not None
    other = 1 - axis_index
    assert coupling.r1_lateral_offset_m[axis_index] == pytest.approx(lateral_m)
    assert coupling.r1_lateral_offset_m[other] == pytest.approx(0.0, abs=1.0e-15)
    assert coupling.r1_angular_offset_rad[axis_index] == pytest.approx(angle_rad)
    assert coupling.r1_angular_offset_rad[other] == pytest.approx(0.0, abs=1.0e-15)
    assert coupling.result.fiber_coupling_efficiency < 1.0


def math_tan(value: float) -> float:
    # A tiny helper keeps the analytical test direction construction explicit.
    import math

    return math.tan(value)


def test_configured_offsets_add_componentwise_in_same_receive_frame(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    config = scenario["receiver"]["fiber_coupling"]
    config["lateral_offset_m"] = [2.0e-6, -3.0e-6]
    config["angular_offset_rad"] = [2.0e-3, -3.0e-3]
    _write_yaml(scenario_path, scenario)

    _, _, coupling = _pipeline(load_project(copied_project))

    assert coupling.configured_lateral_offset_m == pytest.approx((2.0e-6, -3.0e-6))
    assert coupling.configured_angular_offset_rad == pytest.approx((2.0e-3, -3.0e-3))
    assert coupling.combined_lateral_offset_m is not None
    assert coupling.combined_angular_offset_rad is not None
    assert coupling.combined_lateral_offset_m == pytest.approx((2.0e-6, -3.0e-6), abs=1e-15)
    assert coupling.combined_angular_offset_rad == pytest.approx((2.0e-3, -3.0e-3), abs=1e-14)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receive_mode_field_diameter_m", "20 um"),
        ("receive_mode_waist_offset_m", "50 um"),
    ],
)
def test_receive_mode_size_and_focus_mismatch_reduce_efficiency(
    copied_project: Path,
    field: str,
    value: str,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["fiber_coupling"][field] = value
    _write_yaml(scenario_path, scenario)

    report = build_phase2_optical_train_report(load_project(copied_project))

    efficiency = report.summary["fiber_coupling_efficiency"]
    assert efficiency is not None
    assert 0.0 < efficiency < 1.0
    assert report.summary["power_coupled_into_fiber_w"] < report.summary["power_at_fiber_plane_w"]


def test_unsupported_receive_mfd_definition_is_structured_and_nullable(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["fiber_coupling"][
        "receive_mode_field_diameter_definition"
    ] = "petermann_ii"
    _write_yaml(scenario_path, scenario)

    report = build_phase2_optical_train_report(load_project(copied_project))
    section = report.reciprocal_return["fiber_coupling"]

    assert report.reciprocal_return["fiber_coupling_status"] == "unsupported_mfd_definition"
    assert section is not None
    assert section["status"] == "unsupported_mfd_definition"
    assert section["fiber_coupling_efficiency"] is None
    assert section["power_coupled_into_fiber_w"] is None
    assert report.summary["fiber_coupling_efficiency"] is None
    assert report.summary["power_coupled_into_fiber_w"] is None
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="unsupported R3 MFD report",
    )


def test_missing_r2_result_keeps_r3_not_evaluated_and_null(
    copied_project: Path,
) -> None:
    material_path = (
        copied_project.parent.parent
        / "catalog"
        / "materials"
        / "custom"
        / "diffuse_gray_020.yaml"
    )
    material = yaml.safe_load(material_path.read_text(encoding="utf-8"))
    material["optical"]["model"] = "unsupported_test_brdf"
    _write_yaml(material_path, material)

    report = build_phase2_optical_train_report(load_project(copied_project))

    assert report.reciprocal_return["power_status"] == "unsupported_material"
    assert report.reciprocal_return["fiber_coupling_status"] == "not_evaluated"
    assert report.reciprocal_return["fiber_coupling"] is None
    assert report.summary["fiber_coupling_efficiency"] is None
    assert report.summary["power_coupled_into_fiber_w"] is None


def test_zero_r2_power_reports_zero_coupled_power_without_coherent_field(
    copied_project: Path,
) -> None:
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "ideal_collimator_f20.yaml"
    )
    component = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    component["optical"]["power_transmission"] = 0.0
    _write_yaml(component_path, component)

    report = build_phase2_optical_train_report(load_project(copied_project))
    section = report.reciprocal_return["fiber_coupling"]

    assert report.reciprocal_return["power_status"] == "zero_power"
    assert report.reciprocal_return["fiber_coupling_status"] == "zero_available_power"
    assert section is not None
    assert section["fiber_coupling_efficiency"] == pytest.approx(1.0)
    assert section["power_coupled_into_fiber_w"] == 0.0
    assert section["coupled_field_amplitude_sqrt_w"] is None
    assert section["coherent_field_status"] == "not_provided"


def test_failed_r2_energy_check_is_not_propagated_into_r3(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    geometry, power, _ = _pipeline(project)
    assert power.result is not None
    invalid_power = replace(
        power,
        status="fail",
        status_reason="forced upstream energy regression",
        result=replace(power.result, energy_check_status="fail"),
    )

    coupling = evaluate_project_fiber_coupling(project, geometry, invalid_power)

    assert coupling.status == "fail"
    assert coupling.result is None
    assert coupling.energy_check_status == "not_evaluated"
    assert coupling.power_ledger == ()
    assert any("R2 return power ledger" in warning for warning in coupling.warnings)

    monkeypatch.setattr(
        optical_train_results,
        "evaluate_project_reciprocal_return_power",
        lambda *_args, **_kwargs: invalid_power,
    )
    report = build_phase2_optical_train_report(project)

    assert report.reciprocal_return["fiber_coupling_status"] == "fail"
    assert (
        report.reciprocal_return["fiber_coupling"][
            "available_power_at_fiber_plane_w"
        ]
        is None
    )
    assert report.reciprocal_return["fiber_coupling"]["power_ledger"] == []
    assert report.analytical_checks["fiber_coupling"]["status"] == "fail"
    assert report.summary["overall_status"] == "fail"


def test_legacy_single_mode_overlap_name_is_accepted_with_warning(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["fiber_coupling"]["model"] = "single_mode_overlap"
    _write_yaml(scenario_path, scenario)

    project = load_project(copied_project)
    report = build_phase2_optical_train_report(project)

    assert any(
        warning.path == "receiver.fiber_coupling.model"
        and "Legacy single_mode_overlap" in warning.message
        for warning in project.warnings
    )
    assert report.reciprocal_return["fiber_coupling_status"] == "pass"


def test_phase2_v5_fiber_coupling_schema_round_trip(project_root: Path) -> None:
    report = build_phase2_optical_train_report(
        load_project(project_root / "configs" / "project.yaml")
    )
    payload = yaml.safe_load(
        yaml.safe_dump(report.to_dict(), sort_keys=False, allow_unicode=True)
    )

    SchemaStore.load(project_root / "schemas").validate(
        payload,
        "phase2_optical_train_report.schema.json",
        source="R3 Phase 2 v5 round-trip",
    )
    assert payload["schema_version"] == 5
    assert payload["summary"]["fiber_coupling_efficiency"] == pytest.approx(1.0)
    assert payload["analytical_checks"]["fiber_coupling"]["status"] == "pass"
