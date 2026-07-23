"""First analytical Lambertian receiver-return estimate for Phase 2.3."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from lidarsim.geometry.transform import normalize_vector
from lidarsim.scene import TargetFootprint


def _vec3(value: Iterable[float], *, name: str) -> np.ndarray:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    array.setflags(write=False)
    return array


def _safe_loss_db(reference_power_w: float, received_power_w: float) -> float | None:
    if reference_power_w <= 0.0 or received_power_w <= 0.0:
        return None
    return -10.0 * math.log10(received_power_w / reference_power_w)


@dataclass(frozen=True, slots=True)
class ReceiverReturn:
    """Small-footprint Lambertian virtual-aperture return report."""

    target_id: str
    material_ref: str
    material_model: str
    material_reflectivity: float | None
    receiver_architecture: str
    receiver_direction_input: tuple[float, float, float]
    receiver_direction: tuple[float, float, float]
    receiver_aperture_area_m2: float
    receiver_distance_m: float | None
    receiver_fov_status: str
    receiver_axis_angle_rad: float | None
    receiver_axis_cosine: float | None
    target_to_receiver_cosine: float | None
    estimated_power_on_target_w: float
    estimated_received_power_w: float
    link_loss_db: float | None
    status: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "material_ref": self.material_ref,
            "material_model": self.material_model,
            "material_reflectivity": self.material_reflectivity,
            "receiver_architecture": self.receiver_architecture,
            "receiver_direction_input": list(self.receiver_direction_input),
            "receiver_direction": list(self.receiver_direction),
            "receiver_aperture_area_m2": self.receiver_aperture_area_m2,
            "receiver_distance_m": self.receiver_distance_m,
            "receiver_fov_status": self.receiver_fov_status,
            "receiver_axis_angle_rad": self.receiver_axis_angle_rad,
            "receiver_axis_cosine": self.receiver_axis_cosine,
            "target_to_receiver_cosine": self.target_to_receiver_cosine,
            "estimated_power_on_target_w": self.estimated_power_on_target_w,
            "estimated_received_power_w": self.estimated_received_power_w,
            "link_loss_db": self.link_loss_db,
            "status": self.status,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def estimate_lambertian_receiver_return(
    *,
    footprint: TargetFootprint,
    material: Any,
    receiver: Any,
) -> ReceiverReturn:
    """One rectangle-plane Lambertian target의 virtual-aperture power를 추정한다."""

    architecture = str(receiver["architecture"])
    aperture_diameter = float(receiver["aperture_diameter_m"])
    if aperture_diameter <= 0.0 or not math.isfinite(aperture_diameter):
        raise ValueError("receiver.aperture_diameter_m은 0보다 큰 유한한 값이어야 합니다.")
    aperture_area = math.pi * (0.5 * aperture_diameter) ** 2
    receiver_direction_input_array = _vec3(
        receiver["direction"],
        name="receiver.direction input",
    )
    receiver_direction = normalize_vector(
        receiver_direction_input_array,
        name="receiver.direction",
    )
    receiver_direction_input = tuple(
        float(value) for value in receiver_direction_input_array
    )
    receiver_direction_resolved = tuple(float(value) for value in receiver_direction)
    assumptions = [
        "Small-footprint Lambertian analytical approximation입니다.",
        "Receiver는 virtual aperture이며 동일 scanner/collimator의 reverse path, single-mode fiber coupling, detector와 duplexer를 생략합니다.",
        "estimated_received_power_w는 virtual aperture plane의 분석용 추정값이며 fiber-coupled power가 아닙니다.",
        "Occlusion, atmospheric loss, speckle, coherent field, shot noise와 detector saturation은 계산하지 않습니다.",
        "Receiver aperture projected solid angle은 A_rx*cos(theta_rx)/R^2로 근사합니다.",
    ]
    warnings = list(footprint.warnings)
    material_model = str(material["optical"].get("model", "unknown"))
    reflectivity: float | None = None

    if architecture not in {"virtual_monostatic", "virtual_aperture"}:
        warnings.append(f"지원하지 않는 receiver architecture입니다: {architecture!r}")
        return ReceiverReturn(
            target_id=footprint.target_id,
            material_ref=footprint.material_ref,
            material_model=material_model,
            material_reflectivity=None,
            receiver_architecture=architecture,
            receiver_direction_input=receiver_direction_input,
            receiver_direction=receiver_direction_resolved,
            receiver_aperture_area_m2=aperture_area,
            receiver_distance_m=None,
            receiver_fov_status="not_evaluated",
            receiver_axis_angle_rad=None,
            receiver_axis_cosine=None,
            target_to_receiver_cosine=None,
            estimated_power_on_target_w=footprint.estimated_power_on_target_w,
            estimated_received_power_w=0.0,
            link_loss_db=None,
            status="unsupported_receiver_architecture",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    if not footprint.hit or footprint.intersection.hit_center_m is None:
        return ReceiverReturn(
            target_id=footprint.target_id,
            material_ref=footprint.material_ref,
            material_model=material_model,
            material_reflectivity=None,
            receiver_architecture=architecture,
            receiver_direction_input=receiver_direction_input,
            receiver_direction=receiver_direction_resolved,
            receiver_aperture_area_m2=aperture_area,
            receiver_distance_m=None,
            receiver_fov_status="no_target_hit",
            receiver_axis_angle_rad=None,
            receiver_axis_cosine=None,
            target_to_receiver_cosine=None,
            estimated_power_on_target_w=0.0,
            estimated_received_power_w=0.0,
            link_loss_db=None,
            status="no_target_hit",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    if not footprint.contributes_to_scene_energy and footprint.visibility_status.startswith(
        "occluded"
    ):
        warnings.append(
            f"Target은 {footprint.occluded_by_target_id!r} 뒤에 가려져 receiver return에 "
            "기여하지 않습니다."
        )
        return ReceiverReturn(
            target_id=footprint.target_id,
            material_ref=footprint.material_ref,
            material_model=material_model,
            material_reflectivity=None,
            receiver_architecture=architecture,
            receiver_direction_input=receiver_direction_input,
            receiver_direction=receiver_direction_resolved,
            receiver_aperture_area_m2=aperture_area,
            receiver_distance_m=None,
            receiver_fov_status="occluded",
            receiver_axis_angle_rad=None,
            receiver_axis_cosine=None,
            target_to_receiver_cosine=None,
            estimated_power_on_target_w=0.0,
            estimated_received_power_w=0.0,
            link_loss_db=None,
            status="occluded_by_nearer_target",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    if material_model != "lambertian":
        warnings.append(f"지원하지 않는 material optical.model입니다: {material_model!r}")
        return ReceiverReturn(
            target_id=footprint.target_id,
            material_ref=footprint.material_ref,
            material_model=material_model,
            material_reflectivity=None,
            receiver_architecture=architecture,
            receiver_direction_input=receiver_direction_input,
            receiver_direction=receiver_direction_resolved,
            receiver_aperture_area_m2=aperture_area,
            receiver_distance_m=None,
            receiver_fov_status="not_evaluated",
            receiver_axis_angle_rad=None,
            receiver_axis_cosine=None,
            target_to_receiver_cosine=None,
            estimated_power_on_target_w=footprint.estimated_power_on_target_w,
            estimated_received_power_w=0.0,
            link_loss_db=None,
            status="unsupported_material_model",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    reflectivity = float(material["optical"]["hemispherical_reflectivity"])
    receiver_position = _vec3(receiver["position_m"], name="receiver.position_m")
    hit = footprint.intersection.hit_center_m
    target_to_receiver = receiver_position - hit
    distance = float(np.linalg.norm(target_to_receiver))
    if distance <= 1e-15:
        warnings.append("Receiver position이 target hit point와 같습니다.")
        return ReceiverReturn(
            target_id=footprint.target_id,
            material_ref=footprint.material_ref,
            material_model=material_model,
            material_reflectivity=reflectivity,
            receiver_architecture=architecture,
            receiver_direction_input=receiver_direction_input,
            receiver_direction=receiver_direction_resolved,
            receiver_aperture_area_m2=aperture_area,
            receiver_distance_m=0.0,
            receiver_fov_status="invalid_zero_distance",
            receiver_axis_angle_rad=None,
            receiver_axis_cosine=None,
            target_to_receiver_cosine=None,
            estimated_power_on_target_w=footprint.estimated_power_on_target_w,
            estimated_received_power_w=0.0,
            link_loss_db=None,
            status="invalid_geometry",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    unit_target_to_receiver = target_to_receiver / distance
    unit_receiver_to_target = -unit_target_to_receiver
    receiver_axis_cosine = float(np.dot(receiver_direction, unit_receiver_to_target))
    receiver_axis_angle = math.acos(min(max(receiver_axis_cosine, -1.0), 1.0))
    full_fov = float(receiver["full_fov_rad"])
    half_fov = 0.5 * full_fov
    if receiver_axis_angle > half_fov:
        warnings.append("Target hit point가 receiver full FOV 밖에 있습니다.")
        return ReceiverReturn(
            target_id=footprint.target_id,
            material_ref=footprint.material_ref,
            material_model=material_model,
            material_reflectivity=reflectivity,
            receiver_architecture=architecture,
            receiver_direction_input=receiver_direction_input,
            receiver_direction=receiver_direction_resolved,
            receiver_aperture_area_m2=aperture_area,
            receiver_distance_m=distance,
            receiver_fov_status="outside_fov",
            receiver_axis_angle_rad=receiver_axis_angle,
            receiver_axis_cosine=receiver_axis_cosine,
            target_to_receiver_cosine=None,
            estimated_power_on_target_w=footprint.estimated_power_on_target_w,
            estimated_received_power_w=0.0,
            link_loss_db=None,
            status="outside_fov",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    target_cosine = max(0.0, float(np.dot(footprint.intersection.target_normal, unit_target_to_receiver)))
    projected_receiver_cosine = max(0.0, receiver_axis_cosine)
    efficiency = float(receiver["optical_efficiency"])
    if not 0.0 <= efficiency <= 1.0:
        raise ValueError("receiver.optical_efficiency는 0과 1 사이여야 합니다.")
    received = (
        footprint.estimated_power_on_target_w
        * reflectivity
        / math.pi
        * target_cosine
        * aperture_area
        * projected_receiver_cosine
        / (distance * distance)
        * efficiency
    )
    if target_cosine <= 0.0:
        warnings.append("Target normal이 receiver 방향을 향하지 않아 Lambertian return을 0으로 둡니다.")
    status = "pass" if received > 0.0 else "zero_return"
    return ReceiverReturn(
        target_id=footprint.target_id,
        material_ref=footprint.material_ref,
        material_model=material_model,
        material_reflectivity=reflectivity,
        receiver_architecture=architecture,
        receiver_direction_input=receiver_direction_input,
        receiver_direction=receiver_direction_resolved,
        receiver_aperture_area_m2=aperture_area,
        receiver_distance_m=distance,
        receiver_fov_status="inside_fov",
        receiver_axis_angle_rad=receiver_axis_angle,
        receiver_axis_cosine=receiver_axis_cosine,
        target_to_receiver_cosine=target_cosine,
        estimated_power_on_target_w=footprint.estimated_power_on_target_w,
        estimated_received_power_w=received,
        link_loss_db=_safe_loss_db(footprint.estimated_power_on_target_w, received),
        status=status,
        assumptions=tuple(assumptions),
        warnings=tuple(warnings),
    )


def estimate_receiver_returns(project: Any, footprints: tuple[TargetFootprint, ...]) -> tuple[ReceiverReturn, ...]:
    """Active scenario receiver로 모든 target footprint return을 추정한다."""

    receiver = project.active_scenario["receiver"]
    returns: list[ReceiverReturn] = []
    for footprint in footprints:
        material = project.catalog[footprint.material_ref].data
        returns.append(
            estimate_lambertian_receiver_return(
                footprint=footprint,
                material=material,
                receiver=receiver,
            )
        )
    return tuple(returns)
