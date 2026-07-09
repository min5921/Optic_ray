"""Analytical target primitive intersection for Phase 2.2."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from lidarsim.beam import BeamState
from lidarsim.geometry.transform import normalize_vector


def _vec3(value: Iterable[float], *, name: str) -> np.ndarray:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    array.setflags(write=False)
    return array


def _positive(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 유한한 값이어야 합니다.")
    return result


def rectangle_plane_axes(normal: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    """Rectangle target의 deterministic local width/height axes를 만든다."""

    unit_normal = normalize_vector(normal, name="target normal")
    for candidate in (
        np.array([0.0, 1.0, 0.0], dtype=np.float64),
        np.array([0.0, 0.0, 1.0], dtype=np.float64),
        np.array([1.0, 0.0, 0.0], dtype=np.float64),
    ):
        projected = candidate - float(np.dot(candidate, unit_normal)) * unit_normal
        if float(np.linalg.norm(projected)) > 1e-12:
            width_axis = normalize_vector(projected, name="target width axis")
            height_axis = normalize_vector(
                np.cross(width_axis, unit_normal),
                name="target height axis",
            )
            return width_axis, height_axis
    raise ValueError("target normal에서 local axes를 만들 수 없습니다.")


@dataclass(frozen=True, slots=True, eq=False)
class TargetIntersection:
    """Beam center ray와 rectangle-plane target의 교차 결과."""

    target_id: str
    material_ref: str
    geometry_type: str
    hit: bool
    miss_reason: str | None
    hit_center_m: np.ndarray | None
    distance_to_target_m: float | None
    incidence_angle_rad: float | None
    incidence_cosine: float | None
    local_coordinates_m: tuple[float, float] | None
    target_center_m: np.ndarray
    target_normal: np.ndarray
    width_axis: np.ndarray
    height_axis: np.ndarray
    width_m: float
    height_m: float
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "material_ref": self.material_ref,
            "geometry_type": self.geometry_type,
            "hit": self.hit,
            "miss_reason": self.miss_reason,
            "hit_center_m": None if self.hit_center_m is None else self.hit_center_m.tolist(),
            "distance_to_target_m": self.distance_to_target_m,
            "incidence_angle_rad": self.incidence_angle_rad,
            "incidence_angle_convention": "angle_from_surface_normal_radians",
            "incidence_cosine": self.incidence_cosine,
            "local_coordinates_m": (
                None if self.local_coordinates_m is None else list(self.local_coordinates_m)
            ),
            "target_center_m": self.target_center_m.tolist(),
            "target_normal": self.target_normal.tolist(),
            "width_axis_world": self.width_axis.tolist(),
            "height_axis_world": self.height_axis.tolist(),
            "width_m": self.width_m,
            "height_m": self.height_m,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _miss(
    *,
    target_id: str,
    material_ref: str,
    geometry_type: str,
    reason: str,
    center: np.ndarray,
    normal: np.ndarray,
    width_axis: np.ndarray,
    height_axis: np.ndarray,
    width_m: float,
    height_m: float,
    assumptions: tuple[str, ...],
    warnings: tuple[str, ...] = (),
) -> TargetIntersection:
    return TargetIntersection(
        target_id=target_id,
        material_ref=material_ref,
        geometry_type=geometry_type,
        hit=False,
        miss_reason=reason,
        hit_center_m=None,
        distance_to_target_m=None,
        incidence_angle_rad=None,
        incidence_cosine=None,
        local_coordinates_m=None,
        target_center_m=center,
        target_normal=normal,
        width_axis=width_axis,
        height_axis=height_axis,
        width_m=width_m,
        height_m=height_m,
        assumptions=assumptions,
        warnings=warnings,
    )


def intersect_rectangle_plane(
    beam: BeamState,
    *,
    target_id: str,
    material_ref: str,
    center_m: Iterable[float],
    normal: Iterable[float],
    width_m: float,
    height_m: float,
    epsilon: float = 1e-12,
) -> TargetIntersection:
    """Beam center ray와 rectangle plane의 첫 교차를 계산한다."""

    center = _vec3(center_m, name="target center_m")
    unit_normal = normalize_vector(normal, name="target normal")
    width = _positive(width_m, name="target width_m")
    height = _positive(height_m, name="target height_m")
    width_axis, height_axis = rectangle_plane_axes(unit_normal)
    assumptions = (
        "rectangle_plane target은 완전 평면 primitive로 취급합니다.",
        "STL visibility, occlusion, roughness와 curved-surface intersection은 계산하지 않습니다.",
    )

    denominator = float(np.dot(beam.direction, unit_normal))
    if abs(denominator) <= float(epsilon):
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="parallel_to_plane",
            center=center,
            normal=unit_normal,
            width_axis=width_axis,
            height_axis=height_axis,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
        )

    distance = float(np.dot(center - beam.origin_m, unit_normal) / denominator)
    if distance <= float(epsilon):
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="intersection_behind_beam",
            center=center,
            normal=unit_normal,
            width_axis=width_axis,
            height_axis=height_axis,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
        )

    hit = beam.origin_m + distance * beam.direction
    offset = hit - center
    local_u = float(np.dot(offset, width_axis))
    local_v = float(np.dot(offset, height_axis))
    if abs(local_u) > 0.5 * width + float(epsilon) or abs(local_v) > 0.5 * height + float(epsilon):
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="outside_rectangle_bounds",
            center=center,
            normal=unit_normal,
            width_axis=width_axis,
            height_axis=height_axis,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
        )

    incidence_cosine = abs(denominator)
    incidence_angle = math.acos(min(max(incidence_cosine, 0.0), 1.0))
    hit.setflags(write=False)
    warnings: list[str] = []
    if denominator > 0.0:
        warnings.append(
            "Beam이 target normal의 뒷면 방향에서 접근합니다. 양면 Lambertian reference로 계산합니다."
        )
    return TargetIntersection(
        target_id=target_id,
        material_ref=material_ref,
        geometry_type="rectangle_plane",
        hit=True,
        miss_reason=None,
        hit_center_m=hit,
        distance_to_target_m=distance,
        incidence_angle_rad=incidence_angle,
        incidence_cosine=incidence_cosine,
        local_coordinates_m=(local_u, local_v),
        target_center_m=center,
        target_normal=unit_normal,
        width_axis=width_axis,
        height_axis=height_axis,
        width_m=width,
        height_m=height,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )


def evaluate_target_footprints(project: Any, beam: BeamState) -> tuple[Any, ...]:
    """Active scenario targets를 읽고 rectangle-plane footprint들을 평가한다."""

    from lidarsim.scene.footprint import estimate_rectangle_plane_footprint

    footprints: list[Any] = []
    for target in project.active_scenario["scene"]["targets"]:
        geometry = target["geometry"]
        target_id = str(target["id"])
        material_ref = str(target["material_ref"])
        geometry_type = str(geometry["type"])
        if geometry_type != "rectangle_plane":
            normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            width_axis, height_axis = rectangle_plane_axes(normal)
            intersection = _miss(
                target_id=target_id,
                material_ref=material_ref,
                geometry_type=geometry_type,
                reason=f"unsupported_geometry_type:{geometry_type}",
                center=np.zeros(3, dtype=np.float64),
                normal=normal,
                width_axis=width_axis,
                height_axis=height_axis,
                width_m=1.0,
                height_m=1.0,
                assumptions=("STL/CAD target hit detection은 이번 Phase 2.2 patch 범위 밖입니다.",),
            )
            footprints.append(estimate_rectangle_plane_footprint(beam, intersection))
            continue
        intersection = intersect_rectangle_plane(
            beam,
            target_id=target_id,
            material_ref=material_ref,
            center_m=geometry["center_m"],
            normal=geometry["normal"],
            width_m=geometry["width_m"],
            height_m=geometry["height_m"],
        )
        footprints.append(estimate_rectangle_plane_footprint(beam, intersection))
    return tuple(footprints)
