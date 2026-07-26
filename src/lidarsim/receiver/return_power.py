"""Phase 2.4-R2 reciprocal-path analytical return-power ledger.

This module deliberately models optical *power*, not a reverse Gaussian beam or
coherent field.  A small Lambertian target footprint illuminates the projected
scanner-mirror clear area, after which scalar aperture and component
transmissions are applied in physical traversal order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from lidarsim.geometry.transform import normalize_vector


_APERTURE_STATUSES = frozenset({"pass", "miss", "no_intersection", "not_checked"})


def _nonnegative(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name}은 0 이상의 유한한 값이어야 합니다.")
    return result


def _positive(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 유한한 값이어야 합니다.")
    return result


def _fraction(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name}은 0 이상 1 이하의 유한한 값이어야 합니다.")
    return result


def _point(value: Iterable[float], *, name: str) -> np.ndarray:
    result = np.array(value, dtype=np.float64, copy=True)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    result.setflags(write=False)
    return result


def _model_source(value: str, *, name: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{name}은 빈 문자열이어서는 안 됩니다.")
    return result


def _aperture_status(value: str, *, name: str) -> str:
    result = str(value)
    if result not in _APERTURE_STATUSES:
        allowed = ", ".join(sorted(_APERTURE_STATUSES))
        raise ValueError(f"{name}은 다음 중 하나여야 합니다: {allowed}.")
    return result


def _loss_db(input_power_w: float, output_power_w: float) -> float | None:
    if input_power_w <= 0.0 or output_power_w <= 0.0:
        return None
    value = -10.0 * math.log10(output_power_w / input_power_w)
    return 0.0 if abs(value) <= 1.0e-15 else value


@dataclass(frozen=True, slots=True)
class ReturnPowerLedgerEntry:
    """One scalar-power transition between named reciprocal-path planes."""

    input_power_w: float
    loss_w: float
    output_power_w: float
    mechanism: str
    plane: str
    model_source: str
    transmission_fraction: float
    status: str
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_power_w": self.input_power_w,
            "loss_w": self.loss_w,
            "output_power_w": self.output_power_w,
            "mechanism": self.mechanism,
            "plane": self.plane,
            "model_source": self.model_source,
            "transmission_fraction": self.transmission_fraction,
            "status": self.status,
            "warning": self.warning,
        }


@dataclass(frozen=True, slots=True)
class ReciprocalReturnPowerResult:
    """Small-footprint Lambertian power propagated to the fiber reference plane."""

    status: str
    termination_reason: str | None
    power_on_target_w: float
    target_reflectivity: float
    target_to_mirror_distance_m: float
    target_to_mirror_cosine: float
    mirror_incidence_cosine: float
    mirror_clear_area_m2: float
    projected_mirror_area_m2: float
    raw_target_to_mirror_fraction: float
    target_to_mirror_fraction: float
    mirror_aperture_status: str
    collimator_aperture_status: str
    fiber_plane_status: str
    power_at_return_mirror_w: float
    power_after_return_mirror_aperture_w: float
    power_after_return_mirror_w: float
    power_at_return_collimator_w: float
    power_after_return_collimator_aperture_w: float
    power_after_return_collimator_w: float
    power_at_fiber_plane_w: float
    target_to_fiber_plane_link_loss_db: float | None
    power_ledger: tuple[ReturnPowerLedgerEntry, ...]
    maximum_energy_residual_w: float
    energy_tolerance_w: float
    energy_check_status: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "lambertian_small_footprint_reciprocal_power_ledger",
            "status": self.status,
            "termination_reason": self.termination_reason,
            "power_on_target_w": self.power_on_target_w,
            "target_reflectivity": self.target_reflectivity,
            "target_to_mirror_distance_m": self.target_to_mirror_distance_m,
            "target_to_mirror_cosine": self.target_to_mirror_cosine,
            "mirror_incidence_cosine": self.mirror_incidence_cosine,
            "mirror_clear_area_m2": self.mirror_clear_area_m2,
            "projected_mirror_area_m2": self.projected_mirror_area_m2,
            "raw_target_to_mirror_fraction": self.raw_target_to_mirror_fraction,
            "target_to_mirror_fraction": self.target_to_mirror_fraction,
            "mirror_aperture_status": self.mirror_aperture_status,
            "collimator_aperture_status": self.collimator_aperture_status,
            "fiber_plane_status": self.fiber_plane_status,
            "power_at_return_mirror_w": self.power_at_return_mirror_w,
            "power_after_return_mirror_aperture_w": (
                self.power_after_return_mirror_aperture_w
            ),
            "power_after_return_mirror_w": self.power_after_return_mirror_w,
            "power_at_return_collimator_w": self.power_at_return_collimator_w,
            "power_after_return_collimator_aperture_w": (
                self.power_after_return_collimator_aperture_w
            ),
            "power_after_return_collimator_w": self.power_after_return_collimator_w,
            "power_at_fiber_plane_w": self.power_at_fiber_plane_w,
            "target_to_fiber_plane_link_loss_db": (
                self.target_to_fiber_plane_link_loss_db
            ),
            "power_ledger": [entry.to_dict() for entry in self.power_ledger],
            "maximum_energy_residual_w": self.maximum_energy_residual_w,
            "energy_tolerance_w": self.energy_tolerance_w,
            "energy_check_status": self.energy_check_status,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _ledger_entry(
    input_power_w: float,
    transmission_fraction: float,
    *,
    mechanism: str,
    plane: str,
    model_source: str,
    status: str = "applied",
    warning: str | None = None,
) -> ReturnPowerLedgerEntry:
    output_power = input_power_w * transmission_fraction
    return ReturnPowerLedgerEntry(
        input_power_w=input_power_w,
        loss_w=input_power_w - output_power,
        output_power_w=output_power,
        mechanism=mechanism,
        plane=plane,
        model_source=model_source,
        transmission_fraction=transmission_fraction,
        status=status,
        warning=warning,
    )


def _energy_residual(
    ledger: tuple[ReturnPowerLedgerEntry, ...],
) -> float:
    residuals: list[float] = []
    previous_output: float | None = None
    for entry in ledger:
        if previous_output is not None:
            residuals.append(abs(entry.input_power_w - previous_output))
        residuals.append(
            abs(entry.input_power_w - entry.loss_w - entry.output_power_w)
        )
        previous_output = entry.output_power_w
    return max(residuals, default=0.0)


def estimate_reciprocal_return_power(
    *,
    power_on_target_w: float,
    target_reflectivity: float,
    target_normal: Iterable[float],
    target_hit_m: Iterable[float],
    mirror_hit_m: Iterable[float],
    mirror_surface_normal: Iterable[float],
    mirror_clear_width_m: float,
    mirror_clear_height_m: float,
    mirror_aperture_status: str,
    mirror_aperture_transmission_fraction: float = 1.0,
    mirror_power_reflectivity: float = 1.0,
    collimator_aperture_status: str = "pass",
    collimator_aperture_transmission_fraction: float = 1.0,
    reverse_collimator_transmission: float = 1.0,
    fiber_plane_status: str = "pass",
    target_model_source: str = "material.optical.hemispherical_reflectivity",
    mirror_model_source: str = "scanner_mirror.optical",
    collimator_model_source: str = "collimator.optical",
    energy_tolerance_w: float = 1.0e-15,
) -> ReciprocalReturnPowerResult:
    """Estimate scalar return power from a small Lambertian patch.

    The first transition uses

    ``P_target * rho/pi * cos(theta_target) * A_mirror_projected / R**2``.

    This is a small-footprint/small-aperture analytical reference, not an exact
    spatial aperture integral.  A center-ray aperture status other than
    ``"pass"`` rejects all power at that aperture.  A configured transmission
    fraction of zero is valid and is retained as a zero-power ledger entry.
    """

    target_power = _nonnegative(power_on_target_w, name="power_on_target_w")
    reflectivity = _fraction(target_reflectivity, name="target_reflectivity")
    mirror_width = _positive(mirror_clear_width_m, name="mirror_clear_width_m")
    mirror_height = _positive(mirror_clear_height_m, name="mirror_clear_height_m")
    mirror_aperture = _aperture_status(
        mirror_aperture_status,
        name="mirror_aperture_status",
    )
    collimator_aperture = _aperture_status(
        collimator_aperture_status,
        name="collimator_aperture_status",
    )
    fiber_plane = _aperture_status(
        fiber_plane_status,
        name="fiber_plane_status",
    )
    mirror_aperture_fraction = _fraction(
        mirror_aperture_transmission_fraction,
        name="mirror_aperture_transmission_fraction",
    )
    mirror_reflectivity = _fraction(
        mirror_power_reflectivity,
        name="mirror_power_reflectivity",
    )
    collimator_aperture_fraction = _fraction(
        collimator_aperture_transmission_fraction,
        name="collimator_aperture_transmission_fraction",
    )
    collimator_transmission = _fraction(
        reverse_collimator_transmission,
        name="reverse_collimator_transmission",
    )
    tolerance = _positive(energy_tolerance_w, name="energy_tolerance_w")
    target_source = _model_source(target_model_source, name="target_model_source")
    mirror_source = _model_source(mirror_model_source, name="mirror_model_source")
    collimator_source = _model_source(
        collimator_model_source,
        name="collimator_model_source",
    )

    target_point = _point(target_hit_m, name="target_hit_m")
    mirror_point = _point(mirror_hit_m, name="mirror_hit_m")
    direction = mirror_point - target_point
    distance = float(np.linalg.norm(direction))
    if not math.isfinite(distance) or distance <= 0.0:
        raise ValueError("target_hit_m과 mirror_hit_m은 서로 다른 점이어야 합니다.")
    direction = normalize_vector(direction, name="target-to-mirror direction")
    normal_target = normalize_vector(target_normal, name="target_normal")
    normal_mirror = normalize_vector(
        mirror_surface_normal,
        name="mirror_surface_normal",
    )
    target_cosine = min(
        max(float(np.dot(normal_target, direction)), 0.0),
        1.0,
    )
    mirror_cosine = min(abs(float(np.dot(normal_mirror, direction))), 1.0)
    clear_area = mirror_width * mirror_height
    projected_area = clear_area * mirror_cosine
    raw_acceptance = (
        reflectivity
        / math.pi
        * target_cosine
        * projected_area
        / (distance * distance)
    )
    acceptance = min(max(raw_acceptance, 0.0), 1.0)
    warnings: list[str] = []
    if raw_acceptance > 1.0:
        warnings.append(
            "Small-aperture Lambertian approximation이 1을 초과해 energy 보존을 위해 "
            "target-to-mirror fraction을 1로 제한했습니다. 정확한 solid-angle 적분이 필요합니다."
        )
    if target_cosine <= 0.0:
        warnings.append(
            "Target radiometric normal이 mirror 방향을 향하지 않아 Lambertian return이 0 W입니다."
        )
    if mirror_cosine <= 1.0e-12:
        warnings.append(
            "Mirror projected area가 0에 가까운 grazing geometry이므로 return이 0 W입니다."
        )

    target_entry = _ledger_entry(
        target_power,
        acceptance,
        mechanism="lambertian_target_to_mirror_acceptance",
        plane="return_mirror_incident",
        model_source=target_source,
        warning=(
            "Small-footprint/small-aperture approximation; exact spatial solid-angle integral을 적용하지 않음."
        ),
    )

    mirror_pass = mirror_aperture == "pass"
    effective_mirror_aperture_fraction = (
        mirror_aperture_fraction if mirror_pass else 0.0
    )
    mirror_aperture_warning = None
    if not mirror_pass:
        mirror_aperture_warning = (
            f"Center ray mirror aperture status가 {mirror_aperture!r}이므로 return power를 0 W로 종료합니다."
        )
        warnings.append(mirror_aperture_warning)
    mirror_aperture_entry = _ledger_entry(
        target_entry.output_power_w,
        effective_mirror_aperture_fraction,
        mechanism="return_mirror_aperture",
        plane="return_mirror_after_aperture",
        model_source=mirror_source,
        status="applied" if mirror_pass else "rejected",
        warning=mirror_aperture_warning,
    )
    mirror_reflection_entry = _ledger_entry(
        mirror_aperture_entry.output_power_w,
        mirror_reflectivity,
        mechanism="return_mirror_reflectivity",
        plane="return_mirror_reflected",
        model_source=mirror_source,
    )

    collimator_pass = collimator_aperture == "pass"
    effective_collimator_aperture_fraction = (
        collimator_aperture_fraction if collimator_pass else 0.0
    )
    collimator_aperture_warning = None
    if not collimator_pass:
        collimator_aperture_warning = (
            f"Center ray collimator aperture status가 {collimator_aperture!r}이므로 return power를 0 W로 종료합니다."
        )
        warnings.append(collimator_aperture_warning)
    collimator_aperture_entry = _ledger_entry(
        mirror_reflection_entry.output_power_w,
        effective_collimator_aperture_fraction,
        mechanism="return_collimator_aperture",
        plane="return_collimator_after_aperture",
        model_source=collimator_source,
        status="applied" if collimator_pass else "rejected",
        warning=collimator_aperture_warning,
    )
    collimator_transmission_entry = _ledger_entry(
        collimator_aperture_entry.output_power_w,
        collimator_transmission,
        mechanism="reverse_collimator_transmission",
        plane="return_collimator_transmitted",
        model_source=collimator_source,
    )
    fiber_pass = fiber_plane == "pass"
    fiber_plane_warning = None
    if not fiber_pass:
        fiber_plane_warning = (
            f"Fiber reference-plane geometry status가 {fiber_plane!r}이므로 "
            "return power를 0 W로 종료합니다."
        )
        warnings.append(fiber_plane_warning)
    fiber_plane_entry = _ledger_entry(
        collimator_transmission_entry.output_power_w,
        1.0 if fiber_pass else 0.0,
        mechanism="fiber_reference_plane_geometry",
        plane="fiber_reference_plane",
        model_source="receiver.return_path fiber reference-plane intersection",
        status="applied" if fiber_pass else "rejected",
        warning=fiber_plane_warning,
    )
    ledger = (
        target_entry,
        mirror_aperture_entry,
        mirror_reflection_entry,
        collimator_aperture_entry,
        collimator_transmission_entry,
        fiber_plane_entry,
    )
    residual = _energy_residual(ledger)
    energy_status = "pass" if residual <= tolerance else "fail"
    final_power = fiber_plane_entry.output_power_w
    link_loss = (
        None
        if target_power <= 0.0 or final_power <= 0.0
        else _loss_db(target_power, final_power)
    )
    termination_reason: str | None = None
    if not mirror_pass:
        termination_reason = "return_mirror_aperture_rejected"
    elif not collimator_pass:
        termination_reason = "return_collimator_aperture_rejected"
    elif not fiber_pass:
        termination_reason = "fiber_reference_plane_geometry_rejected"
    status = (
        "fail"
        if energy_status == "fail"
        else "terminated"
        if termination_reason is not None
        else "pass"
        if final_power > 0.0
        else "zero_power"
    )

    return ReciprocalReturnPowerResult(
        status=status,
        termination_reason=termination_reason,
        power_on_target_w=target_power,
        target_reflectivity=reflectivity,
        target_to_mirror_distance_m=distance,
        target_to_mirror_cosine=target_cosine,
        mirror_incidence_cosine=mirror_cosine,
        mirror_clear_area_m2=clear_area,
        projected_mirror_area_m2=projected_area,
        raw_target_to_mirror_fraction=raw_acceptance,
        target_to_mirror_fraction=acceptance,
        mirror_aperture_status=mirror_aperture,
        collimator_aperture_status=collimator_aperture,
        fiber_plane_status=fiber_plane,
        power_at_return_mirror_w=target_entry.output_power_w,
        power_after_return_mirror_aperture_w=mirror_aperture_entry.output_power_w,
        power_after_return_mirror_w=mirror_reflection_entry.output_power_w,
        power_at_return_collimator_w=mirror_reflection_entry.output_power_w,
        power_after_return_collimator_aperture_w=(
            collimator_aperture_entry.output_power_w
        ),
        power_after_return_collimator_w=collimator_transmission_entry.output_power_w,
        power_at_fiber_plane_w=final_power,
        target_to_fiber_plane_link_loss_db=link_loss,
        power_ledger=ledger,
        maximum_energy_residual_w=residual,
        energy_tolerance_w=tolerance,
        energy_check_status=energy_status,
        assumptions=(
            "Target footprint을 하나의 작은 Lambertian patch로 간주합니다.",
            "Target-to-mirror power는 rho/pi * cos(theta_target) * projected_mirror_area/R^2 근사를 사용합니다.",
            "Mirror와 collimator aperture는 center-ray pass/miss와 설정된 scalar fractional transmission으로 평가합니다.",
            "Fiber reference plane은 actual center-ray intersection pass/miss로 평가하며 miss 뒤에 power를 재중심화하지 않습니다.",
            "Exact spatial aperture/solid-angle integral, mesh 전체 footprint, visibility occlusion과 BRDF 적분은 계산하지 않습니다.",
            "반환광을 단일 Gaussian beam이나 coherent field로 재해석하지 않습니다.",
            "Fiber mode overlap, duplexer, detector, speckle과 coherent FMCW는 이 결과에 포함하지 않습니다.",
        ),
        warnings=tuple(warnings),
    )


__all__ = [
    "ReciprocalReturnPowerResult",
    "ReturnPowerLedgerEntry",
    "estimate_reciprocal_return_power",
]
