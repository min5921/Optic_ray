"""Phase 2 optical train report: ABCD lens, aperture clipping과 power ledger."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from lidarsim import __version__
from lidarsim.config.immutable import deep_thaw
from lidarsim.optics import ABCDMatrix, OpticalTrainResult, propagate_transmitter_train
from lidarsim.receiver import (
    ProjectDetectorBoundary,
    ProjectFiberCoupling,
    ProjectReciprocalReturn,
    ProjectReciprocalReturnPower,
    ReceiverReturn,
    estimate_lambertian_receiver_return,
    evaluate_project_detector_boundary,
    evaluate_project_fiber_coupling,
    evaluate_project_reciprocal_return,
    evaluate_project_reciprocal_return_power,
)
from lidarsim.results.accuracy import assess_readiness
from lidarsim.scene import (
    StlTargetIntersection,
    TargetFootprint,
    evaluate_stl_target_intersections,
    evaluate_target_footprints,
    resolve_mixed_target_visibility,
)


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
    stl_intersections: tuple[dict[str, Any], ...]
    scene_energy_ledger: dict[str, Any]
    receiver_return: dict[str, Any]
    reciprocal_return: dict[str, Any]
    analytical_checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 6,
            "report_type": "phase2_optical_train",
            "manifest": deep_thaw(self.manifest),
            "summary": deep_thaw(self.summary),
            "accuracy": deep_thaw(self.accuracy),
            "model": deep_thaw(self.model),
            "optical_train": deep_thaw(self.optical_train),
            "target_footprints": deep_thaw(self.target_footprints),
            "stl_intersections": deep_thaw(self.stl_intersections),
            "scene_energy_ledger": deep_thaw(self.scene_energy_ledger),
            "receiver_return": deep_thaw(self.receiver_return),
            "reciprocal_return": deep_thaw(self.reciprocal_return),
            "analytical_checks": deep_thaw(self.analytical_checks),
        }


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
    clips = [
        report["aperture_clip"]
        for report in result.component_reports
        if "aperture_clip" in report
    ]
    fractions = [float(clip["transmission_fraction"]) for clip in clips]
    converged_clips = [
        clip for clip in clips if "quadrature_relative_residual" in clip
    ]
    residuals = [
        float(clip["quadrature_relative_residual"])
        for clip in converged_clips
    ]
    tolerances = [
        float(clip["quadrature_tolerance"])
        for clip in converged_clips
    ]
    convergence_status = (
        "warning"
        if any(clip.get("convergence_status") != "pass" for clip in converged_clips)
        else "pass"
    )
    valid = all(0.0 <= value <= 1.0 for value in fractions)
    status = (
        "fail"
        if not valid
        else "warning"
        if convergence_status != "pass"
        else "pass"
    )
    return {
        "checked_apertures": len(fractions),
        "minimum_transmission_fraction": min(fractions) if fractions else None,
        "quadrature_checked_apertures": len(converged_clips),
        "max_quadrature_relative_residual": max(residuals) if residuals else None,
        "minimum_quadrature_tolerance": min(tolerances) if tolerances else None,
        "numerical_convergence_status": convergence_status,
        "status": status,
        "message": (
            "Aperture clipping fraction의 물리 범위와 numerical aperture의 "
            "base/refined quadrature 수렴을 확인합니다."
        ),
    }


def _target_footprint_check(footprints: tuple[TargetFootprint, ...]) -> dict[str, Any]:
    hit_count = sum(1 for footprint in footprints if footprint.hit)
    powers = [footprint.estimated_power_on_target_w for footprint in footprints]
    contributing = [
        footprint for footprint in footprints if footprint.contributes_to_scene_energy
    ]
    finite = all(math.isfinite(power) and power >= 0.0 for power in powers)
    unique_visible = len(contributing) <= 1
    integrated = [footprint for footprint in footprints if footprint.hit]
    residuals = [
        footprint.quadrature_relative_residual for footprint in integrated
    ]
    tolerances = [footprint.quadrature_tolerance for footprint in integrated]
    convergence_status = (
        "warning"
        if any(footprint.convergence_status != "pass" for footprint in integrated)
        else "pass"
    )
    status = (
        "fail"
        if not finite or not unique_visible
        else "pass"
        if contributing and convergence_status == "pass"
        else "warning"
    )
    return {
        "target_count": len(footprints),
        "hit_count": hit_count,
        "visible_contributing_target_count": len(contributing),
        "visible_target_id": contributing[0].target_id if contributing else None,
        "total_estimated_power_on_target_w": sum(powers),
        "quadrature_checked_footprints": len(integrated),
        "max_quadrature_relative_residual": max(residuals) if residuals else None,
        "minimum_quadrature_tolerance": min(tolerances) if tolerances else None,
        "numerical_convergence_status": convergence_status,
        "status": status,
        "message": (
            "Rectangle-plane 후보 hit, nearest-visible target energy ownership과 "
            "base/refined footprint quadrature 수렴을 검사합니다."
        ),
    }


def _stl_closest_hit_check(
    intersections: tuple[StlTargetIntersection, ...],
) -> dict[str, Any]:
    evaluated = [item for item in intersections if item.intersection is not None]
    hits = [item for item in intersections if item.hit]
    visible = [
        item for item in intersections if item.contributes_to_center_ray_visibility
    ]
    if len(visible) > 1:
        status = "fail"
    elif not intersections:
        status = "not_evaluated"
    elif len(evaluated) != len(intersections):
        status = "warning"
    else:
        status = "pass"
    return {
        "target_count": len(intersections),
        "evaluated_count": len(evaluated),
        "hit_count": len(hits),
        "visible_hit_count": len(visible),
        "visible_target_id": visible[0].target_id if visible else None,
        "status": status,
        "message": (
            "STL sidecar scale/placement를 적용한 CPU float64 center-ray nearest "
            "positive triangle hit와 explicit miss를 검사합니다."
        ),
    }


def _visible_center_ray_target(
    footprints: tuple[TargetFootprint, ...],
    stl_intersections: tuple[StlTargetIntersection, ...],
) -> tuple[str | None, str | None]:
    for footprint in footprints:
        if footprint.contributes_to_scene_energy:
            return footprint.target_id, "rectangle_plane"
    for intersection in stl_intersections:
        if intersection.contributes_to_center_ray_visibility:
            return intersection.target_id, "stl_asset"
    return None, None


def _scene_energy_ledger(
    final_power_w: float,
    footprints: tuple[TargetFootprint, ...],
    stl_intersections: tuple[StlTargetIntersection, ...],
) -> dict[str, Any]:
    entries = [
        {
            "target_id": footprint.target_id,
            "geometry_type": "rectangle_plane",
            "hit": footprint.hit,
            "visibility_status": footprint.visibility_status,
            "power_status": "evaluated",
            "candidate_power_on_target_w": (
                footprint.candidate_estimated_power_on_target_w
            ),
            "contributing_power_on_target_w": footprint.estimated_power_on_target_w,
            "contributes_to_scene_energy": footprint.contributes_to_scene_energy,
            "contributes_to_center_ray_visibility": (
                footprint.contributes_to_scene_energy
            ),
            "occluded_by_target_id": footprint.occluded_by_target_id,
        }
        for footprint in footprints
    ]
    entries.extend(
        {
            "target_id": item.target_id,
            "geometry_type": "stl_asset",
            "hit": item.hit,
            "visibility_status": item.visibility_status,
            "power_status": "not_evaluated",
            "candidate_power_on_target_w": None,
            "contributing_power_on_target_w": None,
            "contributes_to_scene_energy": False,
            "contributes_to_center_ray_visibility": (
                item.contributes_to_center_ray_visibility
            ),
            "occluded_by_target_id": item.occluded_by_target_id,
        }
        for item in stl_intersections
    )
    total = sum(
        footprint.estimated_power_on_target_w
        for footprint in footprints
        if footprint.contributes_to_scene_energy
    )
    oversubscription = max(total - float(final_power_w), 0.0)
    tolerance = max(ENERGY_LEDGER_TOLERANCE_W, abs(float(final_power_w)) * 1.0e-12)
    visible_target_id, visible_geometry_type = _visible_center_ray_target(
        footprints,
        stl_intersections,
    )
    partial = visible_geometry_type == "stl_asset" and float(final_power_w) > tolerance
    return {
        "policy": "nearest_positive_center_ray_hit_is_opaque_visible_target",
        "input_beam_power_w": float(final_power_w),
        "entries": entries,
        "visible_target_id": visible_target_id,
        "visible_geometry_type": visible_geometry_type,
        "power_accounting_status": (
            "partial_not_evaluated" if partial else "complete"
        ),
        "total_contributing_power_on_target_w": total,
        "unintercepted_or_unmodeled_power_w": max(float(final_power_w) - total, 0.0),
        "oversubscription_residual_w": oversubscription,
        "tolerance_w": tolerance,
        "status": (
            "fail"
            if oversubscription > tolerance
            else "warning"
            if partial
            else "pass"
        ),
        "assumptions": [
            "모든 rectangle-plane 후보와 STL closest-hit 결과는 report에 보존합니다.",
            "현재 단일 center ray visibility에서는 가장 가까운 positive hit 하나를 opaque visible target으로 선택합니다.",
            "더 먼 hit의 후보 footprint geometry는 보존하지만 target/receiver scene energy는 0으로 둡니다.",
            "Visible STL target의 full footprint power는 M1에서 not_evaluated이므로 scene power accounting은 partial입니다.",
            "Beam footprint 일부가 서로 다른 target에 나뉘는 면적 visibility 적분은 아직 계산하지 않습니다.",
        ],
    }


def _virtual_aperture_regression_returns(
    project: Any,
    footprints: tuple[TargetFootprint, ...],
) -> tuple[ReceiverReturn, ...]:
    """Reciprocal architecture에서도 기존 virtual-aperture intermediate를 유지한다."""

    receiver = deep_thaw(project.active_scenario["receiver"])
    receiver["architecture"] = "virtual_monostatic"
    results: list[ReceiverReturn] = []
    for footprint in footprints:
        material = project.catalog[footprint.material_ref].data
        results.append(
            estimate_lambertian_receiver_return(
                footprint=footprint,
                material=material,
                receiver=receiver,
            )
        )
    return tuple(results)


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
        "output_plane": "virtual_aperture_regression_intermediate",
        "returns": items,
        "total_estimated_received_power_w": total_power,
        "power_at_virtual_aperture_w": total_power,
        "total_estimated_power_on_target_w": total_power_on_target,
        "total_link_loss_db": link_loss,
        "assumptions": [
            "Nearest visible target footprint만 small-footprint Lambertian patch로 계산합니다.",
            "Target material의 one_sided/two_sided 정책과 intersection의 radiometric normal을 동일하게 사용합니다.",
            "estimated_received_power_w는 기존 schema 이름이며 현재는 virtual aperture plane의 값입니다.",
            "동일 scanner/collimator의 역방향 광로와 single-mode fiber mode coupling은 계산하지 않습니다.",
            "Occlusion, BRDF lobe, detector response, coherent sum과 speckle은 계산하지 않습니다.",
        ],
    }


def _reciprocal_return_check(
    result: ProjectReciprocalReturn,
) -> dict[str, Any]:
    if result.architecture != "reciprocal_single_mode_fiber":
        status = "not_evaluated"
        message = "Configured receiver architecture에 reciprocal R1 path가 적용되지 않습니다."
    elif result.path is None:
        status = "warning"
        message = "Nearest-visible target 또는 forward component report가 없어 R1 path를 평가하지 못했습니다."
    elif result.path.terminated:
        status = "fail"
        message = "Reciprocal center ray가 실제 return plane/aperture에서 종료되었습니다."
    else:
        status = result.path.closure.status
        message = "Same mirror/collimator/fiber reference plane의 reciprocal closure residual을 검사합니다."
    return {
        "status": status,
        "closure_status": None if result.path is None else result.path.closure.status,
        "terminated": None if result.path is None else result.path.terminated,
        "maximum_position_residual_m": (
            None
            if result.path is None
            else result.path.closure.maximum_position_residual_m
        ),
        "maximum_angular_residual_rad": (
            None
            if result.path is None
            else result.path.closure.maximum_angular_residual_rad
        ),
        "message": message,
    }


def _reciprocal_return_power_check(
    result: ProjectReciprocalReturnPower,
) -> dict[str, Any]:
    power = result.result
    if result.status == "fail":
        status = "fail"
        message = result.status_reason or "R2 reciprocal return power evaluation이 실패했습니다."
    elif result.status == "not_evaluated":
        status = "not_evaluated"
        message = result.status_reason or "R2 reciprocal return power를 평가하지 않았습니다."
    elif result.status == "unsupported_material":
        status = "warning"
        message = result.status_reason or "R2가 지원하지 않는 target material입니다."
    elif power is None:
        status = "warning"
        message = result.status_reason or "R2 reciprocal return power result가 없습니다."
    elif power.energy_check_status == "fail":
        status = "fail"
        message = "Return power ledger energy conservation residual이 tolerance를 초과했습니다."
    elif power.status == "terminated":
        status = "warning"
        message = "R1 actual geometry에서 return power가 명시적으로 0 W로 종료되었습니다."
    elif power.status == "zero_power":
        status = "warning"
        message = "Return ledger는 일관되지만 catalog/geometry 조건으로 최종 power가 0 W입니다."
    else:
        status = "pass"
        message = "Target-to-fiber-plane R2 return ledger와 energy conservation을 검사합니다."
    return {
        "status": status,
        "power_status": result.status,
        "energy_check_status": None if power is None else power.energy_check_status,
        "maximum_energy_residual_w": (
            None if power is None else power.maximum_energy_residual_w
        ),
        "energy_tolerance_w": None if power is None else power.energy_tolerance_w,
        "target_hit_residual_m": result.target_hit_residual_m,
        "target_hit_tolerance_m": result.target_hit_tolerance_m,
        "message": message,
    }


def _fiber_coupling_check(result: ProjectFiberCoupling) -> dict[str, Any]:
    coupling = result.result
    if result.status == "fail":
        status = "fail"
        message = result.status_reason or "R3 upstream 또는 coupling energy check가 실패했습니다."
    elif result.status == "not_evaluated":
        status = "not_evaluated"
        message = result.status_reason or "R3 fiber coupling을 평가하지 않았습니다."
    elif result.status == "unsupported_mfd_definition":
        status = "warning"
        message = result.status_reason or "R3가 지원하지 않는 MFD definition입니다."
    elif coupling is None:
        status = "warning"
        message = result.status_reason or "R3 fiber coupling result가 없습니다."
    elif result.energy_check_status == "fail":
        status = "fail"
        message = "Fiber coupling ledger energy residual이 tolerance를 초과했습니다."
    elif coupling.status == "zero_available_power":
        status = "warning"
        message = "Alignment efficiency는 계산했지만 R2 available fiber-plane power가 0 W입니다."
    else:
        status = "pass"
        message = "Gaussian alignment proxy efficiency와 passive coupling ledger를 검사합니다."
    return {
        "status": status,
        "fiber_coupling_status": result.status,
        "energy_check_status": result.energy_check_status,
        "maximum_energy_residual_w": result.maximum_energy_residual_w,
        "energy_tolerance_w": result.energy_tolerance_w,
        "coherent_field_status": result.coherent_field_status,
        "field_usable_for_coherent_propagation": (
            result.field_usable_for_coherent_propagation
        ),
        "message": message,
    }


def _detector_boundary_check(result: ProjectDetectorBoundary) -> dict[str, Any]:
    boundary = result.result
    if result.status == "fail":
        status = "fail"
        message = result.status_reason or "R4 upstream 또는 detector boundary energy check가 실패했습니다."
    elif result.status == "not_evaluated":
        status = "not_evaluated"
        message = result.status_reason or "R4 detector-input boundary를 평가하지 않았습니다."
    elif boundary is None:
        status = "warning"
        message = result.status_reason or "R4 detector-input boundary result가 없습니다."
    elif result.energy_check_status == "fail":
        status = "fail"
        message = "Detector boundary power ledger energy residual이 tolerance를 초과했습니다."
    elif result.status == "zero_input":
        status = "warning"
        message = "유효한 R3 fiber-coupled input이 0 W이므로 detector input도 0 W입니다."
    elif result.status == "blocked":
        status = "warning"
        message = "Duplexer return transmission이 0이므로 detector input이 차단되었습니다."
    else:
        status = "pass"
        message = "R3-to-detector passive duplexer ledger와 energy conservation을 검사합니다."
    return {
        "status": status,
        "detector_input_status": result.status,
        "energy_check_status": result.energy_check_status,
        "maximum_energy_residual_w": result.maximum_energy_residual_w,
        "energy_tolerance_w": result.energy_tolerance_w,
        "coherent_field_status": result.coherent_field_status,
        "field_usable_for_coherent_propagation": (
            result.field_usable_for_coherent_propagation
        ),
        "detector_response_status": "not_evaluated",
        "message": message,
    }


def _reciprocal_return_section(
    geometry: ProjectReciprocalReturn,
    power: ProjectReciprocalReturnPower,
    coupling: ProjectFiberCoupling,
    detector_boundary: ProjectDetectorBoundary,
) -> dict[str, Any]:
    section = geometry.to_dict()
    section.update(
        {
            "power_status": power.status,
            "power_status_reason": power.status_reason,
            "power_geometry_type": power.geometry_type,
            "material_ref": power.material_ref,
            "material_model": power.material_model,
            "material_reflectivity": power.material_reflectivity,
            "target_hit_residual_m": power.target_hit_residual_m,
            "target_hit_tolerance_m": power.target_hit_tolerance_m,
            "return_power": None if power.result is None else power.result.to_dict(),
            "fiber_coupling_status": coupling.status,
            "fiber_coupling_status_reason": coupling.status_reason,
            "fiber_coupling": (
                None if coupling.status == "not_evaluated" else coupling.to_dict()
            ),
            "detector_status": detector_boundary.status,
            "detector_status_reason": detector_boundary.status_reason,
            "detector_boundary": (
                None
                if detector_boundary.status == "not_evaluated"
                else detector_boundary.to_dict()
            ),
            "assumptions": (
                list(geometry.assumptions)
                + list(power.assumptions)
                + list(coupling.assumptions)
                + list(detector_boundary.assumptions)
            ),
            "warnings": (
                list(geometry.warnings)
                + list(power.warnings)
                + list(coupling.warnings)
                + list(detector_boundary.warnings)
            ),
        }
    )
    return section


def _accuracy(
    project: Any,
    result: OpticalTrainResult,
    footprints: tuple[TargetFootprint, ...],
    stl_intersections: tuple[StlTargetIntersection, ...],
    returns: tuple[ReceiverReturn, ...],
    reciprocal_return: ProjectReciprocalReturn,
    reciprocal_return_power: ProjectReciprocalReturnPower,
    fiber_coupling: ProjectFiberCoupling,
    detector_boundary: ProjectDetectorBoundary,
) -> dict[str, Any]:
    readiness = assess_readiness(project)
    warnings = [item.format() for item in project.warnings]
    warnings.extend(readiness.warnings)
    warnings.extend(result.warnings)
    for footprint in footprints:
        warnings.extend(footprint.warnings)
    for intersection in stl_intersections:
        warnings.extend(intersection.warnings)
        if intersection.hit:
            warnings.append(
                f"STL target {intersection.target_id!r} center-ray hit는 계산했지만 full footprint와 radiometry는 not_evaluated입니다."
            )
    for receiver_return in returns:
        warnings.extend(receiver_return.warnings)
    warnings.extend(reciprocal_return.warnings)
    warnings.extend(reciprocal_return_power.warnings)
    warnings.extend(fiber_coupling.warnings)
    warnings.extend(detector_boundary.warnings)
    warnings.append(
        "power_at_virtual_aperture_w는 기존 analytical regression intermediate입니다. "
        "R2 reciprocal return power와 별도이며 fiber 결합 또는 detector input power가 아닙니다."
    )
    if result.unsupported_elements:
        warnings.append(
            "Scanner/mirror 이후 propagation은 아직 계산하지 않고 unsupported_elements에 기록합니다."
        )
    return {
        "model_purpose": readiness.model_purpose,
        "accuracy_mode": readiness.accuracy_mode,
        "hardware_readiness": readiness.hardware_readiness,
        "confidence_level": readiness.confidence_level,
        "calibration_status": readiness.calibration_status,
        "calibration_evidence": readiness.calibration_evidence,
        "scope": (
            "source_to_static_mirror_rectangle_or_stl_center_ray_target_"
            "lambertian_virtual_aperture_and_reciprocal_center_ray_geometry_"
            "and_return_power_ledger_and_gaussian_alignment_proxy"
            "_and_passive_detector_input_boundary"
        ),
        "assumptions": [
            "Source부터 collimator까지는 scalar paraxial Gaussian q-parameter로 계산합니다.",
            "Collimator는 catalog의 ideal_thin_lens, clear aperture와 power_transmission만 사용합니다.",
            "Scanner mirror는 catalog base pose에 static command angle을 적용하고 catalog reflectivity를 사용합니다.",
            "Rectangle-plane target footprint는 projected Gaussian first-order model로 계산합니다.",
            "STL target는 sidecar world placement가 적용된 CPU float64 closest-hit와 geometric normal만 계산합니다.",
            "Target roll은 geometry.width_axis로 고정하고 material surface sidedness를 intersection과 radiometry에 동일하게 적용합니다.",
            "Mirror aperture와 target footprint 적분은 base/refined Gauss-Legendre 수렴 잔차를 보고합니다.",
            "Receiver return은 Lambertian small-footprint analytical virtual-aperture approximation입니다.",
            "Reciprocal return은 nearest-visible rectangle target에서 same mirror/collimator/fiber plane까지의 R1 geometry와 R2 scalar-power ledger입니다.",
            "R2 aperture acceptance는 actual R1 center-ray pass/miss만 사용하고 forward Gaussian clipping fraction을 재사용하지 않습니다.",
            "R3는 R2 fiber-plane power에 deterministic Gaussian alignment proxy overlap을 적용한 analytical upper-bound/reference입니다.",
            "Radiometric R3는 coherent input field를 만들거나 downstream으로 전달하지 않습니다.",
            "R4는 R3 coupled power에 duplexer return transmission만 적용하고 detector input optical boundary에서 종료합니다.",
            "R4 detector input은 analytical/uncalibrated reference이며 detector response와 coherent field를 만들지 않습니다.",
            "Aperture clipping 뒤 profile shape, diffraction과 edge scattering은 계산하지 않고 power loss만 반영합니다.",
            "Scanner time dynamics, STL full footprint/radiometry, BRDF/BSDF, detector noise와 coherent FMCW는 계산하지 않습니다.",
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
    footprints = evaluate_target_footprints(
        project,
        train.final_state.state,
        blocked_reason=(
            None
            if train.termination is None
            else str(train.termination["reason"])
        ),
    )
    stl_intersections = evaluate_stl_target_intersections(
        project,
        train.final_state.state,
        blocked_reason=(
            None
            if train.termination is None
            else str(train.termination["reason"])
        ),
    )
    footprints, stl_intersections = resolve_mixed_target_visibility(
        footprints,
        stl_intersections,
    )
    receiver_returns = _virtual_aperture_regression_returns(project, footprints)
    reciprocal_return = evaluate_project_reciprocal_return(
        project,
        train,
        footprints,
    )
    reciprocal_return_power = evaluate_project_reciprocal_return_power(
        project,
        footprints,
        reciprocal_return,
    )
    fiber_coupling = evaluate_project_fiber_coupling(
        project,
        reciprocal_return,
        reciprocal_return_power,
    )
    reciprocal_power_result = reciprocal_return_power.result
    detector_boundary = evaluate_project_detector_boundary(
        project,
        fiber_coupling,
        power_on_target_w=(
            None
            if reciprocal_power_result is None
            else reciprocal_power_result.power_on_target_w
        ),
    )
    final_state = train.final_state
    q_check = _q_check(train)
    energy_check = _energy_check(train)
    aperture_check = _aperture_check(train)
    target_check = _target_footprint_check(footprints)
    stl_check = _stl_closest_hit_check(stl_intersections)
    scene_ledger = _scene_energy_ledger(
        train.final_state.state.power_w,
        footprints,
        stl_intersections,
    )
    receiver_check = _receiver_return_check(receiver_returns)
    reciprocal_check = _reciprocal_return_check(reciprocal_return)
    reciprocal_power_check = _reciprocal_return_power_check(
        reciprocal_return_power
    )
    fiber_coupling_check = _fiber_coupling_check(fiber_coupling)
    detector_boundary_check = _detector_boundary_check(detector_boundary)
    accuracy = _accuracy(
        project,
        train,
        footprints,
        stl_intersections,
        receiver_returns,
        reciprocal_return,
        reciprocal_return_power,
        fiber_coupling,
        detector_boundary,
    )
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
        scene_ledger["status"],
        reciprocal_check["status"],
        reciprocal_power_check["status"],
        fiber_coupling_check["status"],
        detector_boundary_check["status"],
        stl_check["status"],
    ]
    overall_status = (
        "fail"
        if "fail" in check_statuses
        else "warning"
        if (
            accuracy["hardware_readiness"] != "calibrated"
            or accuracy["warnings"]
            or train.unsupported_elements
            or "warning" in check_statuses
        )
        else "pass"
    )
    receiver_section = _receiver_return_section(receiver_returns)
    reciprocal_section = _reciprocal_return_section(
        reciprocal_return,
        reciprocal_return_power,
        fiber_coupling,
        detector_boundary,
    )
    reciprocal_power = reciprocal_return_power.result
    coupling_result = fiber_coupling.result
    detector_result = detector_boundary.result
    visible_target_id, visible_geometry_type = _visible_center_ray_target(
        footprints,
        stl_intersections,
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
            "optical_train_status": "terminated" if train.terminated else "completed",
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
            "target_hit_count": target_check["hit_count"] + stl_check["hit_count"],
            "rectangle_target_hit_count": target_check["hit_count"],
            "stl_target_hit_count": stl_check["hit_count"],
            "visible_target_id": visible_target_id,
            "visible_geometry_type": visible_geometry_type,
            "estimated_power_on_target_w": target_check[
                "total_estimated_power_on_target_w"
            ],
            "estimated_received_power_w": receiver_section["total_estimated_received_power_w"],
            "power_at_virtual_aperture_w": receiver_section["power_at_virtual_aperture_w"],
            "link_loss_db": receiver_section["total_link_loss_db"],
            "q_parameter_status": q_check["status"],
            "energy_ledger_status": energy_check["status"],
            "aperture_status": aperture_check["status"],
            "target_footprint_status": target_check["status"],
            "stl_closest_hit_status": stl_check["status"],
            "receiver_return_status": receiver_check["status"],
            "reciprocal_return_status": reciprocal_check["status"],
            "power_at_return_mirror_w": (
                None if reciprocal_power is None else reciprocal_power.power_at_return_mirror_w
            ),
            "power_at_return_collimator_w": (
                None
                if reciprocal_power is None
                else reciprocal_power.power_at_return_collimator_w
            ),
            "power_at_fiber_plane_w": (
                None if reciprocal_power is None else reciprocal_power.power_at_fiber_plane_w
            ),
            "target_to_fiber_plane_link_loss_db": (
                None
                if reciprocal_power is None
                else reciprocal_power.target_to_fiber_plane_link_loss_db
            ),
            "reciprocal_return_power_status": reciprocal_return_power.status,
            "fiber_coupling_status": fiber_coupling.status,
            "fiber_coupling_efficiency": (
                None
                if coupling_result is None
                else coupling_result.fiber_coupling_efficiency
            ),
            "power_coupled_into_fiber_w": (
                None
                if coupling_result is None
                else coupling_result.power_coupled_into_fiber_w
            ),
            "target_to_fiber_coupled_link_loss_db": (
                fiber_coupling.target_to_fiber_coupled_link_loss_db
            ),
            "detector_input_status": detector_boundary.status,
            "power_at_detector_input_w": (
                None
                if detector_result is None
                else detector_result.power_at_detector_input_w
            ),
            "fiber_coupled_to_detector_input_link_loss_db": (
                detector_boundary.fiber_coupled_to_detector_input_link_loss_db
            ),
            "target_to_detector_input_link_loss_db": (
                detector_boundary.target_to_detector_input_link_loss_db
            ),
            "source_to_detector_input_round_trip_link_loss_db": (
                detector_boundary.source_to_detector_input_round_trip_link_loss_db
            ),
        },
        accuracy=accuracy,
        model={
            "propagation_model": "gaussian_q_abcd_plus_analytical_radiometry",
            "radius_definition": "1/e^2 irradiance radius",
            "validity": (
                "Paraxial scalar Gaussian, ideal thin lens with deterministic off-axis chief ray, projected apertures, "
                "static flat mirror reflection, rectangle-plane footprint, CPU STL center-ray closest-hit, "
                "Lambertian return power, deterministic Gaussian alignment coupling proxy and passive detector-input boundary"
            ),
            "limitations": [
                "No aberration, diffraction, coating spectral curve, polarization or ghost reflection.",
                "Deterministic placement decenter/tilt is geometric/paraxial only; no aberration model or stochastic tolerance ensemble yet.",
                "This Phase 2 report applies one static scanner command angle; use the ideal scanner-path report for forward-line samples.",
                "No scanner motor lag, jitter, bidirectional return stroke or calibration table yet.",
                "STL center-ray closest-hit is implemented; no STL full footprint clipping, area visibility, occlusion graph or BVH yet.",
                "No non-Lambertian BRDF/BSDF, roughness, speckle or coherent FMCW yet.",
                "R1 reciprocal center-ray geometry and R2 small-footprint Lambertian scalar return-power ledger are implemented.",
                "R2 uses binary center-ray aperture acceptance; exact diffuse-return spatial aperture/solid-angle integration is not implemented.",
                "R3 Gaussian alignment coupling is an optimistic proxy for diffuse return; spatial-mode reciprocity/decomposition is not implemented.",
                "Radiometric R3 reports no coherent field and its normalized overlap cannot be propagated as an FMCW field.",
                "R4 applies only configured duplexer return transmission and stops at the detector input optical boundary.",
                "R4 detector input remains analytical/uncalibrated and contains no detector responsivity, photocurrent, saturation or noise model.",
                "estimated_received_power_w and power_at_virtual_aperture_w are analytical virtual-aperture values, not fiber-coupled power.",
                "No detector photocurrent, noise, saturation, FFT or CZT yet.",
                "No measured/vendor black-box optical model execution yet.",
                "Astigmatic post-lens beam with separated x/y waist locations is rejected by the current BeamState contract.",
            ],
        },
        optical_train=train.to_dict(),
        target_footprints=tuple(footprint.to_dict() for footprint in footprints),
        stl_intersections=tuple(item.to_dict() for item in stl_intersections),
        scene_energy_ledger=scene_ledger,
        receiver_return=receiver_section,
        reciprocal_return=reciprocal_section,
        analytical_checks={
            "check_scope": "internal_consistency_only",
            "q_parameter": q_check,
            "energy_ledger": energy_check,
            "aperture_fraction": aperture_check,
            "target_footprint": target_check,
            "stl_closest_hit": stl_check,
            "scene_energy_ledger": {
                "status": scene_ledger["status"],
                "message": (
                    "Nearest-visible target contribution이 final beam power를 초과하지 "
                    "않는지 검사합니다."
                ),
                "oversubscription_residual_w": scene_ledger[
                    "oversubscription_residual_w"
                ],
                "tolerance_w": scene_ledger["tolerance_w"],
            },
            "receiver_return": receiver_check,
            "reciprocal_return": reciprocal_check,
            "reciprocal_return_power": reciprocal_power_check,
            "fiber_coupling": fiber_coupling_check,
            "detector_boundary": detector_boundary_check,
            "external_validation_status": "not_evaluated",
        },
    )
