"""Phase 2 optical train report: ABCD lens, aperture clipping과 power ledger."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lidarsim import __version__
from lidarsim.config.immutable import deep_thaw
from lidarsim.optics import ABCDMatrix, OpticalTrainResult, propagate_transmitter_train
from lidarsim.receiver import ReceiverReturn, estimate_receiver_returns
from lidarsim.scene import TargetFootprint, evaluate_target_footprints


Q_PARAMETER_TOLERANCE = 1e-12
ENERGY_LEDGER_TOLERANCE_W = 1e-15


@dataclass(frozen=True, slots=True)
class Phase2OpticalTrainReport:
    manifest: dict[str, Any]
    summary: dict[str, Any]
    accuracy: dict[str, Any]
    model: dict[str, Any]
    optical_train: dict[str, Any]
    target_footprints: tuple[dict[str, Any], ...]
    receiver_return: dict[str, Any]
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
            "target_footprints": deep_thaw(self.target_footprints),
            "receiver_return": deep_thaw(self.receiver_return),
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
        if component.get("model") != "ideal_thin_lens":
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


def _target_footprint_check(footprints: tuple[TargetFootprint, ...]) -> dict[str, Any]:
    hit_count = sum(1 for footprint in footprints if footprint.hit)
    powers = [footprint.estimated_power_on_target_w for footprint in footprints]
    finite = all(math.isfinite(power) and power >= 0.0 for power in powers)
    status = "pass" if hit_count > 0 and finite else "warning" if finite else "fail"
    return {
        "target_count": len(footprints),
        "hit_count": hit_count,
        "max_estimated_power_on_target_w": max(powers, default=0.0),
        "status": status,
        "message": (
            "Rectangle-plane target hit, projected Gaussian footprint와 intercepted power를 검사합니다."
        ),
    }


def _receiver_return_check(returns: tuple[ReceiverReturn, ...]) -> dict[str, Any]:
    powers = [item.estimated_received_power_w for item in returns]
    finite = all(math.isfinite(power) and power >= 0.0 for power in powers)
    positive = any(power > 0.0 for power in powers)
    unsupported = any(item.status.startswith("unsupported") for item in returns)
    status = "fail" if not finite or unsupported else "pass" if positive else "warning"
    return {
        "return_count": len(returns),
        "positive_return_count": sum(1 for power in powers if power > 0.0),
        "total_estimated_received_power_w": sum(powers),
        "status": status,
        "message": "Lambertian small-footprint virtual-aperture power를 검사합니다.",
    }


def _receiver_return_section(returns: tuple[ReceiverReturn, ...]) -> dict[str, Any]:
    items = [item.to_dict() for item in returns]
    total_power = sum(float(item["estimated_received_power_w"]) for item in items)
    total_power_on_target = sum(float(item["estimated_power_on_target_w"]) for item in items)
    link_loss = (
        None
        if total_power <= 0.0 or total_power_on_target <= 0.0
        else -10.0 * math.log10(total_power / total_power_on_target)
    )
    return {
        "model": "lambertian_small_footprint_receiver_aperture",
        "returns": items,
        "total_estimated_received_power_w": total_power,
        "total_estimated_power_on_target_w": total_power_on_target,
        "total_link_loss_db": link_loss,
        "assumptions": [
            "각 target footprint를 독립 small-footprint Lambertian patch로 근사합니다.",
            "estimated_received_power_w는 기존 schema 이름이며 현재는 virtual aperture plane의 값입니다.",
            "동일 scanner/collimator의 역방향 광로와 single-mode fiber mode coupling은 계산하지 않습니다.",
            "Occlusion, BRDF lobe, detector response, coherent sum과 speckle은 계산하지 않습니다.",
        ],
    }


def _accuracy(
    project: Any,
    result: OpticalTrainResult,
    footprints: tuple[TargetFootprint, ...],
    returns: tuple[ReceiverReturn, ...],
) -> dict[str, Any]:
    confidence, hardware, calibration = _readiness(project)
    warnings = [item.format() for item in project.warnings]
    warnings.extend(result.warnings)
    for footprint in footprints:
        warnings.extend(footprint.warnings)
    for receiver_return in returns:
        warnings.extend(receiver_return.warnings)
    warnings.append(
        "현재 receiver return은 analytical virtual aperture 추정값입니다. 동일 scanner mirror와 "
        "collimator의 역방향 traversal, single-mode fiber 결합과 duplexer/detector loss는 아직 "
        "계산하지 않습니다."
    )
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
        "scope": "source_to_static_mirror_rectangle_target_lambertian_virtual_aperture",
        "assumptions": [
            "Source부터 collimator까지는 scalar paraxial Gaussian q-parameter로 계산합니다.",
            "Collimator는 catalog의 ideal_thin_lens, clear aperture와 power_transmission만 사용합니다.",
            "Scanner mirror는 catalog base pose에 static command angle을 적용하고 catalog reflectivity를 사용합니다.",
            "Rectangle-plane target footprint는 projected Gaussian first-order model로 계산합니다.",
            "Receiver return은 Lambertian small-footprint analytical virtual-aperture approximation입니다.",
            "Aperture clipping 뒤 profile shape, diffraction과 edge scattering은 계산하지 않고 power loss만 반영합니다.",
            "Scanner time dynamics, STL hit detection, BRDF/BSDF, detector noise와 coherent FMCW는 계산하지 않습니다.",
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
    footprints = evaluate_target_footprints(project, train.final_state.state)
    receiver_returns = estimate_receiver_returns(project, footprints)
    final_state = train.final_state
    q_check = _q_check(train)
    energy_check = _energy_check(train)
    aperture_check = _aperture_check(train)
    target_check = _target_footprint_check(footprints)
    receiver_check = _receiver_return_check(receiver_returns)
    accuracy = _accuracy(project, train, footprints, receiver_returns)
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    total_loss_db = (
        None
        if train.total_transmission <= 0.0
        else -10.0 * math.log10(train.total_transmission)
    )
    check_statuses = [
        q_check["status"],
        energy_check["status"],
        aperture_check["status"],
        target_check["status"],
        receiver_check["status"],
    ]
    overall_status = (
        "fail"
        if "fail" in check_statuses
        else "warning"
        if (
            accuracy["hardware_readiness"] != "calibrated"
            or train.unsupported_elements
            or "warning" in check_statuses
        )
        else "pass"
    )
    receiver_section = _receiver_return_section(receiver_returns)

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
            "target_hit_count": target_check["hit_count"],
            "estimated_power_on_target_w": target_check["max_estimated_power_on_target_w"],
            "estimated_received_power_w": receiver_section["total_estimated_received_power_w"],
            "link_loss_db": receiver_section["total_link_loss_db"],
            "q_parameter_status": q_check["status"],
            "energy_ledger_status": energy_check["status"],
            "aperture_status": aperture_check["status"],
            "target_footprint_status": target_check["status"],
            "receiver_return_status": receiver_check["status"],
        },
        accuracy=accuracy,
        model={
            "propagation_model": "gaussian_q_abcd_plus_analytical_radiometry",
            "radius_definition": "1/e^2 irradiance radius",
            "validity": (
                "Paraxial scalar Gaussian, ideal centered thin lens, centered apertures, "
                "static flat mirror reflection, rectangle-plane footprint and Lambertian virtual-aperture return"
            ),
            "limitations": [
                "No aberration, diffraction, coating spectral curve, polarization or ghost reflection.",
                "No decenter/tilt tolerance propagation yet.",
                "This Phase 2 report applies one static scanner command angle; use the ideal scanner-path report for forward-line samples.",
                "No scanner motor lag, jitter, bidirectional return stroke or calibration table yet.",
                "No STL mesh hit detection, visibility, occlusion or BVH yet.",
                "No non-Lambertian BRDF/BSDF, roughness, speckle or coherent FMCW yet.",
                "No reciprocal target-to-scanner-to-collimator return train or single-mode fiber coupling yet.",
                "estimated_received_power_w is an analytical virtual-aperture value, not fiber-coupled power.",
                "No detector photocurrent, noise, saturation, FFT or CZT yet.",
                "No measured/vendor black-box optical model execution yet.",
                "Astigmatic post-lens beam with separated x/y waist locations is rejected by the current BeamState contract.",
            ],
        },
        optical_train=train.to_dict(),
        target_footprints=tuple(footprint.to_dict() for footprint in footprints),
        receiver_return=receiver_section,
        analytical_checks={
            "check_scope": "internal_consistency_only",
            "q_parameter": q_check,
            "energy_ledger": energy_check,
            "aperture_fraction": aperture_check,
            "target_footprint": target_check,
            "receiver_return": receiver_check,
            "external_validation_status": "not_evaluated",
        },
    )
