"""Phase 2.4-R2 project adapter for reciprocal analytical return power.

The adapter deliberately keeps the forward transmitter power ledger separate
from the return ledger.  It accepts only the configured nearest-visible
``rectangle_plane`` target and the actual R1 center-ray intersections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from lidarsim.scene import TargetFootprint

from .reciprocal_project import ProjectReciprocalReturn, RECIPROCAL_ARCHITECTURE
from .return_power import (
    ReciprocalReturnPowerResult,
    estimate_reciprocal_return_power,
)


@dataclass(frozen=True, slots=True)
class ProjectReciprocalReturnPower:
    """One active project's structured R2 evaluation result."""

    status: str
    status_reason: str | None
    target_id: str | None
    geometry_type: str | None
    material_ref: str | None
    material_model: str | None
    material_reflectivity: float | None
    target_hit_residual_m: float | None
    target_hit_tolerance_m: float
    result: ReciprocalReturnPowerResult | None
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "status_reason": self.status_reason,
            "target_id": self.target_id,
            "geometry_type": self.geometry_type,
            "material_ref": self.material_ref,
            "material_model": self.material_model,
            "material_reflectivity": self.material_reflectivity,
            "target_hit_residual_m": self.target_hit_residual_m,
            "target_hit_tolerance_m": self.target_hit_tolerance_m,
            "result": None if self.result is None else self.result.to_dict(),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _target_spec(
    scenario: Mapping[str, Any],
    target_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (
            target
            for target in scenario["scene"]["targets"]
            if str(target["id"]) == target_id
        ),
        None,
    )


def _element_spec(
    scenario: Mapping[str, Any],
    element_id: str,
) -> Mapping[str, Any]:
    element = next(
        (
            item
            for item in scenario["optical_assembly"]["elements"]
            if str(item["id"]) == element_id
        ),
        None,
    )
    if element is None:
        raise ValueError(
            f"receiver.return_path가 존재하지 않는 element를 참조합니다: {element_id!r}"
        )
    return element


def _visible_configured_footprint(
    footprints: tuple[TargetFootprint, ...],
    target_id: str,
) -> TargetFootprint | None:
    return next(
        (
            footprint
            for footprint in footprints
            if footprint.target_id == target_id
            and footprint.hit
            and footprint.contributes_to_scene_energy
        ),
        None,
    )


def _not_evaluated(
    *,
    status: str,
    reason: str,
    target_id: str | None,
    geometry_type: str | None,
    material_ref: str | None,
    material_model: str | None,
    material_reflectivity: float | None,
    assumptions: tuple[str, ...],
    target_hit_residual_m: float | None = None,
    target_hit_tolerance_m: float = 1.0e-9,
) -> ProjectReciprocalReturnPower:
    return ProjectReciprocalReturnPower(
        status=status,
        status_reason=reason,
        target_id=target_id,
        geometry_type=geometry_type,
        material_ref=material_ref,
        material_model=material_model,
        material_reflectivity=material_reflectivity,
        target_hit_residual_m=target_hit_residual_m,
        target_hit_tolerance_m=target_hit_tolerance_m,
        result=None,
        assumptions=assumptions,
        warnings=(reason,),
    )


def evaluate_project_reciprocal_return_power(
    project: Any,
    footprints: tuple[TargetFootprint, ...],
    reciprocal_geometry: ProjectReciprocalReturn,
    *,
    target_hit_tolerance_m: float = 1.0e-9,
) -> ProjectReciprocalReturnPower:
    """Map resolved project data and R1 actual hits into the R2 power ledger.

    R1 center-ray aperture pass maps to exactly 1.0 and every other status maps
    to zero.  Forward Gaussian clipping fractions are intentionally never
    reused because the diffuse return spatial distribution has not been
    integrated over those apertures.
    """

    tolerance = float(target_hit_tolerance_m)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("target_hit_tolerance_m은 0보다 큰 유한한 값이어야 합니다.")
    assumptions = (
        "Configured nearest-visible rectangle_plane target 하나만 reciprocal return power에 기여합니다.",
        "Target의 intersection.radiometric_normal을 Lambertian emission cosine에 사용합니다.",
        "Target emission cosine과 projected mirror-area cosine은 서로 다른 기하 항으로 각각 한 번만 적용합니다.",
        "R1 mirror/collimator center-ray aperture pass는 1.0, 그 외 상태는 0.0으로 매핑합니다.",
        "Forward Gaussian aperture clipping fraction은 diffuse return 분포와 같지 않으므로 재사용하지 않습니다.",
        "Return power ledger는 forward transmitter power ledger와 독립적으로 보고합니다.",
        "Footprint hit와 R1 actual target hit가 target_hit_tolerance_m 안에서 일치할 때만 R2를 계산합니다.",
        "이 결과는 small-footprint Lambertian analytical reference이며 측정 보정된 hardware 예측이 아닙니다.",
    )
    scenario = project.active_scenario
    receiver = scenario["receiver"]
    architecture = str(receiver["architecture"])
    if architecture != RECIPROCAL_ARCHITECTURE:
        return _not_evaluated(
            status="not_evaluated",
            reason=(
                "receiver.architecture가 reciprocal_single_mode_fiber가 아니므로 "
                "R2 return power를 계산하지 않았습니다."
            ),
            target_id=None,
            geometry_type=None,
            material_ref=None,
            material_model=None,
            material_reflectivity=None,
            assumptions=assumptions,
            target_hit_tolerance_m=tolerance,
        )

    path_config = receiver.get("return_path")
    if not isinstance(path_config, Mapping):
        raise ValueError("reciprocal receiver에는 receiver.return_path가 필요합니다.")
    target_id = str(path_config["target_ref"])
    target_spec = _target_spec(scenario, target_id)
    if target_spec is None:
        raise ValueError(
            f"receiver.return_path.target_ref가 존재하지 않는 target을 참조합니다: {target_id!r}"
        )
    geometry_type = str(target_spec["geometry"]["type"])
    material_ref = str(target_spec["material_ref"])
    material = project.catalog[material_ref].data
    optical = material["optical"]
    material_model = str(optical.get("model", "unknown"))
    reflectivity_value = optical.get("hemispherical_reflectivity")
    material_reflectivity = (
        None if reflectivity_value is None else float(reflectivity_value)
    )

    if geometry_type != "rectangle_plane":
        return _not_evaluated(
            status="not_evaluated",
            reason=(
                f"Target {target_id!r} geometry는 {geometry_type!r}입니다. "
                "R2는 rectangle_plane full footprint radiometry만 지원하며 STL radiometry는 아직 계산하지 않습니다."
            ),
            target_id=target_id,
            geometry_type=geometry_type,
            material_ref=material_ref,
            material_model=material_model,
            material_reflectivity=material_reflectivity,
            assumptions=assumptions,
            target_hit_tolerance_m=tolerance,
        )
    if material_model != "lambertian" or material_reflectivity is None:
        return _not_evaluated(
            status="unsupported_material",
            reason=(
                f"R2가 지원하지 않는 material optical.model입니다: {material_model!r}. "
                "현재는 hemispherical_reflectivity가 있는 lambertian만 계산합니다."
            ),
            target_id=target_id,
            geometry_type=geometry_type,
            material_ref=material_ref,
            material_model=material_model,
            material_reflectivity=material_reflectivity,
            assumptions=assumptions,
            target_hit_tolerance_m=tolerance,
        )

    footprint = _visible_configured_footprint(footprints, target_id)
    if footprint is None or footprint.intersection.hit_center_m is None:
        return _not_evaluated(
            status="not_evaluated",
            reason=(
                f"Configured target {target_id!r}가 nearest-visible contributing rectangle footprint가 아니므로 "
                "R2 return power를 계산하지 않았습니다."
            ),
            target_id=target_id,
            geometry_type=geometry_type,
            material_ref=material_ref,
            material_model=material_model,
            material_reflectivity=material_reflectivity,
            assumptions=assumptions,
            target_hit_tolerance_m=tolerance,
        )
    if reciprocal_geometry.path is None:
        return _not_evaluated(
            status="not_evaluated",
            reason=(
                "Configured nearest-visible target의 R1 reciprocal center-ray path가 없어 "
                "R2 power plane을 평가할 수 없습니다."
            ),
            target_id=target_id,
            geometry_type=geometry_type,
            material_ref=material_ref,
            material_model=material_model,
            material_reflectivity=material_reflectivity,
            assumptions=assumptions,
            target_hit_tolerance_m=tolerance,
        )
    if reciprocal_geometry.target_id != target_id:
        return _not_evaluated(
            status="not_evaluated",
            reason="R1 reciprocal target와 configured R2 return target가 일치하지 않습니다.",
            target_id=target_id,
            geometry_type=geometry_type,
            material_ref=material_ref,
            material_model=material_model,
            material_reflectivity=material_reflectivity,
            assumptions=assumptions,
            target_hit_tolerance_m=tolerance,
        )

    path = reciprocal_geometry.path
    target_hit_residual = float(
        np.linalg.norm(path.target_hit_m - footprint.intersection.hit_center_m)
    )
    if target_hit_residual > tolerance:
        return _not_evaluated(
            status="not_evaluated",
            reason=(
                "R1 target hit와 visible footprint center가 일치하지 않습니다: "
                f"residual={target_hit_residual:.9g} m, tolerance={tolerance:.9g} m."
            ),
            target_id=target_id,
            geometry_type=geometry_type,
            material_ref=material_ref,
            material_model=material_model,
            material_reflectivity=material_reflectivity,
            assumptions=assumptions,
            target_hit_residual_m=target_hit_residual,
            target_hit_tolerance_m=tolerance,
        )
    scanner_id = str(path_config["scanner_element_id"])
    collimator_id = str(path_config["collimator_element_id"])
    scanner_element = _element_spec(scenario, scanner_id)
    collimator_element = _element_spec(scenario, collimator_id)
    scanner_ref = str(scanner_element["component_ref"])
    collimator_ref = str(collimator_element["component_ref"])
    scanner_optical = project.catalog[scanner_ref].data["optical"]
    collimator_optical = project.catalog[collimator_ref].data["optical"]

    mirror_aperture_status = (
        "pass"
        if path.mirror_hit.intersection.hit
        and path.mirror_hit.aperture_status == "pass"
        else "no_intersection"
        if not path.mirror_hit.intersection.hit
        else "miss"
    )
    collimator_hit = path.collimator_hit
    collimator_aperture_status = (
        "pass"
        if collimator_hit is not None
        and collimator_hit.intersection.hit
        and collimator_hit.aperture_status == "pass"
        else "no_intersection"
        if collimator_hit is None or not collimator_hit.intersection.hit
        else "miss"
    )
    fiber_hit = path.fiber_hit
    fiber_plane_status = (
        "pass"
        if fiber_hit is not None and fiber_hit.intersection.hit
        else "no_intersection"
    )
    actual_mirror_point = (
        path.mirror_hit.intersection.point_m
        if path.mirror_hit.intersection.point_m is not None
        else path.transmit_mirror_hit_m
    )
    result = estimate_reciprocal_return_power(
        power_on_target_w=footprint.estimated_power_on_target_w,
        target_reflectivity=material_reflectivity,
        target_normal=footprint.intersection.radiometric_normal,
        target_hit_m=path.target_hit_m,
        mirror_hit_m=actual_mirror_point,
        mirror_surface_normal=path.mirror_hit.frame.normal,
        mirror_clear_width_m=float(scanner_optical["clear_width_m"]),
        mirror_clear_height_m=float(scanner_optical["clear_height_m"]),
        mirror_aperture_status=mirror_aperture_status,
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=float(scanner_optical["power_reflectivity"]),
        collimator_aperture_status=collimator_aperture_status,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=float(
            collimator_optical["power_transmission"]
        ),
        fiber_plane_status=fiber_plane_status,
        target_model_source=(
            f"catalog material {material_ref} optical.hemispherical_reflectivity"
        ),
        mirror_model_source=f"catalog component {scanner_ref} optical",
        collimator_model_source=f"catalog component {collimator_ref} optical",
    )
    warnings = list(result.warnings)
    warnings.append(
        "Diffuse Lambertian return을 Gaussian single-mode field로 간주하지 않았습니다; R3 fiber overlap 전의 공간 파워 상한/reference입니다."
    )
    return ProjectReciprocalReturnPower(
        status=result.status,
        status_reason=result.termination_reason,
        target_id=target_id,
        geometry_type=geometry_type,
        material_ref=material_ref,
        material_model=material_model,
        material_reflectivity=material_reflectivity,
        target_hit_residual_m=target_hit_residual,
        target_hit_tolerance_m=tolerance,
        result=result,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )


__all__ = [
    "ProjectReciprocalReturnPower",
    "evaluate_project_reciprocal_return_power",
]
