"""Phase 2 optical train report: ABCD lens, aperture clipping과 power ledger."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lidarsim import __version__
from lidarsim.config.immutable import deep_thaw
from lidarsim.optics import ABCDMatrix, OpticalTrainResult, propagate_transmitter_train


Q_PARAMETER_TOLERANCE = 1e-12
ENERGY_LEDGER_TOLERANCE_W = 1e-15


@dataclass(frozen=True, slots=True)
class Phase2OpticalTrainReport:
    manifest: dict[str, Any]
    summary: dict[str, Any]
    accuracy: dict[str, Any]
    model: dict[str, Any]
    optical_train: dict[str, Any]
    analytical_checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "report_type": "phase2_optical_train",
            "manifest": deep_thaw(self.manifest),
            "summary": deep_thaw(self.summary),
            "accuracy": deep_thaw(self.accuracy),
            "model": deep_thaw(self.model),
            "optical_train": deep_thaw(self.optical_train),
            "analytical_checks": deep_thaw(self.analytical_checks),
        }


def _readiness(project: Any) -> tuple[str, str, str]:
    purpose = str(project.active_scenario["model_purpose"])
    confidence = {
        "analytical_regression": "comparative",
        "bench_template": "engineering_estimate",
        "calibrated_hardware": "calibrated",
    }[purpose]
    hardware = {
        "analytical_regression": "analytical_only",
        "bench_template": "bench_template",
        "calibrated_hardware": "calibrated",
    }[purpose]
    calibration = "calibrated" if purpose == "calibrated_hardware" else "uncalibrated"
    return confidence, hardware, calibration


def _q_check(result: OpticalTrainResult) -> dict[str, Any]:
    errors: list[float] = []
    checked_elements = []
    for component in result.component_reports:
        if component["model"] != "ideal_thin_lens":
            continue
        matrix_values = component["abcd_matrix"]
        matrix = ABCDMatrix(
            matrix_values[0][0],
            matrix_values[0][1],
            matrix_values[1][0],
            matrix_values[1][1],
        )
        input_state = component["input_beam_state"]
        output_state = component["output_beam_state"]
        for axis in ("x", "y"):
            q_in = complex(
                float(input_state["distance_from_waist_m"]),
                float(input_state[f"rayleigh_range_{axis}_m"]),
            )
            q_expected = matrix.apply_q(q_in)
            q_actual = complex(
                float(output_state["distance_from_waist_m"]),
                float(output_state[f"rayleigh_range_{axis}_m"]),
            )
            scale = max(abs(q_expected), 1.0)
            errors.append(abs(q_expected - q_actual) / scale)
        checked_elements.append(str(component["element_id"]))
    max_error = max(errors, default=0.0)
    return {
        "checked_elements": checked_elements,
        "max_relative_error": max_error,
        "tolerance": Q_PARAMETER_TOLERANCE,
        "status": "pass" if max_error <= Q_PARAMETER_TOLERANCE else "fail",
        "message": "Thin-lens output q-parameter가 ABCD 분석식과 일치하는지 확인합니다.",
    }


def _energy_check(result: OpticalTrainResult) -> dict[str, Any]:
    residuals: list[float] = []
    previous_output = None
    for entry in result.power_ledger:
        if previous_output is not None:
            residuals.append(abs(entry.input_power_w - previous_output))
        residuals.append(abs(entry.input_power_w - entry.loss_w - entry.output_power_w))
        previous_output = entry.output_power_w
    residual = max(residuals, default=0.0)
    return {
        "max_power_residual_w": residual,
        "tolerance_w": ENERGY_LEDGER_TOLERANCE_W,
        "status": "pass" if residual <= ENERGY_LEDGER_TOLERANCE_W else "fail",
        "message": "각 power ledger entry의 input - loss = output 관계를 검사합니다.",
    }


def _aperture_check(result: OpticalTrainResult) -> dict[str, Any]:
    fractions = [
        float(report["aperture_clip"]["transmission_fraction"])
        for report in result.component_reports
        if "aperture_clip" in report
    ]
    valid = all(0.0 <= value <= 1.0 for value in fractions)
    return {
        "checked_apertures": len(fractions),
        "minimum_transmission_fraction": min(fractions) if fractions else None,
        "status": "pass" if valid else "fail",
        "message": "Aperture clipping fraction이 물리 범위 [0, 1] 안에 있는지 확인합니다.",
    }


def _accuracy(project: Any, result: OpticalTrainResult) -> dict[str, Any]:
    confidence, hardware, calibration = _readiness(project)
    warnings = [item.format() for item in project.warnings]
    warnings.extend(result.warnings)
    if result.unsupported_elements:
        warnings.append(
            "Scanner/mirror 이후 propagation은 아직 계산하지 않고 unsupported_elements에 기록합니다."
        )
    return {
        "model_purpose": str(project.active_scenario["model_purpose"]),
        "accuracy_mode": str(project.active_scenario["simulation"]["accuracy_mode"]),
        "hardware_readiness": hardware,
        "confidence_level": confidence,
        "calibration_status": calibration,
        "scope": "source_to_ideal_thin_lens_collimator_and_scanner_input",
        "assumptions": [
            "Source부터 collimator까지는 scalar paraxial Gaussian q-parameter로 계산합니다.",
            "Collimator는 catalog의 ideal_thin_lens, clear aperture와 power_transmission만 사용합니다.",
            "Aperture clipping 뒤 profile shape와 diffraction은 계산하지 않고 power loss만 반영합니다.",
            "Mirror reflection, scanner motion, target footprint와 receiver return은 후속 Phase에서 계산합니다.",
        ],
        "warnings": warnings,
    }


def build_phase2_optical_train_report(
    project: Any,
    result: OpticalTrainResult | None = None,
    *,
    created_at: datetime | None = None,
) -> Phase2OpticalTrainReport:
    """Phase 2 first vertical-slice train report를 만든다."""

    train = result or propagate_transmitter_train(project)
    final_state = train.final_state
    q_check = _q_check(train)
    energy_check = _energy_check(train)
    aperture_check = _aperture_check(train)
    accuracy = _accuracy(project, train)
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    total_loss_db = (
        None
        if train.total_transmission <= 0.0
        else -10.0 * math.log10(train.total_transmission)
    )
    check_statuses = [q_check["status"], energy_check["status"], aperture_check["status"]]
    overall_status = (
        "fail"
        if "fail" in check_statuses
        else "warning"
        if accuracy["hardware_readiness"] != "calibrated" or train.unsupported_elements
        else "pass"
    )

    return Phase2OpticalTrainReport(
        manifest={
            "project_id": str(project.project["project_id"]),
            "scenario_id": str(project.active_scenario["scenario_id"]),
            "config_hash": project.config_hash,
            "created_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
            "software_version": __version__,
            "backend": "numpy",
            "real_dtype": "float64",
        },
        summary={
            "overall_status": overall_status,
            "optical_path_id": train.optical_path_id,
            "final_plane": final_state.label,
            "final_radius_x_m": final_state.state.radius_x_m,
            "final_radius_y_m": final_state.state.radius_y_m,
            "final_power_w": final_state.state.power_w,
            "total_transmission": train.total_transmission,
            "total_loss_w": train.total_loss_w,
            "total_loss_db": total_loss_db,
            "processed_component_count": len(train.component_reports),
            "unsupported_element_count": len(train.unsupported_elements),
            "q_parameter_status": q_check["status"],
            "energy_ledger_status": energy_check["status"],
            "aperture_status": aperture_check["status"],
        },
        accuracy=accuracy,
        model={
            "propagation_model": "gaussian_q_abcd",
            "radius_definition": "1/e^2 irradiance radius",
            "validity": "Paraxial scalar Gaussian, ideal centered thin lens and centered circular aperture",
            "limitations": [
                "No aberration, diffraction, coating spectral curve or ghost reflection.",
                "No decenter/tilt tolerance propagation yet.",
                "No measured/vendor black-box optical model execution yet.",
                "Astigmatic post-lens beam with separated x/y waist locations is rejected by the current BeamState contract.",
            ],
        },
        optical_train=train.to_dict(),
        analytical_checks={
            "check_scope": "internal_consistency_only",
            "q_parameter": q_check,
            "energy_ledger": energy_check,
            "aperture_fraction": aperture_check,
            "external_validation_status": "not_evaluated",
        },
    )
