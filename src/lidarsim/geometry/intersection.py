"""CPU float64 기준 ray-plane intersection primitive."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from lidarsim.geometry.transform import normalize_vector


@dataclass(frozen=True, slots=True)
class RayPlaneIntersection:
    """Half-ray와 무한 plane의 교차 결과."""

    hit: bool
    miss_reason: str | None
    distance_m: float | None
    point_m: np.ndarray | None
    ray_direction: np.ndarray
    plane_origin_m: np.ndarray
    plane_normal: np.ndarray
    denominator: float
    epsilon: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "hit": self.hit,
            "miss_reason": self.miss_reason,
            "distance_m": self.distance_m,
            "point_m": None if self.point_m is None else self.point_m.tolist(),
            "ray_direction": self.ray_direction.tolist(),
            "plane_origin_m": self.plane_origin_m.tolist(),
            "plane_normal": self.plane_normal.tolist(),
            "denominator": self.denominator,
            "epsilon": self.epsilon,
        }


def _point(value: Iterable[float], *, name: str) -> np.ndarray:
    result = np.array(value, dtype=np.float64, copy=True)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    result.setflags(write=False)
    return result


def intersect_ray_plane(
    ray_origin_m: Iterable[float],
    ray_direction: Iterable[float],
    plane_origin_m: Iterable[float],
    plane_normal: Iterable[float],
    *,
    epsilon: float = 1.0e-12,
) -> RayPlaneIntersection:
    """`origin + t*direction`, `t >= 0`인 첫 plane 교차를 계산한다."""

    tolerance = float(epsilon)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("epsilon은 0보다 큰 유한한 값이어야 합니다.")
    origin = _point(ray_origin_m, name="ray_origin_m")
    direction = normalize_vector(ray_direction, name="ray_direction")
    plane_origin = _point(plane_origin_m, name="plane_origin_m")
    normal = normalize_vector(plane_normal, name="plane_normal")
    denominator = float(np.dot(direction, normal))
    if abs(denominator) <= tolerance:
        return RayPlaneIntersection(
            hit=False,
            miss_reason="parallel_to_plane",
            distance_m=None,
            point_m=None,
            ray_direction=direction,
            plane_origin_m=plane_origin,
            plane_normal=normal,
            denominator=denominator,
            epsilon=tolerance,
        )

    distance = float(np.dot(plane_origin - origin, normal) / denominator)
    if distance < -tolerance:
        return RayPlaneIntersection(
            hit=False,
            miss_reason="intersection_behind_ray",
            distance_m=None,
            point_m=None,
            ray_direction=direction,
            plane_origin_m=plane_origin,
            plane_normal=normal,
            denominator=denominator,
            epsilon=tolerance,
        )
    resolved_distance = max(distance, 0.0)
    point = np.asarray(origin + resolved_distance * direction, dtype=np.float64)
    point.setflags(write=False)
    return RayPlaneIntersection(
        hit=True,
        miss_reason=None,
        distance_m=resolved_distance,
        point_m=point,
        ray_direction=direction,
        plane_origin_m=plane_origin,
        plane_normal=normal,
        denominator=denominator,
        epsilon=tolerance,
    )
