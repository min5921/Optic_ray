"""Phase 1 Gaussian beam propagation, confidence와 convergence report."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lidarsim import __version__
from lidarsim.beam import BeamState, build_source_beam
from lidarsim.config.immutable import deep_thaw
from lidarsim.results.accuracy import assess_readiness


POWER_TOLERANCE = 1e-3
GRID_CONVERGENCE_TOLERANCE = 1e-3
INTERNAL_CONSISTENCY_TOLERANCE = 1e-12
PARAXIAL_PROXY_TOLERANCE = 1e-3


@dataclass(frozen=True, slots=True)
class BeamSample:
    distance_m: float
    radius_x_m: float
    radius_y_m: float
    q_x_real_m: float
    q_x_imag_m: float
    q_y_real_m: float
    q_y_imag_m: float
    power_w: float


@dataclass(frozen=True, slots=True)
class Phase1BeamReport:
    manifest: dict[str, Any]
    summary: dict[str, Any]
    accuracy: dict[str, Any]
    model: dict[str, Any]
    source_state: dict[str, Any]
    propagation: dict[str, Any]
    profile_audit: dict[str, Any]
    analytical_checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "report_type": "phase1_beam",
            "manifest": deep_thaw(self.manifest),
            "summary": deep_thaw(self.summary),
            "accuracy": deep_thaw(self.accuracy),
            "model": deep_thaw(self.model),
            "source_state": deep_thaw(self.source_state),
            "propagation": deep_thaw(self.propagation),
            "profile_audit": deep_thaw(self.profile_audit),
            "analytical_checks": deep_thaw(self.analytical_checks),
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """사람이 빠르게 읽을 수 있는 compact result를 반환한다."""

        return {
            "schema_version": 1,
            "report_type": "phase1_beam_summary",
            "manifest": {
                "project_id": self.manifest["project_id"],
                "scenario_id": self.manifest["scenario_id"],
                "config_hash": self.manifest["config_hash"],
                "created_at_utc": self.manifest["created_at_utc"],
            },
            "summary": deep_thaw(self.summary),
            "accuracy": {
                "model_purpose": self.accuracy["model_purpose"],
                "hardware_readiness": self.accuracy["hardware_readiness"],
                "confidence_level": self.accuracy["confidence_level"],
                "calibration_status": self.accuracy["calibration_status"],
                "warnings": deep_thaw(self.accuracy["warnings"]),
            },
            "limitations": deep_thaw(self.model["limitations"]),
        }


def _paraxial_proxy(beam: BeamState) -> dict[str, Any]:
    angle = max(beam.divergence_x_rad, beam.divergence_y_rad)
    if angle >= math.pi / 2.0:
        error = math.inf
    else:
        error = max(
            abs(math.sin(angle) - angle) / angle,
            abs(math.tan(angle) - angle) / angle,
        )
    return {
        "maximum_divergence_half_angle_rad": angle,
        "small_angle_geometric_proxy_error": error,
        "tolerance": PARAXIAL_PROXY_TOLERANCE,
        "status": "pass" if error <= PARAXIAL_PROXY_TOLERANCE else "warning",
        "interpretation": (
            "Small-angle sin/tan approximation proxy이며 실제 beam error의 직접 추정값은 아닙니다."
        ),
    }


def _accuracy(project: Any, beam: BeamState, paraxial: dict[str, Any]) -> dict[str, Any]:
    scenario = project.active_scenario
    source = scenario["source"]
    record = project.catalog[str(beam.source_component_ref)].data
    readiness = assess_readiness(project)
    warnings = [item.format() for item in project.warnings]
    warnings.extend(readiness.warnings)
    assumptions = [
        "Source에서 profile plane까지 scalar paraxial free-space Gaussian으로 계산합니다.",
        "Downstream optical component와 loss를 적용하지 않습니다.",
    ]
    mfd_interpretation = None
    mfd_uncertainty_m = None
    if source["type"] == "fiber_gaussian":
        definition = str(source["mode_field_diameter_definition"])
        mfd_interpretation = (
            f"{definition} MFD를 Gaussian-equivalent 1/e^2 intensity diameter로 해석해 "
            "waist radius=MFD/2를 사용합니다."
        )
        assumptions.append(mfd_interpretation)
        if source.get("mode_field_diameter_uncertainty_m") is not None:
            mfd_uncertainty_m = float(source["mode_field_diameter_uncertainty_m"])
    if paraxial["status"] != "pass" and not any(
        "small-angle geometric proxy error" in warning for warning in warnings
    ):
        warnings.append(
            "Paraxial small-angle proxy가 software tolerance를 넘었습니다. "
            "Non-paraxial 또는 measured model 필요성을 검토하세요."
        )
    return {
        "model_purpose": readiness.model_purpose,
        "accuracy_mode": readiness.accuracy_mode,
        "hardware_readiness": readiness.hardware_readiness,
        "confidence_level": readiness.confidence_level,
        "calibration_status": readiness.calibration_status,
        "calibration_evidence": readiness.calibration_evidence,
        "scope": "source_free_space_only",
        "source_component_ref": beam.source_component_ref,
        "source_model_level": str(record["model_level"]),
        "source_provenance": deep_thaw(record["provenance"]),
        "catalog_parameter_policy": str(source["catalog_parameter_policy"]),
        "mfd_interpretation": mfd_interpretation,
        "mfd_uncertainty_m": mfd_uncertainty_m,
        "paraxial_validity": paraxial,
        "assumptions": assumptions,
        "warnings": warnings,
    }


def build_phase1_beam_report(
    project: Any,
    beam: BeamState | None = None,
    *,
    z_max_m: float,
    sample_count: int = 201,
    profile_distance_m: float | None = None,
    grid_size: int = 301,
    extent_radii: float = 4.0,
    created_at: datetime | None = None,
) -> Phase1BeamReport:
    """Free-space Gaussian envelope와 정직한 numerical audit를 생성한다."""

    simulation = project.active_scenario["simulation"]
    if simulation["backend"] != "numpy" or simulation["real_dtype"] != "float64":
        raise ValueError(
            "Phase 1 reference beam report는 backend=numpy, real_dtype=float64만 지원합니다."
        )
    state = beam or build_source_beam(project)
    maximum = float(z_max_m)
    if not math.isfinite(maximum) or maximum <= 0.0:
        raise ValueError("z_max_m은 0보다 큰 유한한 값이어야 합니다.")
    count = int(sample_count)
    if count < 2:
        raise ValueError("sample_count는 2 이상이어야 합니다.")
    profile_distance = maximum if profile_distance_m is None else float(profile_distance_m)
    if not math.isfinite(profile_distance) or not 0.0 <= profile_distance <= maximum:
        raise ValueError("profile_distance_m은 0과 z_max_m 사이여야 합니다.")
    if int(grid_size) < 11:
        raise ValueError("grid_size는 11 이상이어야 합니다.")

    distances = np.linspace(0.0, maximum, count, dtype=np.float64)
    radius_x, radius_y = state.radius_at(distances)
    samples = []
    for distance, wx, wy in zip(distances, radius_x, radius_y, strict=True):
        propagated = state.propagate_free_space(float(distance))
        samples.append(
            asdict(
                BeamSample(
                    distance_m=float(distance),
                    radius_x_m=float(wx),
                    radius_y_m=float(wy),
                    q_x_real_m=propagated.q_x_m.real,
                    q_x_imag_m=propagated.q_x_m.imag,
                    q_y_real_m=propagated.q_y_m.real,
                    q_y_imag_m=propagated.q_y_m.imag,
                    power_w=propagated.power_w,
                )
            )
        )

    profile = state.sample_profile(
        distance_m=profile_distance,
        grid_size=grid_size,
        extent_radii=extent_radii,
    )
    refined_grid_size = 2 * int(grid_size) - 1
    refined_profile = state.sample_profile(
        distance_m=profile_distance,
        grid_size=refined_grid_size,
        extent_radii=extent_radii,
    )
    retained_fraction = math.erf(math.sqrt(2.0) * float(extent_radii)) ** 2
    analytical_truncated_power = state.power_w * retained_fraction
    truncation_error = 1.0 - retained_fraction
    quadrature_error = (
        abs(profile.integrated_power_w - analytical_truncated_power)
        / analytical_truncated_power
    )
    grid_convergence_error = (
        abs(profile.integrated_power_w - refined_profile.integrated_power_w)
        / refined_profile.integrated_power_w
    )
    total_power_error = profile.relative_power_error
    profile_status = (
        "pass"
        if total_power_error <= POWER_TOLERANCE
        and quadrature_error <= POWER_TOLERANCE
        and grid_convergence_error <= GRID_CONVERGENCE_TOLERANCE
        else "fail"
    )

    moments_x, moments_y = state.second_moments()
    moment_errors = []
    for distance, expected_x, expected_y in zip(distances, radius_x, radius_y, strict=True):
        moment_x = moments_x.propagate(float(distance)).radius_m
        moment_y = moments_y.propagate(float(distance)).radius_m
        moment_errors.extend(
            (
                abs(moment_x - float(expected_x)) / float(expected_x),
                abs(moment_y - float(expected_y)) / float(expected_y),
            )
        )
    moment_error = max(moment_errors, default=0.0)
    rayleigh_errors = []
    for axis_index, waist, rayleigh in (
        (0, state.waist_radius_x_m, state.rayleigh_range_x_m),
        (1, state.waist_radius_y_m, state.rayleigh_range_y_m),
    ):
        radius_at_rayleigh = state.radius_at(
            rayleigh - state.distance_from_waist_m
        )[axis_index]
        rayleigh_errors.append(abs(float(radius_at_rayleigh) - waist * math.sqrt(2.0)) / waist)
    rayleigh_error = max(rayleigh_errors, default=0.0)
    internal_status = (
        "pass"
        if max(moment_error, rayleigh_error) <= INTERNAL_CONSISTENCY_TOLERANCE
        else "fail"
    )
    paraxial = _paraxial_proxy(state)
    accuracy = _accuracy(project, state, paraxial)
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    profile_radius_x, profile_radius_y = state.radius_at(profile_distance)
    overall_status = (
        "fail"
        if profile_status == "fail" or internal_status == "fail"
        else "warning"
        if paraxial["status"] == "warning"
        or accuracy["hardware_readiness"] != "calibrated"
        or accuracy["calibration_status"] != "calibrated"
        or accuracy["warnings"]
        else "pass"
    )

    return Phase1BeamReport(
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
            "profile_kind": state.profile_kind,
            "profile_distance_m": profile_distance,
            "radius_x_m": float(profile_radius_x),
            "radius_y_m": float(profile_radius_y),
            "divergence_x_rad": state.divergence_x_rad,
            "divergence_y_rad": state.divergence_y_rad,
            "power_w": state.power_w,
            "profile_power_status": profile_status,
            "internal_consistency_status": internal_status,
            "paraxial_validity_status": paraxial["status"],
        },
        accuracy=accuracy,
        model={
            "profile_kind": state.profile_kind,
            "propagation_model": state.propagation_model,
            "radius_definition": "1/e^2 irradiance radius",
            "validity": "paraxial scalar Gaussian free-space propagation",
            "limitations": [
                "Downstream lens, aperture, mirror와 scanner interaction은 적용하지 않습니다.",
                "line_gaussian은 numerical elliptical Gaussian이며 Powell/top-hat line model이 아닙니다.",
                "Polarization, diffraction element, aberration과 coherence phase를 계산하지 않습니다.",
                "Measured beam 또는 독립 bench data와의 validation은 아직 수행하지 않습니다.",
            ],
        },
        source_state=state.to_dict(),
        propagation={
            "z_min_m": 0.0,
            "z_max_m": maximum,
            "sample_count": count,
            "samples": samples,
        },
        profile_audit={
            "check_scope": "numerical_quadrature_and_grid_convergence",
            "distance_m": profile_distance,
            "grid_size": int(grid_size),
            "refined_grid_size": refined_grid_size,
            "extent_radii": float(extent_radii),
            "radius_x_m": profile.radius_x_m,
            "radius_y_m": profile.radius_y_m,
            "peak_irradiance_w_m2": float(np.max(profile.irradiance_w_m2)),
            "requested_power_w": profile.requested_power_w,
            "analytical_truncated_power_w": analytical_truncated_power,
            "integrated_power_w": profile.integrated_power_w,
            "refined_integrated_power_w": refined_profile.integrated_power_w,
            "truncation_relative_error": truncation_error,
            "numerical_quadrature_relative_error": quadrature_error,
            "grid_convergence_relative_error": grid_convergence_error,
            "relative_power_error": total_power_error,
            "status": profile_status,
            "power_tolerance": POWER_TOLERANCE,
            "grid_convergence_tolerance": GRID_CONVERGENCE_TOLERANCE,
        },
        analytical_checks={
            "check_scope": "internal_consistency_only",
            "second_moment_radius_max_relative_error": moment_error,
            "rayleigh_identity_max_relative_error": rayleigh_error,
            "tolerance": INTERNAL_CONSISTENCY_TOLERANCE,
            "status": internal_status,
            "external_validation_status": "not_evaluated",
            "message": (
                "Gaussian closed form과 covariance 경로의 내부 일관성 검사이며 "
                "실제 광원 또는 독립 측정 validation이 아닙니다."
            ),
        },
    )
