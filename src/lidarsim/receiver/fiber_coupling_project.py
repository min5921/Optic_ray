"""Phase 2.4-R3 project adapter for a Gaussian alignment coupling proxy.

The R2 Lambertian result is a scalar radiometric power, not a coherent field.
This adapter therefore evaluates only a deterministic Gaussian mode-alignment
proxy and deliberately calls the pure overlap API without an input coherent
field.  The complex normalized overlap may be reported as a shape diagnostic,
but no coupled coherent field is created for downstream propagation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from lidarsim.geometry.transform import normalize_vector

from .fiber_coupling import (
    FiberCouplingResult,
    GaussianModeAtPlane,
    estimate_single_mode_fiber_coupling,
)
from .reciprocal_project import ProjectReciprocalReturn, RECIPROCAL_ARCHITECTURE
from .return_power_project import ProjectReciprocalReturnPower


SUPPORTED_MFD_DEFINITION = "gaussian_1e2_intensity"


def _complex_dict(value: complex) -> dict[str, float]:
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "magnitude": float(abs(value)),
    }


def _loss_db(input_power_w: float, output_power_w: float) -> float | None:
    if input_power_w <= 0.0 or output_power_w <= 0.0:
        return None
    value = -10.0 * math.log10(output_power_w / input_power_w)
    return 0.0 if abs(value) <= 1.0e-15 else value


def _pair(value: Any, *, name: str) -> tuple[float, float]:
    values = tuple(float(item) for item in value)
    if len(values) != 2 or not all(math.isfinite(item) for item in values):
        raise ValueError(f"{name}은 유한한 vec2여야 합니다.")
    return values[0], values[1]


def _vec3_tuple(value: np.ndarray) -> tuple[float, float, float]:
    return tuple(float(item) for item in value)


@dataclass(frozen=True, slots=True)
class FiberCouplingLedgerEntry:
    input_power_w: float
    coupling_loss_w: float
    output_power_w: float
    coupling_efficiency: float
    mechanism: str = "single_mode_gaussian_alignment_proxy"
    input_plane: str = "fiber_reference_plane"
    output_plane: str = "coupled_fiber_mode"

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_power_w": self.input_power_w,
            "coupling_loss_w": self.coupling_loss_w,
            "output_power_w": self.output_power_w,
            "coupling_efficiency": self.coupling_efficiency,
            "mechanism": self.mechanism,
            "input_plane": self.input_plane,
            "output_plane": self.output_plane,
        }


@dataclass(frozen=True, slots=True)
class ProjectFiberCoupling:
    status: str
    status_reason: str | None
    target_id: str | None
    fiber_element_id: str | None
    fiber_component_ref: str | None
    source_mfd_definition: str | None
    fiber_mfd_definition: str | None
    receive_mfd_definition: str | None
    fiber_mode_field_diameter_m: float | None
    receive_mode_field_diameter_m: float | None
    receive_mode_field_source: str | None
    receive_mode_waist_offset_m: float | None
    receive_axis_world: tuple[float, float, float] | None
    receive_x_axis_world: tuple[float, float, float] | None
    receive_y_axis_world: tuple[float, float, float] | None
    r1_lateral_offset_m: tuple[float, float] | None
    configured_lateral_offset_m: tuple[float, float] | None
    combined_lateral_offset_m: tuple[float, float] | None
    r1_angular_offset_rad: tuple[float, float] | None
    configured_angular_offset_rad: tuple[float, float] | None
    combined_angular_offset_rad: tuple[float, float] | None
    result: FiberCouplingResult | None
    fiber_plane_to_coupled_mode_loss_db: float | None
    target_to_fiber_coupled_link_loss_db: float | None
    power_ledger: tuple[FiberCouplingLedgerEntry, ...]
    maximum_energy_residual_w: float | None
    energy_tolerance_w: float
    energy_check_status: str
    coherent_field_status: str
    field_usable_for_coherent_propagation: bool
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = self.result
        return {
            "model": "gaussian_alignment_proxy",
            "status": self.status,
            "status_reason": self.status_reason,
            "target_id": self.target_id,
            "fiber_element_id": self.fiber_element_id,
            "fiber_component_ref": self.fiber_component_ref,
            "source_mfd_definition": self.source_mfd_definition,
            "fiber_mfd_definition": self.fiber_mfd_definition,
            "receive_mfd_definition": self.receive_mfd_definition,
            "fiber_mode_field_diameter_m": self.fiber_mode_field_diameter_m,
            "receive_mode_field_diameter_m": self.receive_mode_field_diameter_m,
            "receive_mode_field_source": self.receive_mode_field_source,
            "receive_mode_waist_offset_m": self.receive_mode_waist_offset_m,
            "receive_frame_convention": (
                "right_handed_x_cross_y_equals_receive_axis; receive_axis=-fiber_port_normal"
            ),
            "receive_axis_world": (
                None if self.receive_axis_world is None else list(self.receive_axis_world)
            ),
            "receive_x_axis_world": (
                None if self.receive_x_axis_world is None else list(self.receive_x_axis_world)
            ),
            "receive_y_axis_world": (
                None if self.receive_y_axis_world is None else list(self.receive_y_axis_world)
            ),
            "r1_lateral_offset_m": (
                None if self.r1_lateral_offset_m is None else list(self.r1_lateral_offset_m)
            ),
            "configured_lateral_offset_m": (
                None
                if self.configured_lateral_offset_m is None
                else list(self.configured_lateral_offset_m)
            ),
            "combined_lateral_offset_m": (
                None
                if self.combined_lateral_offset_m is None
                else list(self.combined_lateral_offset_m)
            ),
            "r1_angular_offset_rad": (
                None if self.r1_angular_offset_rad is None else list(self.r1_angular_offset_rad)
            ),
            "configured_angular_offset_rad": (
                None
                if self.configured_angular_offset_rad is None
                else list(self.configured_angular_offset_rad)
            ),
            "combined_angular_offset_rad": (
                None
                if self.combined_angular_offset_rad is None
                else list(self.combined_angular_offset_rad)
            ),
            "offset_combination_convention": (
                "combined_receive_mode_offset = R1_actual_residual + configured_offset "
                "for each receive-frame x/y axis"
            ),
            "overlap_model": None if result is None else result.model,
            "overlap_model_scope": None if result is None else result.model_scope,
            "input_power_interpretation": (
                None
                if result is None
                else "entire_r2_lambertian_scalar_power_assumed_carried_by_proxy_gaussian_mode"
            ),
            "overlap_api_input_interpretation": (
                None if result is None else result.input_power_interpretation
            ),
            "receive_mode": None if result is None else result.receive_mode.to_dict(),
            "fiber_mode": None if result is None else result.fiber_mode.to_dict(),
            "available_power_at_fiber_plane_w": (
                None if result is None else result.available_power_at_fiber_plane_w
            ),
            "normalized_field_overlap": (
                None if result is None else _complex_dict(result.normalized_field_overlap)
            ),
            "coupled_field_amplitude_sqrt_w": (
                None
                if result is None or result.coupled_field_amplitude_sqrt_w is None
                else _complex_dict(result.coupled_field_amplitude_sqrt_w)
            ),
            "fiber_coupling_efficiency": (
                None if result is None else result.fiber_coupling_efficiency
            ),
            "power_coupled_into_fiber_w": (
                None if result is None else result.power_coupled_into_fiber_w
            ),
            "fiber_plane_to_coupled_mode_loss_db": self.fiber_plane_to_coupled_mode_loss_db,
            "target_to_fiber_coupled_link_loss_db": self.target_to_fiber_coupled_link_loss_db,
            "power_ledger": [entry.to_dict() for entry in self.power_ledger],
            "maximum_energy_residual_w": self.maximum_energy_residual_w,
            "energy_tolerance_w": self.energy_tolerance_w,
            "energy_check_status": self.energy_check_status,
            "coherent_field_status": self.coherent_field_status,
            "field_usable_for_coherent_propagation": self.field_usable_for_coherent_propagation,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _unevaluated(
    *,
    status: str,
    reason: str,
    target_id: str | None,
    fiber_element_id: str | None,
    fiber_component_ref: str | None,
    source_mfd_definition: str | None,
    fiber_mfd_definition: str | None,
    receive_mfd_definition: str | None,
    fiber_mode_field_diameter_m: float | None,
    receive_mode_field_diameter_m: float | None,
    receive_mode_field_source: str | None,
    receive_mode_waist_offset_m: float | None,
    assumptions: tuple[str, ...],
    energy_tolerance_w: float,
) -> ProjectFiberCoupling:
    return ProjectFiberCoupling(
        status=status,
        status_reason=reason,
        target_id=target_id,
        fiber_element_id=fiber_element_id,
        fiber_component_ref=fiber_component_ref,
        source_mfd_definition=source_mfd_definition,
        fiber_mfd_definition=fiber_mfd_definition,
        receive_mfd_definition=receive_mfd_definition,
        fiber_mode_field_diameter_m=fiber_mode_field_diameter_m,
        receive_mode_field_diameter_m=receive_mode_field_diameter_m,
        receive_mode_field_source=receive_mode_field_source,
        receive_mode_waist_offset_m=receive_mode_waist_offset_m,
        receive_axis_world=None,
        receive_x_axis_world=None,
        receive_y_axis_world=None,
        r1_lateral_offset_m=None,
        configured_lateral_offset_m=None,
        combined_lateral_offset_m=None,
        r1_angular_offset_rad=None,
        configured_angular_offset_rad=None,
        combined_angular_offset_rad=None,
        result=None,
        fiber_plane_to_coupled_mode_loss_db=None,
        target_to_fiber_coupled_link_loss_db=None,
        power_ledger=(),
        maximum_energy_residual_w=None,
        energy_tolerance_w=energy_tolerance_w,
        energy_check_status="not_evaluated",
        coherent_field_status="not_provided",
        field_usable_for_coherent_propagation=False,
        assumptions=assumptions,
        warnings=(reason,),
    )


def _element_spec(scenario: Mapping[str, Any], element_id: str) -> Mapping[str, Any]:
    element = next(
        (
            item
            for item in scenario["optical_assembly"]["elements"]
            if str(item["id"]) == element_id
        ),
        None,
    )
    if element is None:
        raise ValueError(f"존재하지 않는 fiber return element입니다: {element_id!r}")
    return element


def evaluate_project_fiber_coupling(
    project: Any,
    reciprocal_geometry: ProjectReciprocalReturn,
    reciprocal_power: ProjectReciprocalReturnPower,
    *,
    energy_tolerance_w: float = 1.0e-15,
) -> ProjectFiberCoupling:
    """Evaluate the R3 Gaussian alignment proxy from actual R1/R2 planes."""

    tolerance = float(energy_tolerance_w)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("energy_tolerance_w는 0보다 큰 유한한 값이어야 합니다.")
    assumptions = (
        "R3 available input power는 R2 power_at_fiber_plane_w를 그대로 사용합니다.",
        "Diffuse Lambertian radiometric power 전체를 deterministic Gaussian receive mode로 가정한 analytical upper-bound/alignment proxy입니다.",
        "Fiber receive frame은 axis=-fiber port normal, x=fiber port x, y=cross(axis,x)의 오른손 좌표계입니다.",
        "R1 actual x/y lateral·angular residual과 configured offset은 같은 receive frame에서 성분별로 더합니다.",
        "Fiber mode는 catalog MFD의 planar waist이며 receive proxy mode만 configured waist offset을 적용합니다.",
        "Radiometric adapter는 input coherent field를 제공하지 않으므로 normalized overlap 외의 coherent field를 생성하거나 R4로 전달하지 않습니다.",
        "Polarization, aberration, diffuse spatial-mode decomposition, speckle과 measured mode profile은 계산하지 않습니다.",
    )
    scenario = project.active_scenario
    receiver = scenario["receiver"]
    if str(receiver["architecture"]) != RECIPROCAL_ARCHITECTURE:
        return _unevaluated(
            status="not_evaluated",
            reason="reciprocal_single_mode_fiber architecture가 아니므로 R3를 계산하지 않았습니다.",
            target_id=None,
            fiber_element_id=None,
            fiber_component_ref=None,
            source_mfd_definition=None,
            fiber_mfd_definition=None,
            receive_mfd_definition=None,
            fiber_mode_field_diameter_m=None,
            receive_mode_field_diameter_m=None,
            receive_mode_field_source=None,
            receive_mode_waist_offset_m=None,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )

    path_config = receiver["return_path"]
    fiber_element_id = str(path_config["fiber_element_id"])
    fiber_element = _element_spec(scenario, fiber_element_id)
    fiber_component_ref = str(fiber_element["component_ref"])
    fiber_optical = project.catalog[fiber_component_ref].data["optical"]
    source = scenario["source"]
    coupling_config = receiver["fiber_coupling"]
    source_definition = str(source.get("mode_field_diameter_definition", ""))
    fiber_definition = str(fiber_optical.get("mode_field_diameter_definition", ""))
    receive_definition = str(
        coupling_config.get("receive_mode_field_diameter_definition", fiber_definition)
    )
    fiber_mfd = float(fiber_optical["mode_field_diameter_m"])
    override_present = "receive_mode_field_diameter_m" in coupling_config
    receive_mfd = float(
        coupling_config.get("receive_mode_field_diameter_m", fiber_mfd)
    )
    receive_mfd_source = (
        "receiver.fiber_coupling.receive_mode_field_diameter_m"
        if override_present
        else f"catalog component {fiber_component_ref} optical.mode_field_diameter_m"
    )
    waist_offset = float(coupling_config.get("receive_mode_waist_offset_m", 0.0))

    if reciprocal_power.result is None:
        return _unevaluated(
            status="not_evaluated",
            reason="R2 power_at_fiber_plane_w가 없어 R3 coupling을 계산하지 않았습니다.",
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )
    if reciprocal_power.result.energy_check_status != "pass":
        return _unevaluated(
            status="fail",
            reason="R2 return power ledger energy check가 pass가 아니므로 R3로 전파하지 않았습니다.",
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )
    if reciprocal_geometry.path is None or reciprocal_geometry.path.fiber_hit is None:
        return _unevaluated(
            status="not_evaluated",
            reason="R1 actual fiber reference-plane hit가 없어 R3 coupling을 계산하지 않았습니다.",
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )
    if not reciprocal_geometry.path.fiber_hit.intersection.hit:
        return _unevaluated(
            status="not_evaluated",
            reason="R1 fiber reference-plane intersection이 miss이므로 R3 coupling을 계산하지 않았습니다.",
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )
    definitions = (source_definition, fiber_definition, receive_definition)
    if any(value != SUPPORTED_MFD_DEFINITION for value in definitions):
        return _unevaluated(
            status="unsupported_mfd_definition",
            reason=(
                "R3는 source/fiber/receive MFD definition이 모두 "
                f"{SUPPORTED_MFD_DEFINITION!r}일 때만 지원합니다: {definitions!r}."
            ),
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )

    path = reciprocal_geometry.path
    fiber_hit = path.fiber_hit
    assert fiber_hit is not None
    assert fiber_hit.intersection.point_m is not None
    if path.fiber_bound_direction is None:
        return _unevaluated(
            status="not_evaluated",
            reason="R1 fiber-bound direction이 없어 angular coupling residual을 계산하지 않았습니다.",
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )

    frame = fiber_hit.frame
    receive_axis = normalize_vector(-frame.normal, name="fiber receive axis")
    receive_x = normalize_vector(frame.x_axis, name="fiber receive x axis")
    receive_y = normalize_vector(
        np.cross(receive_axis, receive_x),
        name="fiber receive y axis",
    )
    hit_delta = fiber_hit.intersection.point_m - frame.origin_m
    r1_lateral = (
        float(np.dot(hit_delta, receive_x)),
        float(np.dot(hit_delta, receive_y)),
    )
    fiber_direction = normalize_vector(
        path.fiber_bound_direction,
        name="fiber-bound direction",
    )
    axial = float(np.dot(fiber_direction, receive_axis))
    if axial <= 1.0e-12:
        return _unevaluated(
            status="not_evaluated",
            reason="Fiber-bound ray가 receive axis의 forward half-space를 향하지 않습니다.",
            target_id=reciprocal_power.target_id,
            fiber_element_id=fiber_element_id,
            fiber_component_ref=fiber_component_ref,
            source_mfd_definition=source_definition,
            fiber_mfd_definition=fiber_definition,
            receive_mfd_definition=receive_definition,
            fiber_mode_field_diameter_m=fiber_mfd,
            receive_mode_field_diameter_m=receive_mfd,
            receive_mode_field_source=receive_mfd_source,
            receive_mode_waist_offset_m=waist_offset,
            assumptions=assumptions,
            energy_tolerance_w=tolerance,
        )
    r1_angular = (
        math.atan2(float(np.dot(fiber_direction, receive_x)), axial),
        math.atan2(float(np.dot(fiber_direction, receive_y)), axial),
    )
    configured_lateral = _pair(
        coupling_config["lateral_offset_m"],
        name="receiver.fiber_coupling.lateral_offset_m",
    )
    configured_angular = _pair(
        coupling_config["angular_offset_rad"],
        name="receiver.fiber_coupling.angular_offset_rad",
    )
    combined_lateral = tuple(
        actual + configured
        for actual, configured in zip(r1_lateral, configured_lateral, strict=True)
    )
    combined_angular = tuple(
        actual + configured
        for actual, configured in zip(r1_angular, configured_angular, strict=True)
    )
    wavelength = float(source["wavelength_m"])
    fiber_mode = GaussianModeAtPlane.from_mode_field_diameter(fiber_mfd)
    receive_mode = GaussianModeAtPlane.from_waist_at_plane(
        0.5 * receive_mfd,
        wavelength_m=wavelength,
        distance_from_waist_m=waist_offset,
        center_offset_m=combined_lateral,
        angular_offset_rad=combined_angular,
    )
    available_power = reciprocal_power.result.power_at_fiber_plane_w
    result = estimate_single_mode_fiber_coupling(
        available_power_at_fiber_plane_w=available_power,
        wavelength_m=wavelength,
        receive_mode=receive_mode,
        fiber_mode=fiber_mode,
        input_field_amplitude_sqrt_w=None,
    )
    coupled_power = result.power_coupled_into_fiber_w
    ledger_entry = FiberCouplingLedgerEntry(
        input_power_w=available_power,
        coupling_loss_w=available_power - coupled_power,
        output_power_w=coupled_power,
        coupling_efficiency=result.fiber_coupling_efficiency,
    )
    residual = abs(
        ledger_entry.input_power_w
        - ledger_entry.coupling_loss_w
        - ledger_entry.output_power_w
    )
    energy_status = "pass" if residual <= tolerance else "fail"
    target_power = reciprocal_power.result.power_on_target_w
    warnings = list(result.warnings)
    warnings.append(
        "R3 eta와 coupled power는 diffuse Lambertian return을 deterministic Gaussian mode로 둔 optimistic analytical upper-bound/reference입니다."
    )
    warnings.append(
        "normalized_field_overlap은 alignment 진단값이며 input coherent field가 없으므로 coupled field를 R4 또는 coherent FMCW에 전달하면 안 됩니다."
    )
    status = "fail" if energy_status == "fail" else result.status
    return ProjectFiberCoupling(
        status=status,
        status_reason=None,
        target_id=reciprocal_power.target_id,
        fiber_element_id=fiber_element_id,
        fiber_component_ref=fiber_component_ref,
        source_mfd_definition=source_definition,
        fiber_mfd_definition=fiber_definition,
        receive_mfd_definition=receive_definition,
        fiber_mode_field_diameter_m=fiber_mfd,
        receive_mode_field_diameter_m=receive_mfd,
        receive_mode_field_source=receive_mfd_source,
        receive_mode_waist_offset_m=waist_offset,
        receive_axis_world=_vec3_tuple(receive_axis),
        receive_x_axis_world=_vec3_tuple(receive_x),
        receive_y_axis_world=_vec3_tuple(receive_y),
        r1_lateral_offset_m=r1_lateral,
        configured_lateral_offset_m=configured_lateral,
        combined_lateral_offset_m=combined_lateral,
        r1_angular_offset_rad=r1_angular,
        configured_angular_offset_rad=configured_angular,
        combined_angular_offset_rad=combined_angular,
        result=result,
        fiber_plane_to_coupled_mode_loss_db=_loss_db(
            available_power,
            coupled_power,
        ),
        target_to_fiber_coupled_link_loss_db=_loss_db(
            target_power,
            coupled_power,
        ),
        power_ledger=(ledger_entry,),
        maximum_energy_residual_w=residual,
        energy_tolerance_w=tolerance,
        energy_check_status=energy_status,
        coherent_field_status=result.coherent_field_status,
        field_usable_for_coherent_propagation=False,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )


__all__ = [
    "FiberCouplingLedgerEntry",
    "ProjectFiberCoupling",
    "SUPPORTED_MFD_DEFINITION",
    "evaluate_project_fiber_coupling",
]
