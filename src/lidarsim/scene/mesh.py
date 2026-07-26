"""CPU float64 STL triangle transform와 closest-hit reference 구현."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

import numpy as np
from numpy.typing import NDArray

from lidarsim.assets.stl import MeshGeometry
from lidarsim.geometry.transform import RigidTransform, normalize_vector

if TYPE_CHECKING:
    from lidarsim.assets.loader import StlAsset


FloatArray = NDArray[np.float64]


def _readonly_vec3(value: Iterable[float], *, name: str) -> FloatArray:
    result = np.array(value, dtype=np.float64, copy=True)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    result.setflags(write=False)
    return result


def _geometric_normals(
    vertices: FloatArray,
) -> tuple[FloatArray, NDArray[np.bool_]]:
    edge_one = vertices[:, 1] - vertices[:, 0]
    edge_two = vertices[:, 2] - vertices[:, 0]
    cross = np.cross(edge_one, edge_two)
    twice_area = np.linalg.norm(cross, axis=1)
    extent = float(np.max(np.ptp(vertices.reshape(-1, 3), axis=0)))
    area_tolerance = max(extent * extent * 1.0e-12, 1.0e-30)
    valid = twice_area > area_tolerance
    normals = np.zeros_like(cross, dtype=np.float64)
    normals[valid] = cross[valid] / twice_area[valid, None]
    return normals, valid


@dataclass(frozen=True, slots=True, eq=False)
class TriangleMesh:
    """World-space triangle vertices와 winding 기반 geometric normal."""

    triangle_vertices_m: FloatArray
    asset_id: str | None = None
    source_path: Path | None = None
    geometric_normals: FloatArray = field(init=False)
    valid_triangle_mask: NDArray[np.bool_] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        vertices = np.array(self.triangle_vertices_m, dtype=np.float64, copy=True)
        if vertices.ndim != 3 or vertices.shape[1:] != (3, 3) or vertices.shape[0] == 0:
            raise ValueError("triangle_vertices_m shape은 (N, 3, 3), N > 0이어야 합니다.")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("triangle_vertices_m에는 유한한 숫자만 사용할 수 있습니다.")
        normals, valid = _geometric_normals(vertices)
        vertices.setflags(write=False)
        normals.setflags(write=False)
        valid.setflags(write=False)
        object.__setattr__(self, "triangle_vertices_m", vertices)
        object.__setattr__(self, "geometric_normals", normals)
        object.__setattr__(self, "valid_triangle_mask", valid)
        if self.source_path is not None:
            object.__setattr__(self, "source_path", Path(self.source_path).resolve())

    @property
    def triangle_count(self) -> int:
        return int(self.triangle_vertices_m.shape[0])

    @property
    def degenerate_triangle_count(self) -> int:
        return int(np.count_nonzero(~self.valid_triangle_mask))

    @property
    def bounds_m(self) -> FloatArray:
        flattened = self.triangle_vertices_m.reshape(-1, 3)
        bounds = np.stack((np.min(flattened, axis=0), np.max(flattened, axis=0)))
        bounds.setflags(write=False)
        return bounds

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_path": None if self.source_path is None else str(self.source_path),
            "triangle_count": self.triangle_count,
            "degenerate_triangle_count": self.degenerate_triangle_count,
            "bounds_m": self.bounds_m.tolist(),
            "normal_source": "triangle_vertex_winding",
            "triangle_semantics": "geometry_only_not_optical_scatterers",
        }


def build_world_triangle_mesh(
    geometry: MeshGeometry,
    *,
    unit_scale_m: float,
    T_world_from_mesh: RigidTransform,
    asset_id: str | None = None,
) -> TriangleMesh:
    """STL unit scale과 rigid transform을 적용해 world-space mesh를 만든다."""

    scale = float(unit_scale_m)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("unit_scale_m은 0보다 큰 유한한 값이어야 합니다.")
    scaled_vertices = geometry.triangle_vertices * scale
    world_vertices = (
        scaled_vertices @ T_world_from_mesh.rotation.T
        + T_world_from_mesh.translation_m
    )
    return TriangleMesh(
        triangle_vertices_m=world_vertices,
        asset_id=asset_id,
        source_path=geometry.path,
    )


def world_triangle_mesh_from_asset(asset: StlAsset) -> TriangleMesh:
    """World parent를 갖는 ``StlAsset`` sidecar에서 world mesh를 만든다."""

    parent_frame = str(asset.data["placement"]["parent_frame"])
    if parent_frame != "world":
        raise ValueError(
            "STL asset의 parent_frame이 'world'가 아닙니다. 먼저 parent transform을 "
            "resolve한 뒤 build_world_triangle_mesh()에 T_world_from_mesh를 전달하세요."
        )
    return build_world_triangle_mesh(
        asset.geometry,
        unit_scale_m=float(asset.data["mesh"]["unit_scale_m"]),
        T_world_from_mesh=asset.T_parent_from_mesh,
        asset_id=asset.identifier,
    )


@dataclass(frozen=True, slots=True, eq=False)
class RayMeshIntersection:
    """Half-ray와 triangle mesh의 nearest positive hit 결과."""

    hit: bool
    status: str
    miss_reason: str | None
    ray_origin_m: FloatArray
    ray_direction: FloatArray
    distance_m: float | None
    point_m: FloatArray | None
    triangle_index: int | None
    barycentric: FloatArray | None
    geometric_normal: FloatArray | None
    front_face: bool | None
    face: str | None
    tested_triangle_count: int
    valid_triangle_count: int
    parallel_epsilon: float
    minimum_distance_m: float
    barycentric_epsilon: float = 1.0e-12
    assumptions: tuple[str, ...] = (
        "CPU NumPy float64 Moller-Trumbore center-ray intersection을 사용합니다.",
        "STL triangle은 geometry와 geometric normal의 기준이며 optical scatterer가 아닙니다.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ray_origin_m",
            _readonly_vec3(self.ray_origin_m, name="ray_origin_m"),
        )
        object.__setattr__(
            self,
            "ray_direction",
            normalize_vector(self.ray_direction, name="ray_direction"),
        )
        for field_name in ("point_m", "barycentric", "geometric_normal"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _readonly_vec3(value, name=field_name))
        if self.status not in {
            "hit",
            "parallel",
            "behind",
            "self_hit_filtered",
            "no_hit",
        }:
            raise ValueError(f"알 수 없는 mesh intersection status입니다: {self.status!r}")
        if self.hit != (self.status == "hit"):
            raise ValueError("hit boolean과 status가 일치하지 않습니다.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "hit": self.hit,
            "status": self.status,
            "miss_reason": self.miss_reason,
            "ray_origin_m": self.ray_origin_m.tolist(),
            "ray_direction": self.ray_direction.tolist(),
            "distance_m": self.distance_m,
            "point_m": None if self.point_m is None else self.point_m.tolist(),
            "triangle_index": self.triangle_index,
            "barycentric": (
                None if self.barycentric is None else self.barycentric.tolist()
            ),
            "barycentric_convention": "weights_for_vertices_v0_v1_v2",
            "geometric_normal": (
                None if self.geometric_normal is None else self.geometric_normal.tolist()
            ),
            "geometric_normal_source": "triangle_vertex_winding",
            "front_face": self.front_face,
            "face": self.face,
            "face_convention": "front_when_dot_ray_direction_geometric_normal_is_negative",
            "tested_triangle_count": self.tested_triangle_count,
            "valid_triangle_count": self.valid_triangle_count,
            "parallel_epsilon": self.parallel_epsilon,
            "barycentric_epsilon": self.barycentric_epsilon,
            "minimum_distance_m": self.minimum_distance_m,
            "assumptions": list(self.assumptions),
        }


def _miss_result(
    *,
    status: str,
    reason: str,
    origin: FloatArray,
    direction: FloatArray,
    mesh: TriangleMesh,
    parallel_epsilon: float,
    barycentric_epsilon: float,
    minimum_distance_m: float,
) -> RayMeshIntersection:
    return RayMeshIntersection(
        hit=False,
        status=status,
        miss_reason=reason,
        ray_origin_m=origin,
        ray_direction=direction,
        distance_m=None,
        point_m=None,
        triangle_index=None,
        barycentric=None,
        geometric_normal=None,
        front_face=None,
        face=None,
        tested_triangle_count=mesh.triangle_count,
        valid_triangle_count=int(np.count_nonzero(mesh.valid_triangle_mask)),
        parallel_epsilon=parallel_epsilon,
        barycentric_epsilon=barycentric_epsilon,
        minimum_distance_m=minimum_distance_m,
    )


def intersect_ray_triangle_mesh(
    ray_origin_m: Iterable[float],
    ray_direction: Iterable[float],
    mesh: TriangleMesh,
    *,
    parallel_epsilon: float = 1.0e-12,
    barycentric_epsilon: float = 1.0e-12,
    minimum_distance_m: float = 1.0e-12,
) -> RayMeshIntersection:
    """Moller-Trumbore로 모든 triangle 중 가장 가까운 positive hit를 고른다."""

    parallel_tolerance = float(parallel_epsilon)
    barycentric_tolerance = float(barycentric_epsilon)
    minimum_distance = float(minimum_distance_m)
    if not math.isfinite(parallel_tolerance) or parallel_tolerance <= 0.0:
        raise ValueError("parallel_epsilon은 0보다 큰 유한한 값이어야 합니다.")
    if not math.isfinite(barycentric_tolerance) or barycentric_tolerance < 0.0:
        raise ValueError("barycentric_epsilon은 0 이상인 유한한 값이어야 합니다.")
    if not math.isfinite(minimum_distance) or minimum_distance < 0.0:
        raise ValueError("minimum_distance_m은 0 이상인 유한한 값이어야 합니다.")

    origin = _readonly_vec3(ray_origin_m, name="ray_origin_m")
    direction = normalize_vector(ray_direction, name="ray_direction")
    vertices = mesh.triangle_vertices_m
    edge_one = vertices[:, 1] - vertices[:, 0]
    edge_two = vertices[:, 2] - vertices[:, 0]
    twice_area = np.linalg.norm(np.cross(edge_one, edge_two), axis=1)
    repeated_direction = np.broadcast_to(direction, edge_two.shape)
    p_vector = np.cross(repeated_direction, edge_two)
    determinant = np.einsum("ij,ij->i", edge_one, p_vector)
    nonparallel = mesh.valid_triangle_mask & (
        np.abs(determinant) > parallel_tolerance * twice_area
    )

    valid_count = int(np.count_nonzero(mesh.valid_triangle_mask))
    if valid_count == 0:
        return _miss_result(
            status="no_hit",
            reason="mesh_has_no_non_degenerate_triangles",
            origin=origin,
            direction=direction,
            mesh=mesh,
            parallel_epsilon=parallel_tolerance,
            barycentric_epsilon=barycentric_tolerance,
            minimum_distance_m=minimum_distance,
        )
    if not np.any(nonparallel):
        return _miss_result(
            status="parallel",
            reason="ray_parallel_to_all_non_degenerate_triangles",
            origin=origin,
            direction=direction,
            mesh=mesh,
            parallel_epsilon=parallel_tolerance,
            barycentric_epsilon=barycentric_tolerance,
            minimum_distance_m=minimum_distance,
        )

    inverse_determinant = np.zeros_like(determinant, dtype=np.float64)
    inverse_determinant[nonparallel] = 1.0 / determinant[nonparallel]
    offset = origin - vertices[:, 0]
    barycentric_u = (
        np.einsum("ij,ij->i", offset, p_vector) * inverse_determinant
    )
    q_vector = np.cross(offset, edge_one)
    barycentric_v = (
        np.einsum("ij,ij->i", repeated_direction, q_vector)
        * inverse_determinant
    )
    distances = (
        np.einsum("ij,ij->i", edge_two, q_vector) * inverse_determinant
    )
    inside = (
        nonparallel
        & (barycentric_u >= -barycentric_tolerance)
        & (barycentric_v >= -barycentric_tolerance)
        & (barycentric_u + barycentric_v <= 1.0 + barycentric_tolerance)
    )
    forward = inside & (distances > minimum_distance)
    if not np.any(forward):
        self_hit_filtered = inside & (distances >= 0.0) & (
            distances <= minimum_distance
        )
        behind = inside & (distances < 0.0)
        if np.any(self_hit_filtered):
            status = "self_hit_filtered"
            reason = "triangle_intersections_at_or_below_minimum_distance"
        elif np.any(behind):
            status = "behind"
            reason = "triangle_intersections_not_in_positive_ray_direction"
        else:
            status = "no_hit"
            reason = "ray_does_not_intersect_any_triangle_bounds"
        return _miss_result(
            status=status,
            reason=reason,
            origin=origin,
            direction=direction,
            mesh=mesh,
            parallel_epsilon=parallel_tolerance,
            barycentric_epsilon=barycentric_tolerance,
            minimum_distance_m=minimum_distance,
        )

    candidates = np.where(forward, distances, np.inf)
    triangle_index = int(np.argmin(candidates))
    distance = float(distances[triangle_index])
    point = origin + distance * direction
    u = float(barycentric_u[triangle_index])
    v = float(barycentric_v[triangle_index])
    barycentric = np.clip(np.array([1.0 - u - v, u, v]), 0.0, 1.0)
    barycentric /= float(np.sum(barycentric))
    normal = mesh.geometric_normals[triangle_index]
    front_face = float(np.dot(direction, normal)) < 0.0
    return RayMeshIntersection(
        hit=True,
        status="hit",
        miss_reason=None,
        ray_origin_m=origin,
        ray_direction=direction,
        distance_m=distance,
        point_m=point,
        triangle_index=triangle_index,
        barycentric=barycentric,
        geometric_normal=normal,
        front_face=front_face,
        face="front" if front_face else "back",
        tested_triangle_count=mesh.triangle_count,
        valid_triangle_count=valid_count,
        parallel_epsilon=parallel_tolerance,
        barycentric_epsilon=barycentric_tolerance,
        minimum_distance_m=minimum_distance,
    )


def intersect_ray_mesh(
    ray_origin_m: Iterable[float],
    ray_direction: Iterable[float],
    mesh: TriangleMesh,
    **kwargs: float,
) -> RayMeshIntersection:
    """간결한 public alias로 closest-hit triangle intersection을 반환한다."""

    return intersect_ray_triangle_mesh(ray_origin_m, ray_direction, mesh, **kwargs)
