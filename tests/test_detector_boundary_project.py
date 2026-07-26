from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math
from pathlib import Path

import pytest
import yaml

import lidarsim.results.optical_train as optical_train_results
from lidarsim.config import load_project
from lidarsim.config.physical import IMPLEMENTED_OUTPUTS
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigValidationError
from lidarsim.optics import propagate_transmitter_train
from lidarsim.receiver import (
    evaluate_project_detector_boundary,
    evaluate_project_fiber_coupling,
    evaluate_project_reciprocal_return,
    evaluate_project_reciprocal_return_power,
)
from lidarsim.scene import evaluate_target_footprints
from lidarsim.results import build_phase2_optical_train_report


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _scenario(copied_project: Path) -> tuple[Path, dict]:
    path = copied_project.parent / "baseline_1550nm.yaml"
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def _pipeline(project):
    train = propagate_transmitter_train(project)
    footprints = evaluate_target_footprints(project, train.final_state.state)
    geometry = evaluate_project_reciprocal_return(project, train, footprints)
    power = evaluate_project_reciprocal_return_power(project, footprints, geometry)
    coupling = evaluate_project_fiber_coupling(project, geometry, power)
    target_power = None if power.result is None else power.result.power_on_target_w
    boundary = evaluate_project_detector_boundary(
        project,
        coupling,
        power_on_target_w=target_power,
    )
    return power, coupling, boundary


def test_baseline_r4_preserves_r3_power_at_unity_duplexer(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    power, coupling, boundary = _pipeline(project)

    assert power.result is not None
    assert coupling.result is not None
    assert boundary.result is not None
    assert boundary.status == "pass"
    assert boundary.result.power_at_detector_input_w == pytest.approx(
        1.8006278445836738e-9
    )
    assert boundary.result.power_at_detector_input_w == pytest.approx(
        coupling.result.power_coupled_into_fiber_w
    )
    assert boundary.fiber_coupled_to_detector_input_link_loss_db == pytest.approx(0.0)
    assert boundary.target_to_detector_input_link_loss_db == pytest.approx(
        67.44574883534182
    )
    assert boundary.source_to_detector_input_round_trip_link_loss_db == pytest.approx(
        67.44576038288172
    )
    assert boundary.energy_check_status == "pass"
    assert boundary.coherent_field_status == "not_provided"
    assert boundary.field_usable_for_coherent_propagation is False
    assert boundary.result.field_at_fiber_output_sqrt_w is None
    assert boundary.result.field_at_detector_input_sqrt_w is None
    assert "detector_input_power" in IMPLEMENTED_OUTPUTS
    architecture_warning = next(
        warning
        for warning in project.warnings
        if warning.path == "receiver.architecture"
    )
    assert "detector optical input boundary" in architecture_warning.message
    assert "Detector response" in architecture_warning.message


def test_quarter_duplexer_transmission_scales_power_and_losses(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["duplexer"]["return_power_transmission"] = 0.25
    _write_yaml(scenario_path, scenario)

    project = load_project(copied_project)
    _, coupling, boundary = _pipeline(project)

    assert coupling.result is not None
    assert boundary.result is not None
    expected_loss_db = -10.0 * math.log10(0.25)
    assert boundary.result.power_at_detector_input_w == pytest.approx(
        0.25 * coupling.result.power_coupled_into_fiber_w
    )
    assert boundary.fiber_coupled_to_detector_input_link_loss_db == pytest.approx(
        expected_loss_db
    )
    assert boundary.target_to_detector_input_link_loss_db == pytest.approx(
        coupling.target_to_fiber_coupled_link_loss_db + expected_loss_db
    )
    assert boundary.source_to_detector_input_round_trip_link_loss_db == pytest.approx(
        67.44576038288172 + expected_loss_db
    )
    assert boundary.result.power_ledger[0].transmission_fraction == pytest.approx(
        0.25
    )
    report = build_phase2_optical_train_report(project)
    assert report.summary["power_at_detector_input_w"] == pytest.approx(
        boundary.result.power_at_detector_input_w
    )
    assert report.summary[
        "fiber_coupled_to_detector_input_link_loss_db"
    ] == pytest.approx(expected_loss_db)


def test_zero_duplexer_transmission_is_explicitly_blocked(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["duplexer"]["return_power_transmission"] = 0.0
    _write_yaml(scenario_path, scenario)

    project = load_project(copied_project)
    _, _, boundary = _pipeline(project)

    assert boundary.result is not None
    assert boundary.status == "blocked"
    assert boundary.result.power_at_detector_input_w == 0.0
    assert boundary.fiber_coupled_to_detector_input_link_loss_db is None
    assert boundary.target_to_detector_input_link_loss_db is None
    assert boundary.source_to_detector_input_round_trip_link_loss_db is None
    assert boundary.result.power_ledger[0].status == "blocked"
    report = build_phase2_optical_train_report(project)
    assert report.summary["detector_input_status"] == "blocked"
    assert report.summary["power_at_detector_input_w"] == 0.0
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="blocked R4 Phase 2 v6 report",
    )


def test_missing_r3_result_leaves_detector_boundary_not_evaluated(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    power, coupling, _ = _pipeline(project)
    missing = replace(
        coupling,
        status="not_evaluated",
        status_reason="forced missing R3 result",
        result=None,
        power_ledger=(),
        maximum_energy_residual_w=None,
        energy_check_status="not_evaluated",
    )

    boundary = evaluate_project_detector_boundary(
        project,
        missing,
        power_on_target_w=power.result.power_on_target_w,
    )

    assert boundary.status == "not_evaluated"
    assert boundary.result is None
    assert boundary.power_at_detector_input_w is None
    assert boundary.power_ledger == ()


def test_failed_r3_result_fails_without_propagating_power(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    power, coupling, _ = _pipeline(project)
    failed = replace(
        coupling,
        status="fail",
        status_reason="forced R3 energy regression",
        result=None,
        power_ledger=(),
        maximum_energy_residual_w=None,
        energy_check_status="fail",
    )

    boundary = evaluate_project_detector_boundary(
        project,
        failed,
        power_on_target_w=power.result.power_on_target_w,
    )

    assert boundary.status == "fail"
    assert boundary.result is None
    assert boundary.energy_check_status == "not_evaluated"
    assert boundary.power_at_detector_input_w is None


def test_r3_power_above_current_project_source_fails_passive_gate(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    power, coupling, _ = _pipeline(project)
    assert coupling.result is not None
    excessive = replace(
        coupling,
        result=replace(
            coupling.result,
            power_coupled_into_fiber_w=0.02,
        ),
    )

    boundary = evaluate_project_detector_boundary(
        project,
        excessive,
        power_on_target_w=power.result.power_on_target_w,
    )

    assert boundary.status == "fail"
    assert boundary.result is None
    assert boundary.power_at_detector_input_w is None
    assert "수동 power bound" in boundary.status_reason


def test_positive_r3_power_cannot_be_reused_with_zero_source_project(
    copied_project: Path,
    project_root: Path,
) -> None:
    baseline_project = load_project(project_root / "configs" / "project.yaml")
    power, coupling, _ = _pipeline(baseline_project)
    scenario_path, scenario = _scenario(copied_project)
    scenario["source"]["optical_power_w"] = "0 W"
    _write_yaml(scenario_path, scenario)
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "baseline_fiber_source.yaml"
    )
    component = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    component["optical"]["optical_power_w"] = "0 W"
    _write_yaml(component_path, component)

    boundary = evaluate_project_detector_boundary(
        load_project(copied_project),
        coupling,
        power_on_target_w=power.result.power_on_target_w,
    )

    assert coupling.result is not None
    assert coupling.result.power_coupled_into_fiber_w > 0.0
    assert boundary.status == "fail"
    assert boundary.result is None
    assert boundary.power_at_detector_input_w is None


def test_tiny_source_passive_gate_does_not_use_energy_residual_tolerance(
    copied_project: Path,
    project_root: Path,
) -> None:
    baseline_project = load_project(project_root / "configs" / "project.yaml")
    power, coupling, _ = _pipeline(baseline_project)
    assert coupling.result is not None
    tiny_positive = replace(
        coupling,
        result=replace(
            coupling.result,
            power_coupled_into_fiber_w=5.0e-16,
        ),
    )
    scenario_path, scenario = _scenario(copied_project)
    scenario["source"]["optical_power_w"] = "1e-18 W"
    _write_yaml(scenario_path, scenario)
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "baseline_fiber_source.yaml"
    )
    component = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    component["optical"]["optical_power_w"] = "1e-18 W"
    _write_yaml(component_path, component)

    boundary = evaluate_project_detector_boundary(
        load_project(copied_project),
        tiny_positive,
        power_on_target_w=power.result.power_on_target_w,
        energy_tolerance_w=1.0e-15,
    )

    assert tiny_positive.result.power_coupled_into_fiber_w < 1.0e-15
    assert boundary.status == "fail"
    assert boundary.result is None


def test_valid_zero_r3_power_remains_valid_zero_input(copied_project: Path) -> None:
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

    _, coupling, boundary = _pipeline(load_project(copied_project))

    assert coupling.result is not None
    assert coupling.result.power_coupled_into_fiber_w == 0.0
    assert boundary.result is not None
    assert boundary.status == "zero_input"
    assert boundary.result.power_at_detector_input_w == 0.0
    assert boundary.result.power_ledger[0].status == "zero_input"
    assert boundary.energy_check_status == "pass"


def test_null_detector_model_is_canonicalized_to_none(copied_project: Path) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["detector_model"] = None
    _write_yaml(scenario_path, scenario)

    _, _, boundary = _pipeline(load_project(copied_project))

    assert boundary.detector_model == "none"
    assert boundary.result is not None
    assert boundary.result.detector_model == "none"
    assert boundary.to_dict()["detector_model"] == "none"


def test_empty_detector_model_is_rejected_by_config_schema(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["receiver"]["detector_model"] = ""
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError, match="non-empty"):
        load_project(copied_project)


def test_nonreciprocal_architecture_without_duplexer_is_not_evaluated(
    copied_project: Path,
    project_root: Path,
) -> None:
    reciprocal_project = load_project(project_root / "configs" / "project.yaml")
    _, coupling, _ = _pipeline(reciprocal_project)
    scenario_path, scenario = _scenario(copied_project)
    receiver = scenario["receiver"]
    receiver["architecture"] = "virtual_monostatic"
    receiver["model_level"] = "virtual_aperture"
    receiver.pop("return_path")
    receiver.pop("fiber_coupling")
    receiver.pop("duplexer")
    _write_yaml(scenario_path, scenario)

    boundary = evaluate_project_detector_boundary(
        load_project(copied_project),
        coupling,
    )

    assert boundary.status == "not_evaluated"
    assert boundary.result is None
    assert boundary.duplexer_type is None
    assert boundary.return_power_transmission is None


def test_r4_project_payload_never_invents_a_coherent_field(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    _, _, boundary = _pipeline(project)
    payload = boundary.to_dict()

    assert payload["field_at_fiber_output_sqrt_w"] is None
    assert payload["field_at_detector_input_sqrt_w"] is None
    assert payload["coherent_field_status"] == "not_provided"
    assert payload["field_usable_for_coherent_propagation"] is False
    assert payload["model_scope"] == "analytical_optical_boundary_only"
    assert payload["hardware_readiness"] == "uncalibrated"
    assert payload["detector_response_status"] == "not_evaluated"


def test_phase2_v6_detector_boundary_schema_yaml_round_trip(
    project_root: Path,
) -> None:
    report = build_phase2_optical_train_report(
        load_project(project_root / "configs" / "project.yaml")
    )
    payload = yaml.safe_load(
        yaml.safe_dump(report.to_dict(), sort_keys=False, allow_unicode=True)
    )

    SchemaStore.load(project_root / "schemas").validate(
        payload,
        "phase2_optical_train_report.schema.json",
        source="R4 Phase 2 v6 round-trip",
    )
    summary = payload["summary"]
    boundary = payload["reciprocal_return"]["detector_boundary"]
    assert payload["schema_version"] == 6
    assert summary["detector_input_status"] == "pass"
    assert summary["power_at_detector_input_w"] == pytest.approx(
        1.8006278445836738e-9
    )
    assert summary[
        "fiber_coupled_to_detector_input_link_loss_db"
    ] == pytest.approx(0.0)
    assert summary["target_to_detector_input_link_loss_db"] == pytest.approx(
        67.44574883534182
    )
    assert summary[
        "source_to_detector_input_round_trip_link_loss_db"
    ] == pytest.approx(67.44576038288172)
    assert payload["reciprocal_return"]["detector_status"] == "pass"
    assert boundary["power_at_detector_input_w"] == pytest.approx(
        summary["power_at_detector_input_w"]
    )
    assert boundary["field_at_detector_input_sqrt_w"] is None
    assert payload["analytical_checks"]["detector_boundary"]["status"] == "pass"


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("reciprocal_return", "detector_boundary"), None),
        (
            (
                "reciprocal_return",
                "detector_boundary",
                "power_at_detector_input_w",
            ),
            None,
        ),
        (("reciprocal_return", "detector_boundary", "power_ledger"), []),
        (
            (
                "reciprocal_return",
                "detector_boundary",
                "maximum_energy_residual_w",
            ),
            None,
        ),
        (("summary", "power_at_detector_input_w"), None),
    ],
)
def test_v6_schema_rejects_pass_detector_boundary_with_missing_result_contract(
    project_root: Path,
    path: tuple[str, ...],
    invalid_value,
) -> None:
    payload = build_phase2_optical_train_report(
        load_project(project_root / "configs" / "project.yaml")
    ).to_dict()
    mutated = deepcopy(payload)
    owner = mutated
    for key in path[:-1]:
        owner = owner[key]
    owner[path[-1]] = invalid_value

    with pytest.raises(ConfigValidationError):
        SchemaStore.load(project_root / "schemas").validate(
            mutated,
            "phase2_optical_train_report.schema.json",
            source="mutated R4 Phase 2 v6 report",
        )


@pytest.mark.parametrize(
    ("outer_status", "nested_status"),
    [
        ("not_evaluated", "pass"),
        ("blocked", "pass"),
        ("pass", "zero_input"),
    ],
)
def test_v6_schema_rejects_outer_and_nested_detector_status_mismatch(
    project_root: Path,
    outer_status: str,
    nested_status: str,
) -> None:
    payload = build_phase2_optical_train_report(
        load_project(project_root / "configs" / "project.yaml")
    ).to_dict()
    payload["reciprocal_return"]["detector_status"] = outer_status
    payload["reciprocal_return"]["detector_boundary"]["status"] = nested_status

    with pytest.raises(ConfigValidationError):
        SchemaStore.load(project_root / "schemas").validate(
            payload,
            "phase2_optical_train_report.schema.json",
            source="mismatched R4 Phase 2 v6 report",
        )


def test_v6_schema_rejects_summary_and_reciprocal_detector_status_mismatch(
    project_root: Path,
) -> None:
    payload = build_phase2_optical_train_report(
        load_project(project_root / "configs" / "project.yaml")
    ).to_dict()
    payload["summary"]["detector_input_status"] = "blocked"
    payload["summary"]["power_at_detector_input_w"] = 0.0
    payload["summary"]["fiber_coupled_to_detector_input_link_loss_db"] = None
    payload["summary"]["target_to_detector_input_link_loss_db"] = None
    payload["summary"][
        "source_to_detector_input_round_trip_link_loss_db"
    ] = None

    with pytest.raises(ConfigValidationError):
        SchemaStore.load(project_root / "schemas").validate(
            payload,
            "phase2_optical_train_report.schema.json",
            source="summary-mismatched R4 Phase 2 v6 report",
        )


def test_zero_source_power_round_trips_r4_as_valid_zero_input(
    copied_project: Path,
) -> None:
    scenario_path, scenario = _scenario(copied_project)
    scenario["source"]["optical_power_w"] = "0 W"
    _write_yaml(scenario_path, scenario)
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "baseline_fiber_source.yaml"
    )
    component = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    component["optical"]["optical_power_w"] = "0 W"
    _write_yaml(component_path, component)

    report = build_phase2_optical_train_report(load_project(copied_project))
    payload = report.to_dict()

    assert payload["summary"]["detector_input_status"] == "zero_input"
    assert payload["summary"]["power_at_detector_input_w"] == 0.0
    assert payload["summary"][
        "source_to_detector_input_round_trip_link_loss_db"
    ] is None
    assert payload["reciprocal_return"]["detector_boundary"][
        "source_power_w"
    ] == 0.0
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        payload,
        "phase2_optical_train_report.schema.json",
        source="zero-source R4 Phase 2 v6 report",
    )


def test_report_propagates_r3_fail_into_r4_and_overall_status(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    _, coupling, _ = _pipeline(project)
    failed = replace(
        coupling,
        status="fail",
        status_reason="forced R3 energy regression",
        result=None,
        power_ledger=(),
        maximum_energy_residual_w=None,
        energy_check_status="fail",
    )
    monkeypatch.setattr(
        optical_train_results,
        "evaluate_project_fiber_coupling",
        lambda *_args, **_kwargs: failed,
    )

    report = build_phase2_optical_train_report(project)

    assert report.summary["detector_input_status"] == "fail"
    assert report.summary["power_at_detector_input_w"] is None
    assert report.reciprocal_return["detector_status"] == "fail"
    assert report.reciprocal_return["detector_boundary"][
        "power_at_detector_input_w"
    ] is None
    assert report.analytical_checks["detector_boundary"]["status"] == "fail"
    assert report.summary["overall_status"] == "fail"
    SchemaStore.load(project_root / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="R3-failed R4 Phase 2 v6 report",
    )


def test_report_serializes_missing_r3_as_null_detector_boundary(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    _, coupling, _ = _pipeline(project)
    missing = replace(
        coupling,
        status="not_evaluated",
        status_reason="forced missing R3",
        result=None,
        power_ledger=(),
        maximum_energy_residual_w=None,
        energy_check_status="not_evaluated",
    )
    monkeypatch.setattr(
        optical_train_results,
        "evaluate_project_fiber_coupling",
        lambda *_args, **_kwargs: missing,
    )

    report = build_phase2_optical_train_report(project)

    assert report.summary["detector_input_status"] == "not_evaluated"
    assert report.summary["power_at_detector_input_w"] is None
    assert report.reciprocal_return["detector_status"] == "not_evaluated"
    assert report.reciprocal_return["detector_boundary"] is None
    assert report.analytical_checks["detector_boundary"]["status"] == "not_evaluated"
    SchemaStore.load(project_root / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="R3-missing R4 Phase 2 v6 report",
    )
