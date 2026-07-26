"""Reciprocal receiver center-ray geometry primitives.

이 모듈은 catalog나 transmitter train의 private helper에 의존하지 않는다.
호출자가 world frame으로 resolve한 mirror, collimator receive plane과 fiber
reference plane을 제공하면 target hit에서 시작한 reverse center ray의 실제
교차점과 closure residual만 계산한다. Power, radiance, fiber mode overlap과
detector response는 의도적으로 이 계층에 포함하지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from lidarsim.geometry import RayPlaneIntersection, intersect_ray_plane
from lidarsim.geometry.transform import normalize_vector
from lidarsim.optics.mirror import reflect_vector


def _point(value: Iterable[float], *, name: str) -> np.ndarray:
    result = np.array(value, dtype=np.float64, copy=True)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    result.setflags(write=False)
    return result


def _positive(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 유한한 값이어야 합니다.")
    return result


def _optional_positive(value: float | None, *, name: str) -> float | None:
    return None if value is None else _positive(value, name=name)


def _angle(first: Iterable[float], second: Iterable[float]) -> float:
    a = normalize_vector(first, name="first direction")
    b = normalize_vector(second, name="second direction")
    return math.acos(float(np.clip(np.dot(a, b), -1.0, 1.0)))


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedPlaneFrame:
    """World frame에 resolve된 right-handed plane frame.

    ``normal``은 local +z, ``x_axis``는 local +x를 정의한다.
    Local +y는 ``normal × x_axis``로 계산하여 ``x × y = normal``인
    오른손 frame을 만든다.
    """

    origin_m: np.ndarray
    normal: np.ndarray
    x_axis: np.ndarray
    y_axis: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        origin = _point(self.origin_m, name="plane origin_m")
        normal = normalize_vector(self.normal, name="plane normal")
        x_candidate = np.array(self.x_axis, dtype=np.float64, copy=True)
        if x_candidate.shape != (3,) or not np.all(np.isfinite(x_candidate)):
            raise ValueError("plane x_axis는 유한한 vec3여야 합니다.")
        x_axis = normalize_vector(
            x_candidate - float(np.dot(x_candidate, normal)) * normal,
            name="plane x_axis",
        )
        y_axis = normalize_vector(np.cross(normal, x_axis), name="plane y_axis")
        object.__setattr__(self, "origin_m", origin)
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)

    def local_coordinates(self, point_m: Iterable[float]) -> tuple[float, float, float]:
        """Point의 local x/y/normal 좌표를 m로 반환한다."""

        delta = _point(point_m, name="plane point_m") - self.origin_m
        return (
            float(np.dot(delta, self.x_axis)),
            float(np.dot(delta, self.y_axis)),
            float(np.dot(delta, self.normal)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin_m": self.origin_m.tolist(),
            "normal": self.normal.tolist(),
            "x_axis": self.x_axis.tolist(),
            "y_axis": self.y_axis.tolist(),
        }


@dataclass(frozen=True, slots=True)
class ReciprocalPlaneHit:
    """One resolved plane에 대한 실제 ray hit·aperture residual."""

    plane_id: str
    frame: ResolvedPlaneFrame
    intersection: RayPlaneIntersection
    local_x_m: float | None
    local_y_m: float | None
    normal_residual_m: float | None
    center_offset_m: float | None
    expected_point_residual_m: float | None
    lateral_residual_m: float | None
    aperture_kind: str
    aperture_status: str
    aperture_margin_m: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plane_id": self.plane_id,
            "frame": self.frame.to_dict(),
            "intersection": self.intersection.to_dict(),
            "local_x_m": self.local_x_m,
            "local_y_m": self.local_y_m,
            "normal_residual_m": self.normal_residual_m,
            "center_offset_m": self.center_offset_m,
            "expected_point_residual_m": self.expected_point_residual_m,
            "lateral_residual_m": self.lateral_residual_m,
            "aperture_kind": self.aperture_kind,
            "aperture_status": self.aperture_status,
            "aperture_margin_m": self.aperture_margin_m,
        }


@dataclass(frozen=True, slots=True)
class ReciprocalClosureResidual:
    """Forward reference와 reverse center ray 사이의 closure residual."""

    mirror_position_residual_m: float | None
    mirror_angular_residual_rad: float | None
    collimator_position_residual_m: float | None
    collimator_lateral_residual_m: float | None
    collimator_angular_residual_rad: float | None
    fiber_position_residual_m: float | None
    fiber_lateral_residual_m: float | None
    fiber_angular_residual_rad: float | None
    maximum_position_residual_m: float | None
    maximum_angular_residual_rad: float | None
    position_tolerance_m: float
    angular_tolerance_rad: float
    status: str

    def to_dict(self) -> dict[str, float | str | None]:
        return {
            "mirror_position_residual_m": self.mirror_position_residual_m,
            "mirror_angular_residual_rad": self.mirror_angular_residual_rad,
            "collimator_position_residual_m": self.collimator_position_residual_m,
            "collimator_lateral_residual_m": self.collimator_lateral_residual_m,
            "collimator_angular_residual_rad": self.collimator_angular_residual_rad,
            "fiber_position_residual_m": self.fiber_position_residual_m,
            "fiber_lateral_residual_m": self.fiber_lateral_residual_m,
            "fiber_angular_residual_rad": self.fiber_angular_residual_rad,
            "maximum_position_residual_m": self.maximum_position_residual_m,
            "maximum_angular_residual_rad": self.maximum_angular_residual_rad,
            "position_tolerance_m": self.position_tolerance_m,
            "angular_tolerance_rad": self.angular_tolerance_rad,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True, eq=False)
class ReciprocalCenterRayResult:
    """Target에서 fiber reference plane까지의 reciprocal geometry 결과."""

    status: str
    terminated: bool
    termination_reason: str | None
    termination_point_m: np.ndarray
    target_hit_m: np.ndarray
    transmit_mirror_hit_m: np.ndarray
    return_incident_direction: np.ndarray
    mirror_hit: ReciprocalPlaneHit
    reflected_direction: np.ndarray | None
    collimator_hit: ReciprocalPlaneHit | None
    fiber_bound_direction: np.ndarray | None
    fiber_hit: ReciprocalPlaneHit | None
    closure: ReciprocalClosureResidual
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "reciprocal_center_ray_geometry",
            "status": self.status,
            "terminated": self.terminated,
            "termination_reason": self.termination_reason,
            "termination_point_m": self.termination_point_m.tolist(),
            "target_hit_m": self.target_hit_m.tolist(),
            "transmit_mirror_hit_m": self.transmit_mirror_hit_m.tolist(),
            "return_incident_direction": self.return_incident_direction.tolist(),
            "mirror_hit": self.mirror_hit.to_dict(),
            "reflected_direction": (
                None if self.reflected_direction is None else self.reflected_direction.tolist()
            ),
            "collimator_hit": (
                None if self.collimator_hit is None else self.collimator_hit.to_dict()
            ),
            "fiber_bound_direction": (
                None
                if self.fiber_bound_direction is None
                else self.fiber_bound_direction.tolist()
            ),
            "fiber_hit": None if self.fiber_hit is None else self.fiber_hit.to_dict(),
            "closure": self.closure.to_dict(),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _plane_hit(
    *,
    plane_id: str,
    frame: ResolvedPlaneFrame,
    intersection: RayPlaneIntersection,
    expected_point_m: np.ndarray,
    rectangular_aperture_m: tuple[float, float] | None = None,
    circular_aperture_diameter_m: float | None = None,
) -> ReciprocalPlaneHit:
    if rectangular_aperture_m is not None and circular_aperture_diameter_m is not None:
        raise ValueError("Plane aperture는 rectangular 또는 circular 중 하나만 사용합니다.")
    if not intersection.hit or intersection.point_m is None:
        return ReciprocalPlaneHit(
            plane_id=plane_id,
            frame=frame,
            intersection=intersection,
            local_x_m=None,
            local_y_m=None,
            normal_residual_m=None,
            center_offset_m=None,
            expected_point_residual_m=None,
            lateral_residual_m=None,
            aperture_kind="not_evaluated",
            aperture_status="no_intersection",
            aperture_margin_m=None,
        )

    point = intersection.point_m
    local_x, local_y, local_normal = frame.local_coordinates(point)
    delta_expected = point - expected_point_m
    expected_residual = float(np.linalg.norm(delta_expected))
    lateral_residual = math.hypot(
        float(np.dot(delta_expected, frame.x_axis)),
        float(np.dot(delta_expected, frame.y_axis)),
    )
    center_offset = math.hypot(local_x, local_y)
    aperture_kind = "not_configured"
    aperture_status = "not_checked"
    aperture_margin: float | None = None

    if rectangular_aperture_m is not None:
        width, height = rectangular_aperture_m
        margin_x = 0.5 * width - abs(local_x)
        margin_y = 0.5 * height - abs(local_y)
        aperture_margin = min(margin_x, margin_y)
        aperture_kind = "rectangle"
        aperture_status = "pass" if aperture_margin >= 0.0 else "miss"
    elif circular_aperture_diameter_m is not None:
        aperture_margin = 0.5 * circular_aperture_diameter_m - center_offset
        aperture_kind = "circle"
        aperture_status = "pass" if aperture_margin >= 0.0 else "miss"

    return ReciprocalPlaneHit(
        plane_id=plane_id,
        frame=frame,
        intersection=intersection,
        local_x_m=local_x,
        local_y_m=local_y,
        normal_residual_m=local_normal,
        center_offset_m=center_offset,
        expected_point_residual_m=expected_residual,
        lateral_residual_m=lateral_residual,
        aperture_kind=aperture_kind,
        aperture_status=aperture_status,
        aperture_margin_m=aperture_margin,
    )


def _closure(
    *,
    mirror_hit: ReciprocalPlaneHit,
    reflected_direction: np.ndarray | None,
    expected_reflected_direction: np.ndarray,
    collimator_hit: ReciprocalPlaneHit | None,
    collimator_receive_axis: np.ndarray,
    fiber_hit: ReciprocalPlaneHit | None,
    fiber_bound_direction: np.ndarray | None,
    fiber_receive_axis: np.ndarray,
    position_tolerance_m: float,
    angular_tolerance_rad: float,
    terminated: bool,
) -> ReciprocalClosureResidual:
    mirror_angular = (
        None
        if reflected_direction is None
        else _angle(reflected_direction, expected_reflected_direction)
    )
    collimator_angular = (
        None
        if collimator_hit is None or not collimator_hit.intersection.hit
        else _angle(reflected_direction, collimator_receive_axis)
    )
    fiber_angular = (
        None
        if fiber_hit is None or not fiber_hit.intersection.hit or fiber_bound_direction is None
        else _angle(fiber_bound_direction, fiber_receive_axis)
    )
    positions = [
        value
        for value in (
            mirror_hit.expected_point_residual_m,
            None if collimator_hit is None else collimator_hit.expected_point_residual_m,
            None if fiber_hit is None else fiber_hit.expected_point_residual_m,
        )
        if value is not None
    ]
    angles = [
        value
        for value in (mirror_angular, collimator_angular, fiber_angular)
        if value is not None
    ]
    max_position = max(positions, default=None)
    max_angle = max(angles, default=None)
    status = (
        "fail"
        if terminated
        else "pass"
        if max_position is not None
        and max_angle is not None
        and max_position <= position_tolerance_m
        and max_angle <= angular_tolerance_rad
        else "warning"
    )
    return ReciprocalClosureResidual(
        mirror_position_residual_m=mirror_hit.expected_point_residual_m,
        mirror_angular_residual_rad=mirror_angular,
        collimator_position_residual_m=(
            None if collimator_hit is None else collimator_hit.expected_point_residual_m
        ),
        collimator_lateral_residual_m=(
            None if collimator_hit is None else collimator_hit.lateral_residual_m
        ),
        collimator_angular_residual_rad=collimator_angular,
        fiber_position_residual_m=(
            None if fiber_hit is None else fiber_hit.expected_point_residual_m
        ),
        fiber_lateral_residual_m=(
            None if fiber_hit is None else fiber_hit.lateral_residual_m
        ),
        fiber_angular_residual_rad=fiber_angular,
        maximum_position_residual_m=max_position,
        maximum_angular_residual_rad=max_angle,
        position_tolerance_m=position_tolerance_m,
        angular_tolerance_rad=angular_tolerance_rad,
        status=status,
    )


def trace_reciprocal_center_ray(
    *,
    target_hit_m: Iterable[float],
    transmit_mirror_hit_m: Iterable[float],
    transmit_incident_direction: Iterable[float],
    mirror_plane: ResolvedPlaneFrame,
    mirror_clear_width_m: float,
    mirror_clear_height_m: float,
    collimator_receive_plane: ResolvedPlaneFrame,
    collimator_receive_axis: Iterable[float],
    fiber_reference_plane: ResolvedPlaneFrame,
    fiber_receive_axis: Iterable[float],
    expected_collimator_hit_m: Iterable[float] | None = None,
    expected_fiber_hit_m: Iterable[float] | None = None,
    collimator_clear_aperture_diameter_m: float | None = None,
    fiber_acceptance_diameter_m: float | None = None,
    fiber_bound_direction: Iterable[float] | None = None,
    position_tolerance_m: float = 1.0e-9,
    angular_tolerance_rad: float = 1.0e-9,
    intersection_epsilon: float = 1.0e-12,
) -> ReciprocalCenterRayResult:
    """Trace one reciprocal center ray through resolved reference planes.

    Return ray는 ``target_hit_m``에서 forward ``transmit_mirror_hit_m``를 향한다.
    Mirror에서 ideal vector reflection을 적용한 뒤 collimator receive
    plane과 fiber reference plane을 순서대로 교차한다. 기본적으로
    collimator plane 후에도 같은 center-ray 방향을 사용하며, 이상
    lens 등 외부 reverse optic이 resolve한 방향은
    ``fiber_bound_direction``으로 명시할 수 있다.

    Power, aperture power integration, collimator diffraction/refraction, fiber mode
    overlap과 detector response는 계산하지 않는다.
    """

    target = _point(target_hit_m, name="target_hit_m")
    transmit_mirror_hit = _point(
        transmit_mirror_hit_m,
        name="transmit_mirror_hit_m",
    )
    transmit_incident = normalize_vector(
        transmit_incident_direction,
        name="transmit_incident_direction",
    )
    return_direction = normalize_vector(
        transmit_mirror_hit - target,
        name="target-to-mirror return direction",
    )
    expected_reflected = normalize_vector(
        -transmit_incident,
        name="expected reciprocal reflected direction",
    )
    collimator_axis = normalize_vector(
        collimator_receive_axis,
        name="collimator_receive_axis",
    )
    fiber_axis = normalize_vector(fiber_receive_axis, name="fiber_receive_axis")
    expected_collimator = (
        collimator_receive_plane.origin_m
        if expected_collimator_hit_m is None
        else _point(expected_collimator_hit_m, name="expected_collimator_hit_m")
    )
    expected_fiber = (
        fiber_reference_plane.origin_m
        if expected_fiber_hit_m is None
        else _point(expected_fiber_hit_m, name="expected_fiber_hit_m")
    )
    width = _positive(mirror_clear_width_m, name="mirror_clear_width_m")
    height = _positive(mirror_clear_height_m, name="mirror_clear_height_m")
    collimator_diameter = _optional_positive(
        collimator_clear_aperture_diameter_m,
        name="collimator_clear_aperture_diameter_m",
    )
    fiber_diameter = _optional_positive(
        fiber_acceptance_diameter_m,
        name="fiber_acceptance_diameter_m",
    )
    position_tolerance = _positive(position_tolerance_m, name="position_tolerance_m")
    angular_tolerance = _positive(angular_tolerance_rad, name="angular_tolerance_rad")
    epsilon = _positive(intersection_epsilon, name="intersection_epsilon")
    assumptions = (
        "Target hit에서 forward mirror hit를 향하는 하나의 reciprocal center ray만 계산합니다.",
        "Mirror에는 ideal flat-surface vector reflection을 적용합니다.",
        "Power, radiance, diffraction, reverse collimator aberration과 single-mode fiber coupling은 계산하지 않습니다.",
    )
    warnings: list[str] = []
    if fiber_bound_direction is None:
        warnings.append(
            "fiber_bound_direction이 없어 collimator receive plane 후의 ray를 "
            "직선 연장했습니다. Reverse lens refraction/focus는 아직 포함하지 않습니다."
        )

    mirror_intersection = intersect_ray_plane(
        target,
        return_direction,
        mirror_plane.origin_m,
        mirror_plane.normal,
        epsilon=epsilon,
    )
    mirror_hit = _plane_hit(
        plane_id="return_mirror",
        frame=mirror_plane,
        intersection=mirror_intersection,
        expected_point_m=transmit_mirror_hit,
        rectangular_aperture_m=(width, height),
    )

    reflected: np.ndarray | None = None
    collimator_hit: ReciprocalPlaneHit | None = None
    fiber_direction: np.ndarray | None = None
    fiber_hit: ReciprocalPlaneHit | None = None
    terminated = False
    termination_reason: str | None = None
    termination_point = target

    if not mirror_intersection.hit or mirror_intersection.point_m is None:
        terminated = True
        termination_reason = f"return_mirror:{mirror_intersection.miss_reason}"
    elif mirror_hit.aperture_status == "miss":
        terminated = True
        termination_reason = "return_mirror:outside_clear_aperture"
        termination_point = mirror_intersection.point_m
    else:
        termination_point = mirror_intersection.point_m
        reflected = reflect_vector(return_direction, mirror_plane.normal)
        collimator_intersection = intersect_ray_plane(
            mirror_intersection.point_m,
            reflected,
            collimator_receive_plane.origin_m,
            collimator_receive_plane.normal,
            epsilon=epsilon,
        )
        collimator_hit = _plane_hit(
            plane_id="return_collimator_receive",
            frame=collimator_receive_plane,
            intersection=collimator_intersection,
            expected_point_m=expected_collimator,
            circular_aperture_diameter_m=collimator_diameter,
        )
        if not collimator_intersection.hit or collimator_intersection.point_m is None:
            terminated = True
            termination_reason = f"return_collimator:{collimator_intersection.miss_reason}"
        elif collimator_hit.aperture_status == "miss":
            terminated = True
            termination_reason = "return_collimator:outside_clear_aperture"
            termination_point = collimator_intersection.point_m
        else:
            termination_point = collimator_intersection.point_m
            fiber_direction = normalize_vector(
                reflected if fiber_bound_direction is None else fiber_bound_direction,
                name="fiber_bound_direction",
            )
            fiber_intersection = intersect_ray_plane(
                collimator_intersection.point_m,
                fiber_direction,
                fiber_reference_plane.origin_m,
                fiber_reference_plane.normal,
                epsilon=epsilon,
            )
            fiber_hit = _plane_hit(
                plane_id="fiber_reference",
                frame=fiber_reference_plane,
                intersection=fiber_intersection,
                expected_point_m=expected_fiber,
                circular_aperture_diameter_m=fiber_diameter,
            )
            if not fiber_intersection.hit or fiber_intersection.point_m is None:
                terminated = True
                termination_reason = f"fiber_reference:{fiber_intersection.miss_reason}"
            elif fiber_hit.aperture_status == "miss":
                terminated = True
                termination_reason = "fiber_reference:outside_acceptance_aperture"
                termination_point = fiber_intersection.point_m
            else:
                termination_point = fiber_intersection.point_m

    closure = _closure(
        mirror_hit=mirror_hit,
        reflected_direction=reflected,
        expected_reflected_direction=expected_reflected,
        collimator_hit=collimator_hit,
        collimator_receive_axis=collimator_axis,
        fiber_hit=fiber_hit,
        fiber_bound_direction=fiber_direction,
        fiber_receive_axis=fiber_axis,
        position_tolerance_m=position_tolerance,
        angular_tolerance_rad=angular_tolerance,
        terminated=terminated,
    )
    status = "terminated" if terminated else closure.status
    if not terminated and closure.status == "warning":
        warnings.append(
            "Reciprocal center-ray closure residual이 설정한 position/angular tolerance를 초과합니다."
        )
    if terminated and termination_reason is not None:
        warnings.append(
            f"Return path가 {termination_reason}에서 종료되었으며 후속 plane으로 재중심화하지 않았습니다."
        )

    return ReciprocalCenterRayResult(
        status=status,
        terminated=terminated,
        termination_reason=termination_reason,
        termination_point_m=_point(termination_point, name="termination_point_m"),
        target_hit_m=target,
        transmit_mirror_hit_m=transmit_mirror_hit,
        return_incident_direction=return_direction,
        mirror_hit=mirror_hit,
        reflected_direction=reflected,
        collimator_hit=collimator_hit,
        fiber_bound_direction=fiber_direction,
        fiber_hit=fiber_hit,
        closure=closure,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )
