"""3D optical bench viewport data contract.

이 module은 UI가 숨겨진 source of truth가 되지 않도록, resolved config와
structured report에서만 viewport snapshot을 만든다. Streamlit, Plotly,
Three.js 또는 Matplotlib renderer는 이 contract만 소비한다.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lidarsim.config.immutable import deep_freeze, deep_thaw
from lidarsim.geometry import AssemblyPlacement, resolve_assembly
from lidarsim.geometry.transform import normalize_vector
from lidarsim.results import Phase2OpticalTrainReport, build_phase2_optical_train_report
from lidarsim.scene.footprint import FOOTPRINT_AXIS_CONVENTION
from lidarsim.scene.mesh import TriangleMesh, world_triangle_mesh_from_asset
from lidarsim.scene.mesh_targets import resolve_project_stl_asset
from lidarsim.scene.targets import rectangle_plane_axes


Vec3 = tuple[float, float, float]
Mat3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Triangle3 = tuple[Vec3, Vec3, Vec3]


MAX_VIEWPORT_MESH_TRIANGLES = 2_000


def _vec3(value: Any, *, name: str) -> Vec3:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    return (float(array[0]), float(array[1]), float(array[2]))


def _matrix3(value: Any, *, name: str) -> Mat3:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3, 3) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name}은 유한한 3x3 matrix여야 합니다.")
    return tuple(tuple(float(array[row, col]) for col in range(3)) for row in range(3))  # type: ignore[return-value]


def _point(value: Vec3) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _distance(start: Vec3, end: Vec3) -> float:
    return float(np.linalg.norm(_point(end) - _point(start)))


def _format_optional_float(value: Any, *, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Viewport metadata에는 유한한 숫자만 사용할 수 있습니다.")
    return f"{number:.6g}{suffix}"


def _frame_from_z_axis(axis: Any, *, name: str) -> Mat3:
    """Local z axis가 지정 vector를 향하는 deterministic right-handed frame을 만든다."""

    z_axis = normalize_vector(axis, name=name)
    for candidate in (
        np.array((0.0, 1.0, 0.0), dtype=np.float64),
        np.array((0.0, 0.0, 1.0), dtype=np.float64),
        np.array((1.0, 0.0, 0.0), dtype=np.float64),
    ):
        projected = candidate - float(np.dot(candidate, z_axis)) * z_axis
        if float(np.linalg.norm(projected)) > 1.0e-12:
            x_axis = normalize_vector(projected, name=f"{name} frame x axis")
            y_axis = normalize_vector(np.cross(z_axis, x_axis), name=f"{name} frame y axis")
            return _matrix3(
                np.column_stack((x_axis, y_axis, z_axis)),
                name=f"{name} frame",
            )
    raise ValueError(f"{name}에서 local frame을 만들 수 없습니다.")


def _frame_from_target_normal(
    normal: Any,
    width_axis: Any | None = None,
    *,
    name: str,
) -> Mat3:
    unit_normal = normalize_vector(normal, name=name)
    resolved_width_axis, height_axis = rectangle_plane_axes(
        unit_normal,
        width_axis,
    )
    return _matrix3(
        np.column_stack((resolved_width_axis, height_axis, unit_normal)),
        name=f"{name} frame",
    )


def _as_report_dict(report: Phase2OpticalTrainReport | dict[str, Any]) -> dict[str, Any]:
    return report.to_dict() if hasattr(report, "to_dict") else dict(report)


@dataclass(frozen=True, slots=True)
class ViewportComponent:
    """3D workspace에서 선택·표시할 component 또는 scene object."""

    element_id: str
    component_ref: str
    component_type: str
    model_level: str
    origin_world_m: Vec3
    rotation_world_from_component: Mat3
    bounds_m: tuple[Vec3, Vec3] | None
    display_role: str
    selectable: bool = True
    editable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "component_ref": self.component_ref,
            "component_type": self.component_type,
            "model_level": self.model_level,
            "origin_world_m": list(self.origin_world_m),
            "rotation_world_from_component": [list(row) for row in self.rotation_world_from_component],
            "bounds_m": None
            if self.bounds_m is None
            else [list(self.bounds_m[0]), list(self.bounds_m[1])],
            "display_role": self.display_role,
            "selectable": self.selectable,
            "editable": self.editable,
        }


@dataclass(frozen=True, slots=True)
class ViewportPort:
    """Optical input/output port marker."""

    element_id: str
    port_id: str
    role: str
    interface_type: str
    reference_plane: str
    origin_world_m: Vec3
    axis_world: Vec3
    transverse_x_world: Vec3
    clear_aperture_m: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "port_id": self.port_id,
            "role": self.role,
            "interface_type": self.interface_type,
            "reference_plane": self.reference_plane,
            "origin_world_m": list(self.origin_world_m),
            "axis_world": list(self.axis_world),
            "transverse_x_world": list(self.transverse_x_world),
            "clear_aperture_m": self.clear_aperture_m,
        }


@dataclass(frozen=True, slots=True)
class GuideLine:
    """Grid, optical axis, local frame, FOV, normal 또는 ruler guide."""

    guide_id: str
    guide_type: str
    start_m: Vec3
    end_m: Vec3
    color: str
    label: str
    enabled: bool
    source: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", deep_freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "guide_id": self.guide_id,
            "guide_type": self.guide_type,
            "start_m": list(self.start_m),
            "end_m": list(self.end_m),
            "color": self.color,
            "label": self.label,
            "enabled": self.enabled,
            "source": self.source,
            "metadata": deep_thaw(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RaySegment:
    """Beam path와 reflected ray 표시 단위."""

    segment_id: str
    start_m: Vec3
    end_m: Vec3
    direction: Vec3
    optical_path_id: str
    source_element_id: str
    target_element_id: str | None
    power_w: float | None
    radius_start_m: float | None
    radius_end_m: float | None
    status: str
    label: str
    propagation_role: str = "transmit"
    plane_power_name: str | None = None

    @property
    def length_m(self) -> float:
        return _distance(self.start_m, self.end_m)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_m": list(self.start_m),
            "end_m": list(self.end_m),
            "direction": list(self.direction),
            "optical_path_id": self.optical_path_id,
            "source_element_id": self.source_element_id,
            "target_element_id": self.target_element_id,
            "power_w": self.power_w,
            "radius_start_m": self.radius_start_m,
            "radius_end_m": self.radius_end_m,
            "length_m": self.length_m,
            "status": self.status,
            "label": self.label,
            "propagation_role": self.propagation_role,
            "plane_power_name": self.plane_power_name,
        }


@dataclass(frozen=True, slots=True)
class FootprintOverlay:
    """Target surface 위 projected footprint 표시 단위."""

    target_id: str
    hit_center_m: Vec3
    normal: Vec3
    major_radius_m: float
    minor_radius_m: float
    major_axis_world: Vec3
    minor_axis_world: Vec3
    axis_convention: str
    area_m2: float
    power_on_target_w: float
    clipped_by_target_bounds: bool
    status: str

    def __post_init__(self) -> None:
        normal = normalize_vector(self.normal, name="footprint normal")
        major = normalize_vector(self.major_axis_world, name="footprint major axis")
        minor = normalize_vector(self.minor_axis_world, name="footprint minor axis")
        if abs(float(np.dot(major, minor))) > 1.0e-9:
            raise ValueError("Footprint major/minor world axis는 서로 직교해야 합니다.")
        handedness = float(np.dot(np.cross(major, minor), normal))
        if not math.isclose(handedness, 1.0, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError(
                "Footprint axis는 cross(major, minor)=normal인 오른손 좌표계여야 합니다."
            )
        if self.major_radius_m + 1.0e-15 < self.minor_radius_m:
            raise ValueError("Footprint major radius는 minor radius 이상이어야 합니다.")
        if self.axis_convention != FOOTPRINT_AXIS_CONVENTION:
            raise ValueError(f"지원하지 않는 footprint axis convention입니다: {self.axis_convention!r}")
        object.__setattr__(self, "normal", _vec3(normal, name="footprint normal"))
        object.__setattr__(self, "major_axis_world", _vec3(major, name="footprint major axis"))
        object.__setattr__(self, "minor_axis_world", _vec3(minor, name="footprint minor axis"))

    @property
    def orientation_axis_world(self) -> Vec3:
        """이전 viewport consumer를 위한 major-axis alias."""

        return self.major_axis_world

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "hit_center_m": list(self.hit_center_m),
            "normal": list(self.normal),
            "major_radius_m": self.major_radius_m,
            "minor_radius_m": self.minor_radius_m,
            "major_axis_world": list(self.major_axis_world),
            "minor_axis_world": list(self.minor_axis_world),
            "orientation_axis_world": list(self.orientation_axis_world),
            "axis_convention": self.axis_convention,
            "area_m2": self.area_m2,
            "power_on_target_w": self.power_on_target_w,
            "clipped_by_target_bounds": self.clipped_by_target_bounds,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ViewportMesh:
    """렌더링 전용 STL triangle subset.

    ``triangles_world_m``은 simulation mesh의 복사된 표시 snapshot이다. 원본
    ``TriangleMesh``의 triangle 수와 index를 함께 기록해 decimation을 숨기지 않는다.
    """

    target_id: str
    asset_id: str
    material_ref: str
    triangles_world_m: tuple[Triangle3, ...]
    source_triangle_count: int
    display_triangle_indices: tuple[int, ...]
    display_triangle_limit: int
    display_selection: str
    geometry_semantics: str = "geometry_only_not_optical_scatterers"

    def __post_init__(self) -> None:
        triangles = np.asarray(self.triangles_world_m, dtype=np.float64)
        if triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or triangles.shape[0] == 0:
            raise ValueError("ViewportMesh triangles_world_m shape은 (N, 3, 3), N > 0이어야 합니다.")
        if not np.all(np.isfinite(triangles)):
            raise ValueError("ViewportMesh triangle 좌표는 모두 유한해야 합니다.")
        indices = tuple(int(index) for index in self.display_triangle_indices)
        if len(indices) != triangles.shape[0]:
            raise ValueError("ViewportMesh triangle payload와 display index 수가 일치해야 합니다.")
        if len(set(indices)) != len(indices) or tuple(sorted(indices)) != indices:
            raise ValueError("ViewportMesh display triangle index는 중복 없이 오름차순이어야 합니다.")
        if self.source_triangle_count <= 0:
            raise ValueError("ViewportMesh source_triangle_count는 0보다 커야 합니다.")
        if self.display_triangle_limit <= 0:
            raise ValueError("ViewportMesh display_triangle_limit는 0보다 커야 합니다.")
        if len(indices) > self.display_triangle_limit:
            raise ValueError("ViewportMesh display triangle 수가 표시 limit를 넘었습니다.")
        if indices[0] < 0 or indices[-1] >= self.source_triangle_count:
            raise ValueError("ViewportMesh display triangle index가 source 범위를 벗어났습니다.")
        if self.display_selection not in {
            "all",
            "deterministic_evenly_spaced_with_reported_hit_preservation",
        }:
            raise ValueError(f"지원하지 않는 mesh display selection입니다: {self.display_selection!r}")
        frozen_triangles: tuple[Triangle3, ...] = tuple(
            tuple(_vec3(vertex, name="viewport mesh vertex") for vertex in triangle)  # type: ignore[arg-type]
            for triangle in triangles
        )  # type: ignore[assignment]
        object.__setattr__(self, "triangles_world_m", frozen_triangles)
        object.__setattr__(self, "display_triangle_indices", indices)

    @property
    def display_triangle_count(self) -> int:
        return len(self.triangles_world_m)

    @property
    def decimated(self) -> bool:
        return self.display_triangle_count < self.source_triangle_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "asset_id": self.asset_id,
            "material_ref": self.material_ref,
            "triangles_world_m": [
                [list(vertex) for vertex in triangle]
                for triangle in self.triangles_world_m
            ],
            "source_triangle_count": self.source_triangle_count,
            "display_triangle_count": self.display_triangle_count,
            "display_triangle_indices": list(self.display_triangle_indices),
            "display_triangle_limit": self.display_triangle_limit,
            "display_selection": self.display_selection,
            "decimated": self.decimated,
            "geometry_semantics": self.geometry_semantics,
        }


@dataclass(frozen=True, slots=True)
class MeshHitOverlay:
    """M1 closest-hit report에서 가져온 geometry-only hit marker와 법선."""

    target_id: str
    asset_id: str
    point_m: Vec3
    geometric_normal: Vec3
    normal_end_m: Vec3
    distance_m: float
    triangle_index: int
    front_face: bool
    face: str
    contributes_to_center_ray_visibility: bool
    visibility_status: str
    source: str = "phase4_1_m1_report"
    geometry_only: bool = True
    status: str = "hit"

    def __post_init__(self) -> None:
        point = _vec3(self.point_m, name="mesh hit point")
        normal = _vec3(
            normalize_vector(self.geometric_normal, name="mesh hit geometric normal"),
            name="mesh hit geometric normal",
        )
        normal_end = _vec3(self.normal_end_m, name="mesh hit normal end")
        if not math.isfinite(self.distance_m) or self.distance_m <= 0.0:
            raise ValueError("Mesh hit distance_m은 0보다 큰 유한한 값이어야 합니다.")
        if self.triangle_index < 0:
            raise ValueError("Mesh hit triangle_index는 0 이상이어야 합니다.")
        if self.face not in {"front", "back"}:
            raise ValueError("Mesh hit face는 'front' 또는 'back'이어야 합니다.")
        if (self.face == "front") != self.front_face:
            raise ValueError("Mesh hit face와 front_face가 일치하지 않습니다.")
        if self.status != "hit" or not self.geometry_only:
            raise ValueError("MeshHitOverlay는 geometry-only hit만 표현합니다.")
        normal_segment = np.asarray(normal_end) - np.asarray(point)
        if float(np.linalg.norm(normal_segment)) <= 0.0:
            raise ValueError("Mesh hit normal 표시 길이는 0보다 커야 합니다.")
        if float(np.dot(normalize_vector(normal_segment, name="mesh hit normal segment"), normal)) < 1.0 - 1.0e-9:
            raise ValueError("Mesh hit normal_end_m은 geometric_normal 방향에 있어야 합니다.")
        object.__setattr__(self, "point_m", point)
        object.__setattr__(self, "geometric_normal", normal)
        object.__setattr__(self, "normal_end_m", normal_end)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "asset_id": self.asset_id,
            "point_m": list(self.point_m),
            "geometric_normal": list(self.geometric_normal),
            "normal_end_m": list(self.normal_end_m),
            "distance_m": self.distance_m,
            "triangle_index": self.triangle_index,
            "front_face": self.front_face,
            "face": self.face,
            "contributes_to_center_ray_visibility": self.contributes_to_center_ray_visibility,
            "visibility_status": self.visibility_status,
            "source": self.source,
            "geometry_only": self.geometry_only,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class PlacementConstraint:
    """향후 mate/constraint editor에서 사용할 serializable placement relation."""

    constraint_id: str
    constraint_type: str
    enabled: bool
    source_ref: str
    target_ref: str
    parameters: dict[str, Any]
    residual: float | None
    status: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "constraint_type": self.constraint_type,
            "enabled": self.enabled,
            "source_ref": self.source_ref,
            "target_ref": self.target_ref,
            "parameters": dict(self.parameters),
            "residual": self.residual,
            "status": self.status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class PlacementEdit:
    """UI에서 수행한 placement edit를 저장·재현하기 위한 단위."""

    edit_id: str
    element_id: str
    edit_type: str
    before_transform: dict[str, Any]
    after_transform: dict[str, Any]
    source: str
    timestamp: str | None
    validation_status: str
    serialized_config_patch: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edit_id": self.edit_id,
            "element_id": self.element_id,
            "edit_type": self.edit_type,
            "before_transform": dict(self.before_transform),
            "after_transform": dict(self.after_transform),
            "source": self.source,
            "timestamp": self.timestamp,
            "validation_status": self.validation_status,
            "serialized_config_patch": dict(self.serialized_config_patch),
        }


@dataclass(frozen=True, slots=True)
class ViewportScene:
    """UI renderer가 소비하는 전체 optical bench snapshot."""

    project_id: str
    scenario_id: str
    config_hash: str
    model_scope: str
    components: tuple[ViewportComponent, ...]
    ports: tuple[ViewportPort, ...]
    guides: tuple[GuideLine, ...]
    rays: tuple[RaySegment, ...]
    footprints: tuple[FootprintOverlay, ...]
    meshes: tuple[ViewportMesh, ...]
    mesh_hits: tuple[MeshHitOverlay, ...]
    constraints: tuple[PlacementConstraint, ...]
    placement_edits: tuple[PlacementEdit, ...]
    warnings: tuple[str, ...]
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "scenario_id": self.scenario_id,
            "config_hash": self.config_hash,
            "model_scope": self.model_scope,
            "components": [component.to_dict() for component in self.components],
            "ports": [port.to_dict() for port in self.ports],
            "guides": [guide.to_dict() for guide in self.guides],
            "rays": [ray.to_dict() for ray in self.rays],
            "footprints": [footprint.to_dict() for footprint in self.footprints],
            "meshes": [mesh.to_dict() for mesh in self.meshes],
            "mesh_hits": [hit.to_dict() for hit in self.mesh_hits],
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "placement_edits": [edit.to_dict() for edit in self.placement_edits],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class _ActiveStlTarget:
    target_id: str
    material_ref: str
    asset: Any
    mesh: TriangleMesh


def _stl_intersection_records(report_data: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    records = report_data.get("stl_intersections", ())
    if not isinstance(records, (list, tuple)):
        return ()
    return tuple(record for record in records if isinstance(record, dict))


def _resolve_active_stl_targets(
    project: Any,
    report_data: Mapping[str, Any],
) -> tuple[tuple[_ActiveStlTarget, ...], tuple[str, ...]]:
    records_by_target = {
        str(record.get("target_id")): record
        for record in _stl_intersection_records(report_data)
        if record.get("target_id") is not None
    }
    resolved: list[_ActiveStlTarget] = []
    warnings: list[str] = []
    for target in project.active_scenario["scene"]["targets"]:
        geometry = target["geometry"]
        if geometry["type"] != "stl_asset":
            continue
        target_id = str(target["id"])
        record = records_by_target.get(target_id, {})
        reported_asset_id = (
            str(record["asset_id"])
            if isinstance(record, dict) and record.get("asset_id") is not None
            else None
        )
        try:
            asset = resolve_project_stl_asset(project, geometry)
        except ValueError as exc:
            warnings.append(f"{target_id}: {exc}")
            continue
        if reported_asset_id is not None and reported_asset_id != asset.identifier:
            warnings.append(
                f"{target_id}: report asset_id {reported_asset_id!r}와 config asset "
                f"{asset.identifier!r}가 일치하지 않아 viewport mesh를 표시하지 않습니다."
            )
            continue
        try:
            mesh = world_triangle_mesh_from_asset(asset)
        except ValueError as exc:
            warnings.append(f"{target_id}: STL viewport world transform을 만들 수 없습니다: {exc}")
            continue
        resolved.append(
            _ActiveStlTarget(
                target_id=target_id,
                material_ref=str(target["material_ref"]),
                asset=asset,
                mesh=mesh,
            )
        )
    return tuple(resolved), tuple(warnings)


def _component_bounds(component: dict[str, Any]) -> tuple[Vec3, Vec3] | None:
    component_type = str(component.get("component_type", "unknown"))
    optical = component.get("optical", {})
    if component_type == "collimator":
        diameter = float(optical.get("clear_aperture_diameter_m", 0.01))
        half = 0.5 * diameter
        thickness = min(max(diameter * 0.25, 1.0e-3), 0.01)
        return ((-half, -half, -0.5 * thickness), (half, half, 0.5 * thickness))
    if component_type == "scanner_mirror":
        half_width = 0.5 * float(optical.get("clear_width_m", 0.02))
        half_height = 0.5 * float(optical.get("clear_height_m", 0.02))
        return ((-half_width, -half_height, -5.0e-4), (half_width, half_height, 5.0e-4))
    if component_type in {"fiber_source", "beam_source"}:
        half = 0.005
        return ((-half, -half, -half), (half, half, half))
    return None


def _target_bounds(geometry: dict[str, Any]) -> tuple[Vec3, Vec3] | None:
    if geometry.get("type") != "rectangle_plane":
        return None
    half_width = 0.5 * float(geometry["width_m"])
    half_height = 0.5 * float(geometry["height_m"])
    return ((-half_width, -half_height, 0.0), (half_width, half_height, 0.0))


def _make_components(
    project: Any,
    assembly: AssemblyPlacement,
    stl_targets: tuple[_ActiveStlTarget, ...],
) -> tuple[ViewportComponent, ...]:
    components: list[ViewportComponent] = []
    for element_id, element in assembly.elements.items():
        record = project.catalog[element.component_ref].data
        transform = element.T_world_from_component
        components.append(
            ViewportComponent(
                element_id=element_id,
                component_ref=element.component_ref,
                component_type=str(record.get("component_type", "unknown")),
                model_level=str(record.get("model_level", "unknown")),
                origin_world_m=_vec3(transform.translation_m, name=f"{element_id}.origin"),
                rotation_world_from_component=_matrix3(
                    transform.rotation,
                    name=f"{element_id}.rotation",
                ),
                bounds_m=_component_bounds(dict(record)),
                display_role="optical_component",
            )
        )

    scenario = project.active_scenario
    for target in scenario["scene"]["targets"]:
        geometry = target["geometry"]
        if geometry["type"] != "rectangle_plane":
            continue
        components.append(
            ViewportComponent(
                element_id=str(target["id"]),
                component_ref=str(target["material_ref"]),
                component_type="rectangle_plane_target",
                model_level=str(project.catalog[str(target["material_ref"])].data.get("model_level", "unknown")),
                origin_world_m=_vec3(geometry["center_m"], name=f"{target['id']}.center"),
                rotation_world_from_component=_frame_from_target_normal(
                    geometry["normal"],
                    geometry.get("width_axis"),
                    name=f"{target['id']}.normal",
                ),
                bounds_m=_target_bounds(dict(geometry)),
                display_role="target",
                editable=True,
            )
        )

    for stl_target in stl_targets:
        transform = stl_target.asset.T_parent_from_mesh
        material = project.catalog[stl_target.material_ref].data
        components.append(
            ViewportComponent(
                element_id=stl_target.target_id,
                component_ref=str(stl_target.asset.identifier),
                component_type="stl_asset_target",
                model_level=str(material.get("model_level", "unknown")),
                origin_world_m=_vec3(
                    transform.translation_m,
                    name=f"{stl_target.target_id}.stl_origin",
                ),
                rotation_world_from_component=_matrix3(
                    transform.rotation,
                    name=f"{stl_target.target_id}.stl_rotation",
                ),
                bounds_m=(
                    _vec3(stl_target.asset.audit.bounds_m[0], name="STL lower bounds"),
                    _vec3(stl_target.asset.audit.bounds_m[1], name="STL upper bounds"),
                ),
                display_role="target",
                editable=False,
            )
        )

    receiver = scenario["receiver"]
    reciprocal_receiver = receiver["architecture"] == "reciprocal_single_mode_fiber"
    components.append(
        ViewportComponent(
            element_id="receiver",
            component_ref=f"scenario:{scenario['scenario_id']}:receiver",
            component_type=(
                "virtual_aperture_regression_intermediate"
                if reciprocal_receiver
                else str(receiver["architecture"])
            ),
            model_level=(
                "analytical_regression_intermediate"
                if reciprocal_receiver
                else str(receiver["model_level"])
            ),
            origin_world_m=_vec3(receiver["position_m"], name="receiver.position"),
            rotation_world_from_component=_frame_from_z_axis(
                receiver["direction"],
                name="receiver.direction",
            ),
            bounds_m=((-0.0125, -0.0125, -0.001), (0.0125, 0.0125, 0.001)),
            display_role=(
                "virtual_aperture_reference"
                if reciprocal_receiver
                else "receiver"
            ),
            editable=True,
        )
    )
    return tuple(components)


def _make_ports(assembly: AssemblyPlacement) -> tuple[ViewportPort, ...]:
    ports: list[ViewportPort] = []
    for element_id, element in assembly.elements.items():
        for port_id, port in element.ports.items():
            transform = element.world_from_port(port_id)
            ports.append(
                ViewportPort(
                    element_id=element_id,
                    port_id=port_id,
                    role=port.role,
                    interface_type=port.interface_type,
                    reference_plane=port.reference_plane,
                    origin_world_m=_vec3(transform.translation_m, name=f"{element_id}.{port_id}.origin"),
                    axis_world=_vec3(transform.rotation[:, 2], name=f"{element_id}.{port_id}.axis"),
                    transverse_x_world=_vec3(
                        transform.rotation[:, 0],
                        name=f"{element_id}.{port_id}.x_axis",
                    ),
                    clear_aperture_m=None,
                )
            )
    return tuple(ports)


def _guide_length(report_data: dict[str, Any]) -> float:
    final_origin = np.asarray(
        report_data["optical_train"]["states"][-1]["beam_state"]["origin_m"],
        dtype=np.float64,
    )
    distances = []
    for footprint in report_data.get("target_footprints", ()):
        hit = footprint.get("hit_center_m")
        if hit is not None:
            distances.append(float(np.linalg.norm(np.asarray(hit, dtype=np.float64) - final_origin)))
    for record in _stl_intersection_records(report_data):
        intersection = record.get("intersection")
        if isinstance(intersection, dict) and intersection.get("point_m") is not None:
            distances.append(
                float(
                    np.linalg.norm(
                        np.asarray(intersection["point_m"], dtype=np.float64) - final_origin
                    )
                )
            )
    return max(distances, default=1.0)


def _add_line(
    guides: list[GuideLine],
    *,
    guide_id: str,
    guide_type: str,
    start: Any,
    end: Any,
    color: str,
    label: str,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    guides.append(
        GuideLine(
            guide_id=guide_id,
            guide_type=guide_type,
            start_m=_vec3(start, name=f"{guide_id}.start"),
            end_m=_vec3(end, name=f"{guide_id}.end"),
            color=color,
            label=label,
            enabled=True,
            source=source,
            metadata={} if metadata is None else dict(metadata),
        )
    )


def _reciprocal_path_records(report_data: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """지원 중인 Phase 2.4 report wrapper에서 reciprocal path record를 꺼낸다."""

    section = report_data.get("reciprocal_return")
    if not isinstance(section, dict):
        return ()

    candidates: list[Any] = []
    if isinstance(section.get("path"), dict):
        candidates.append(section["path"])
    elif isinstance(section.get("paths"), list):
        candidates.extend(section["paths"])
    else:
        results = section.get("results")
        if isinstance(results, list):
            candidates.extend(results)
        elif isinstance(results, dict):
            if (
                isinstance(results.get("path"), dict)
                or results.get("model") == "reciprocal_center_ray_geometry"
                or "target_hit_m" in results
            ):
                candidates.append(results)
            else:
                candidates.extend(results.values())
        elif "target_hit_m" in section:
            candidates.append(section)

    records: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        nested = candidate.get("path", candidate.get("result"))
        records.append(nested if isinstance(nested, dict) else candidate)
    return tuple(records)


def _fiber_coupling_record(report_data: dict[str, Any]) -> dict[str, Any] | None:
    """R3 fiber-coupling result를 strict report 위치에서만 읽는다."""

    section = report_data.get("reciprocal_return")
    if not isinstance(section, dict):
        return None
    coupling = section.get("fiber_coupling")
    return coupling if isinstance(coupling, dict) else None


def _detector_boundary_record(report_data: dict[str, Any]) -> dict[str, Any] | None:
    """R4 detector optical boundary를 strict report 위치에서만 읽는다."""

    section = report_data.get("reciprocal_return")
    if not isinstance(section, dict):
        return None
    detector = section.get("detector_boundary")
    return detector if isinstance(detector, dict) else None


def _intersection_point(hit_record: Any) -> Vec3 | None:
    """실제 hit가 명시된 경우에만 intersection point를 반환한다."""

    if not isinstance(hit_record, dict):
        return None
    intersection = hit_record.get("intersection")
    if isinstance(intersection, dict):
        if not bool(intersection.get("hit", False)):
            return None
        point = intersection.get("point_m")
        return None if point is None else _vec3(point, name="reciprocal intersection point")
    for key in ("actual_hit_m", "hit_point_m", "point_m"):
        if hit_record.get(key) is not None:
            return _vec3(hit_record[key], name=f"reciprocal {key}")
    return None


def _return_path_points(path: dict[str, Any]) -> tuple[tuple[str, Vec3], ...]:
    """Teleport 없이 target부터 연속된 실제 reciprocal hit만 반환한다."""

    target_value = path.get("target_hit_m")
    if target_value is None:
        return ()
    points: list[tuple[str, Vec3]] = [
        ("target", _vec3(target_value, name="reciprocal target_hit_m"))
    ]
    hit_specs = (
        ("mirror", "mirror_hit", "mirror_actual_hit_m"),
        ("collimator", "collimator_hit", "collimator_actual_hit_m"),
        ("fiber", "fiber_hit", "fiber_actual_hit_m"),
    )
    termination_reason = str(path.get("termination_reason") or "")
    termination_value = path.get("termination_point_m")
    for plane_name, hit_key, direct_key in hit_specs:
        point = _intersection_point(path.get(hit_key))
        if point is None and path.get(direct_key) is not None:
            point = _vec3(path[direct_key], name=f"reciprocal {direct_key}")
        if point is None and termination_reason.startswith(f"return_{plane_name}:"):
            if termination_value is not None:
                termination = _vec3(
                    termination_value,
                    name="reciprocal termination_point_m",
                )
                if _distance(points[-1][1], termination) > 1.0e-12:
                    point = termination
        if point is None:
            break
        points.append((plane_name, point))
        if termination_reason.startswith(f"return_{plane_name}:"):
            break
    return tuple(points)


_RETURN_SEGMENT_POWER_FIELDS = {
    ("target", "mirror"): "power_at_return_mirror_w",
    ("mirror", "collimator"): "power_after_return_mirror_w",
    ("collimator", "fiber"): "power_at_fiber_plane_w",
}


def _reciprocal_return_segment_power(
    report_data: dict[str, Any],
    *,
    start_plane: str,
    end_plane: str,
) -> tuple[float | None, str | None]:
    """R2 report의 plane power를 실제 reciprocal segment에 연결한다.

    R1 또는 unsupported/not-evaluated R2 report에는 ``return_power``가 없으므로
    명시적으로 ``(None, None)``을 반환한다. 계산된 0 W는 결측값과 구별해
    반드시 ``0.0``으로 보존한다.
    """

    field_name = _RETURN_SEGMENT_POWER_FIELDS.get((start_plane, end_plane))
    if field_name is None:
        return None, None
    section = report_data.get("reciprocal_return")
    if not isinstance(section, dict):
        return None, None
    return_power = section.get("return_power")
    if not isinstance(return_power, dict):
        return None, None
    if field_name not in return_power:
        raise ValueError(
            f"평가된 reciprocal_return.return_power에 {field_name!r}가 없습니다."
        )
    value = return_power[field_name]
    if isinstance(value, bool):
        raise ValueError(f"{field_name}은 0 이상의 유한한 power여야 합니다.")
    power_w = float(value)
    if not math.isfinite(power_w) or power_w < 0.0:
        raise ValueError(f"{field_name}은 0 이상의 유한한 power여야 합니다.")
    return power_w, field_name


def _display_triangle_indices(
    source_triangle_count: int,
    *,
    limit: int = MAX_VIEWPORT_MESH_TRIANGLES,
    preserve: tuple[int, ...] = (),
) -> tuple[int, ...]:
    """표시용 triangle index를 결정적으로 선택하고 reported hit face를 보존한다."""

    count = int(source_triangle_count)
    resolved_limit = int(limit)
    if count <= 0:
        raise ValueError("source_triangle_count는 0보다 커야 합니다.")
    if resolved_limit <= 0:
        raise ValueError("mesh display limit는 0보다 커야 합니다.")
    required = tuple(sorted({int(index) for index in preserve if 0 <= int(index) < count}))
    if len(required) > resolved_limit:
        raise ValueError("보존할 hit triangle 수가 mesh display limit보다 많습니다.")
    if count <= resolved_limit:
        return tuple(range(count))
    if resolved_limit == 1:
        return required[:1] if required else (0,)

    evenly_spaced = {
        int(round(index * (count - 1) / (resolved_limit - 1)))
        for index in range(resolved_limit)
    }
    selected = evenly_spaced | set(required)
    while len(selected) > resolved_limit:
        removable = sorted(selected - set(required), reverse=True)
        if not removable:
            break
        selected.remove(removable[0])
    if len(selected) < resolved_limit:
        # round()가 같은 index를 만든 경우에만 실행된다. 전체 N을 순회하지 않고
        # 낮은 index부터 빈 slot을 채워 결과를 deterministic하게 유지한다.
        candidate = 0
        while len(selected) < resolved_limit:
            selected.add(candidate)
            candidate += 1
    return tuple(sorted(selected))


def _reported_hit_indices(report_data: Mapping[str, Any], target_id: str) -> tuple[int, ...]:
    indices: list[int] = []
    for record in _stl_intersection_records(report_data):
        if str(record.get("target_id")) != target_id:
            continue
        intersection = record.get("intersection")
        if not isinstance(intersection, dict) or not bool(intersection.get("hit", False)):
            continue
        index = intersection.get("triangle_index")
        if isinstance(index, int) and not isinstance(index, bool):
            indices.append(index)
    return tuple(sorted(set(indices)))


def _make_meshes(
    stl_targets: tuple[_ActiveStlTarget, ...],
    report_data: Mapping[str, Any],
) -> tuple[tuple[ViewportMesh, ...], tuple[str, ...]]:
    meshes: list[ViewportMesh] = []
    warnings: list[str] = []
    for target in stl_targets:
        indices = _display_triangle_indices(
            target.mesh.triangle_count,
            preserve=_reported_hit_indices(report_data, target.target_id),
        )
        selected = target.mesh.triangle_vertices_m[np.asarray(indices, dtype=np.int64)]
        selection = (
            "all"
            if len(indices) == target.mesh.triangle_count
            else "deterministic_evenly_spaced_with_reported_hit_preservation"
        )
        viewport_mesh = ViewportMesh(
            target_id=target.target_id,
            asset_id=str(target.asset.identifier),
            material_ref=target.material_ref,
            triangles_world_m=tuple(
                tuple(_vec3(vertex, name="STL display vertex") for vertex in triangle)  # type: ignore[arg-type]
                for triangle in selected
            ),  # type: ignore[arg-type]
            source_triangle_count=target.mesh.triangle_count,
            display_triangle_indices=indices,
            display_triangle_limit=MAX_VIEWPORT_MESH_TRIANGLES,
            display_selection=selection,
        )
        meshes.append(viewport_mesh)
        if viewport_mesh.decimated:
            warnings.append(
                f"{target.target_id}: viewport는 STL {viewport_mesh.source_triangle_count}개 중 "
                f"{viewport_mesh.display_triangle_count}개 triangle만 결정적으로 표시합니다. "
                "Simulation closest-hit는 원본 전체 triangle을 사용합니다."
            )
    return tuple(meshes), tuple(warnings)


def _make_mesh_hits(
    stl_targets: tuple[_ActiveStlTarget, ...],
    report_data: Mapping[str, Any],
) -> tuple[tuple[MeshHitOverlay, ...], tuple[str, ...]]:
    targets_by_id = {target.target_id: target for target in stl_targets}
    overlays: list[MeshHitOverlay] = []
    warnings: list[str] = []
    for record in _stl_intersection_records(report_data):
        target_id = str(record.get("target_id", ""))
        target = targets_by_id.get(target_id)
        intersection = record.get("intersection")
        if target is None or not isinstance(intersection, dict):
            continue
        if not bool(intersection.get("hit", False)):
            continue
        required = {
            "point_m",
            "geometric_normal",
            "distance_m",
            "triangle_index",
            "front_face",
            "face",
        }
        missing = sorted(key for key in required if intersection.get(key) is None)
        if missing:
            warnings.append(
                f"{target_id}: STL hit report에 viewport 필드가 없습니다: {', '.join(missing)}"
            )
            continue
        triangle_index = int(intersection["triangle_index"])
        if not 0 <= triangle_index < target.mesh.triangle_count:
            warnings.append(
                f"{target_id}: report triangle_index {triangle_index}가 mesh 범위를 벗어났습니다."
            )
            continue
        point = np.asarray(intersection["point_m"], dtype=np.float64)
        normal = normalize_vector(
            intersection["geometric_normal"],
            name=f"{target_id} STL hit normal",
        )
        bounds = target.mesh.bounds_m
        normal_length = max(float(np.linalg.norm(bounds[1] - bounds[0])) * 0.08, 1.0e-6)
        overlays.append(
            MeshHitOverlay(
                target_id=target_id,
                asset_id=str(record.get("asset_id") or target.asset.identifier),
                point_m=_vec3(point, name=f"{target_id} STL hit point"),
                geometric_normal=_vec3(normal, name=f"{target_id} STL hit normal"),
                normal_end_m=_vec3(
                    point + normal_length * normal,
                    name=f"{target_id} STL hit normal end",
                ),
                distance_m=float(intersection["distance_m"]),
                triangle_index=triangle_index,
                front_face=bool(intersection["front_face"]),
                face=str(intersection["face"]),
                contributes_to_center_ray_visibility=bool(
                    record.get("contributes_to_center_ray_visibility", False)
                ),
                visibility_status=str(record.get("visibility_status", "candidate")),
            )
        )
    return tuple(overlays), tuple(warnings)


def _receiver_fov_directions(receiver: dict[str, Any], *, segments: int = 12) -> tuple[np.ndarray, ...]:
    look = normalize_vector(receiver["direction"], name="receiver direction")
    reference = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    if abs(float(np.dot(look, reference))) > 0.95:
        reference = np.array((0.0, 1.0, 0.0), dtype=np.float64)
    axis_u = normalize_vector(np.cross(look, reference), name="receiver FOV u axis")
    axis_v = normalize_vector(np.cross(look, axis_u), name="receiver FOV v axis")
    half_angle = 0.5 * float(receiver["full_fov_rad"])
    return tuple(
        normalize_vector(
            math.cos(half_angle) * look
            + math.sin(half_angle) * (math.cos(angle) * axis_u + math.sin(angle) * axis_v),
            name="receiver FOV boundary",
        )
        for angle in np.linspace(0.0, 2.0 * math.pi, int(segments), endpoint=False)
    )


def _make_guides(
    project: Any,
    assembly: AssemblyPlacement,
    report_data: dict[str, Any],
    components: tuple[ViewportComponent, ...],
) -> tuple[GuideLine, ...]:
    guides: list[GuideLine] = []
    length = max(_guide_length(report_data), 0.5)
    axis_length = min(max(length * 0.04, 0.05), 0.5)
    for component in components:
        origin = _point(component.origin_world_m)
        rotation = np.asarray(component.rotation_world_from_component, dtype=np.float64)
        for axis_index, axis_name, color in (
            (0, "x", "#d62728"),
            (1, "y", "#2ca02c"),
            (2, "z", "#1f77b4"),
        ):
            _add_line(
                guides,
                guide_id=f"{component.element_id}.frame.{axis_name}",
                guide_type="component_local_frame",
                start=origin,
                end=origin + axis_length * rotation[:, axis_index],
                color=color,
                label=f"{component.element_id} local {axis_name}",
                source="resolved_assembly",
            )

    for port in _make_ports(assembly):
        start = _point(port.origin_world_m)
        _add_line(
            guides,
            guide_id=f"{port.element_id}.{port.port_id}.axis",
            guide_type="port_axis",
            start=start,
            end=start + axis_length * normalize_vector(port.axis_world, name="port axis"),
            color="#17becf",
            label=f"{port.element_id}.{port.port_id} axis",
            source="resolved_assembly",
        )

    for report in report_data["optical_train"]["component_reports"]:
        if report.get("component_type") != "scanner_mirror":
            continue
        origin = np.asarray(report["output_beam_state"]["origin_m"], dtype=np.float64)
        normal = normalize_vector(report["surface_normal_world"], name="mirror normal")
        reflected = normalize_vector(report["reflected_direction"], name="reflected direction")
        _add_line(
            guides,
            guide_id=f"{report['element_id']}.mirror_normal",
            guide_type="mirror_normal",
            start=origin,
            end=origin + axis_length * normal,
            color="#167c2d",
            label="mirror normal",
            source="phase2_report",
        )
        _add_line(
            guides,
            guide_id=f"{report['element_id']}.reflected_direction",
            guide_type="reflected_direction",
            start=origin,
            end=origin + length * reflected,
            color="#e03131",
            label="reflected ray direction",
            source="phase2_report",
        )

    for target in project.active_scenario["scene"]["targets"]:
        geometry = target["geometry"]
        if geometry["type"] != "rectangle_plane":
            continue
        center = np.asarray(geometry["center_m"], dtype=np.float64)
        normal = normalize_vector(geometry["normal"], name="target normal")
        axis_u, axis_v = rectangle_plane_axes(
            normal,
            geometry.get("width_axis"),
        )
        half_width = 0.5 * float(geometry["width_m"])
        half_height = 0.5 * float(geometry["height_m"])
        corners = (
            center - half_width * axis_u - half_height * axis_v,
            center + half_width * axis_u - half_height * axis_v,
            center + half_width * axis_u + half_height * axis_v,
            center - half_width * axis_u + half_height * axis_v,
        )
        for index in range(4):
            _add_line(
                guides,
                guide_id=f"{target['id']}.target_plane_edge.{index}",
                guide_type="target_plane_edge",
                start=corners[index],
                end=corners[(index + 1) % 4],
                color="#7f7f00",
                label=f"{target['id']} plane",
                source="scenario",
            )

    receiver = project.active_scenario["receiver"]
    reciprocal_receiver = receiver["architecture"] == "reciprocal_single_mode_fiber"
    receiver_position = np.asarray(receiver["position_m"], dtype=np.float64)
    for index, direction in enumerate(_receiver_fov_directions(receiver)):
        _add_line(
            guides,
            guide_id=f"receiver.fov.{index}",
            guide_type="receiver_fov",
            start=receiver_position,
            end=receiver_position + length * direction,
            color="#ae3ec9",
            label=(
                "virtual aperture regression FOV"
                if reciprocal_receiver
                else "receiver FOV"
            ),
            source=(
                "scenario.virtual_aperture_regression_intermediate"
                if reciprocal_receiver
                else "scenario"
            ),
        )

    for path_index, path in enumerate(_reciprocal_path_records(report_data)):
        closure = path.get("closure") if isinstance(path.get("closure"), dict) else {}
        fiber_coupling = _fiber_coupling_record(report_data)
        detector_boundary = _detector_boundary_record(report_data)
        for plane_name, hit_key in (
            ("mirror", "mirror_hit"),
            ("collimator", "collimator_hit"),
            ("fiber", "fiber_hit"),
        ):
            hit = path.get(hit_key)
            actual = _intersection_point(hit)
            if actual is None or not isinstance(hit, dict):
                continue
            frame = hit.get("frame")
            expected = (
                frame.get("origin_m")
                if isinstance(frame, dict) and frame.get("origin_m") is not None
                else actual
            )
            metadata = {
                "plane_id": str(hit.get("plane_id", plane_name)),
                "actual_hit_m": list(actual),
                "expected_center_m": list(_vec3(expected, name=f"{plane_name} expected center")),
                "lateral_residual_m": hit.get("lateral_residual_m"),
                "angular_residual_rad": closure.get(f"{plane_name}_angular_residual_rad"),
                "aperture_status": hit.get("aperture_status"),
                "geometry_only": True,
            }
            label = f"return {plane_name} actual hit / residual"
            if plane_name == "fiber" and fiber_coupling is not None:
                metadata.update(
                    {
                        "fiber_coupling_model": fiber_coupling.get("model"),
                        "fiber_coupling_status": fiber_coupling.get("status"),
                        "fiber_coupling_efficiency": fiber_coupling.get(
                            "fiber_coupling_efficiency"
                        ),
                        "power_coupled_into_fiber_w": fiber_coupling.get(
                            "power_coupled_into_fiber_w"
                        ),
                        "coherent_field_status": fiber_coupling.get(
                            "coherent_field_status"
                        ),
                        "field_usable_for_coherent_propagation": fiber_coupling.get(
                            "field_usable_for_coherent_propagation"
                        ),
                    }
                )
                efficiency = fiber_coupling.get("fiber_coupling_efficiency")
                coupled_power = fiber_coupling.get("power_coupled_into_fiber_w")
                label = (
                    f"{label} | R3 eta={_format_optional_float(efficiency)}, "
                    f"P_coupled={_format_optional_float(coupled_power, suffix=' W')}"
                )
            if plane_name == "fiber" and detector_boundary is not None:
                metadata.update(
                    {
                        "detector_boundary_model": detector_boundary.get("model"),
                        "detector_input_status": detector_boundary.get("status"),
                        "power_at_detector_input_w": detector_boundary.get(
                            "power_at_detector_input_w"
                        ),
                        "fiber_coupled_to_detector_input_link_loss_db": (
                            detector_boundary.get(
                                "fiber_coupled_to_detector_input_link_loss_db"
                            )
                        ),
                        "target_to_detector_input_link_loss_db": detector_boundary.get(
                            "target_to_detector_input_link_loss_db"
                        ),
                        "source_to_detector_input_round_trip_link_loss_db": (
                            detector_boundary.get(
                                "source_to_detector_input_round_trip_link_loss_db"
                            )
                        ),
                        "detector_response_status": detector_boundary.get(
                            "detector_response_status"
                        ),
                        "detector_coherent_field_status": detector_boundary.get(
                            "coherent_field_status"
                        ),
                        "detector_field_usable_for_coherent_propagation": (
                            detector_boundary.get(
                                "field_usable_for_coherent_propagation"
                            )
                        ),
                    }
                )
            _add_line(
                guides,
                guide_id=f"reciprocal_return.{path_index}.{plane_name}_hit_residual",
                guide_type="return_hit_residual",
                start=actual,
                end=expected,
                color="#0ea5e9",
                label=label,
                source="phase2_4_r1_report",
                metadata=metadata,
            )
    return tuple(guides)


def _make_rays(report_data: dict[str, Any]) -> tuple[RaySegment, ...]:
    states = report_data["optical_train"]["states"]
    optical_path_id = str(report_data["optical_train"]["optical_path_id"])
    rays: list[RaySegment] = []
    for index, (start_state, end_state) in enumerate(zip(states, states[1:], strict=False)):
        start = np.asarray(start_state["beam_state"]["origin_m"], dtype=np.float64)
        end = np.asarray(end_state["beam_state"]["origin_m"], dtype=np.float64)
        delta = end - start
        if float(np.linalg.norm(delta)) <= 1e-12:
            continue
        direction = normalize_vector(delta, name=f"ray segment {index}")
        rays.append(
            RaySegment(
                segment_id=f"optical_train.{index}",
                start_m=_vec3(start, name=f"ray{index}.start"),
                end_m=_vec3(end, name=f"ray{index}.end"),
                direction=_vec3(direction, name=f"ray{index}.direction"),
                optical_path_id=optical_path_id,
                source_element_id=str(start_state["element_id"]),
                target_element_id=str(end_state["element_id"]),
                power_w=float(start_state["beam_state"]["power_w"]),
                radius_start_m=float(start_state["beam_state"]["radius_x_m"]),
                radius_end_m=float(end_state["beam_state"]["radius_x_m"]),
                status="propagated",
                label=f"{start_state['label']} → {end_state['label']}",
                propagation_role="transmit",
                plane_power_name=str(start_state["label"]),
            )
        )

    if states:
        final_state = states[-1]
        final_origin = np.asarray(final_state["beam_state"]["origin_m"], dtype=np.float64)
        for footprint in report_data["target_footprints"]:
            if not footprint.get("hit") or footprint.get("hit_center_m") is None:
                continue
            hit = np.asarray(footprint["hit_center_m"], dtype=np.float64)
            direction = normalize_vector(hit - final_origin, name="target hit ray")
            rays.append(
                RaySegment(
                    segment_id=f"target_hit.{footprint['target_id']}",
                    start_m=_vec3(final_origin, name="target_ray.start"),
                    end_m=_vec3(hit, name="target_ray.end"),
                    direction=_vec3(direction, name="target_ray.direction"),
                    optical_path_id=optical_path_id,
                    source_element_id=str(final_state["element_id"]),
                    target_element_id=str(footprint["target_id"]),
                    power_w=float(final_state["beam_state"]["power_w"]),
                    radius_start_m=float(final_state["beam_state"]["radius_x_m"]),
                    radius_end_m=float(footprint["beam_radius_x_m"]),
                    status="target_hit",
                    label=f"{final_state['label']} → {footprint['target_id']}",
                    propagation_role="transmit",
                    plane_power_name=str(final_state["label"]),
                )
            )

        rectangle_hit_targets = {
            str(footprint["target_id"])
            for footprint in report_data["target_footprints"]
            if footprint.get("hit") and footprint.get("hit_center_m") is not None
        }
        for record in _stl_intersection_records(report_data):
            target_id = str(record.get("target_id", ""))
            intersection = record.get("intersection")
            if (
                target_id in rectangle_hit_targets
                or not bool(record.get("contributes_to_center_ray_visibility", False))
                or not isinstance(intersection, dict)
                or not bool(intersection.get("hit", False))
                or intersection.get("point_m") is None
            ):
                continue
            hit = np.asarray(intersection["point_m"], dtype=np.float64)
            delta = hit - final_origin
            if float(np.linalg.norm(delta)) <= 1.0e-12:
                continue
            direction = normalize_vector(delta, name="STL target hit ray")
            rays.append(
                RaySegment(
                    segment_id=f"stl_target_hit.{target_id}",
                    start_m=_vec3(final_origin, name="STL target ray start"),
                    end_m=_vec3(hit, name="STL target ray end"),
                    direction=_vec3(direction, name="STL target ray direction"),
                    optical_path_id=optical_path_id,
                    source_element_id=str(final_state["element_id"]),
                    target_element_id=target_id,
                    power_w=None,
                    radius_start_m=None,
                    radius_end_m=None,
                    status="stl_target_hit_geometry_only",
                    label=f"{final_state['label']} → {target_id} STL closest hit",
                    propagation_role="transmit",
                    plane_power_name=None,
                )
            )

    reciprocal_section = report_data.get("reciprocal_return")
    return_path_config = (
        reciprocal_section.get("return_path", {})
        if isinstance(reciprocal_section, dict)
        else {}
    )
    if not isinstance(return_path_config, dict):
        return_path_config = {}
    target_id = (
        str(reciprocal_section.get("target_id", "target"))
        if isinstance(reciprocal_section, dict)
        else "target"
    )
    element_ids = {
        "target": target_id,
        "mirror": str(return_path_config.get("scanner_element_id", "scan_mirror")),
        "collimator": str(return_path_config.get("collimator_element_id", "collimator")),
        "fiber": str(return_path_config.get("fiber_element_id", "source")),
    }
    labels = {
        "target": target_id,
        "mirror": element_ids["mirror"],
        "collimator": element_ids["collimator"],
        "fiber": element_ids["fiber"],
    }
    for path_index, path in enumerate(_reciprocal_path_records(report_data)):
        points = _return_path_points(path)
        path_id = f"{optical_path_id}:reciprocal_return:{path_index}"
        terminated = bool(path.get("terminated", False))
        termination_point = path.get("termination_point_m")
        for segment_index, ((start_name, start), (end_name, end)) in enumerate(
            zip(points, points[1:], strict=False)
        ):
            delta = _point(end) - _point(start)
            if float(np.linalg.norm(delta)) <= 1.0e-12:
                continue
            is_terminated_segment = (
                terminated
                and termination_point is not None
                and np.allclose(
                    _point(end),
                    np.asarray(termination_point, dtype=np.float64),
                    rtol=0.0,
                    atol=1.0e-12,
                )
            )
            power_w, plane_power_name = _reciprocal_return_segment_power(
                report_data,
                start_plane=start_name,
                end_plane=end_name,
            )
            rays.append(
                RaySegment(
                    segment_id=(
                        f"reciprocal_return.{path_index}.{segment_index}."
                        f"{start_name}_to_{end_name}"
                    ),
                    start_m=start,
                    end_m=end,
                    direction=_vec3(
                        normalize_vector(delta, name="reciprocal return segment"),
                        name="reciprocal return direction",
                    ),
                    optical_path_id=path_id,
                    source_element_id=element_ids[start_name],
                    target_element_id=element_ids[end_name],
                    power_w=power_w,
                    radius_start_m=None,
                    radius_end_m=None,
                    status="return_terminated" if is_terminated_segment else "return_propagated",
                    label=f"Return: {labels[start_name]} → {labels[end_name]}",
                    propagation_role="return",
                    plane_power_name=plane_power_name,
                )
            )
    return tuple(rays)


def _make_footprints(report_data: dict[str, Any]) -> tuple[FootprintOverlay, ...]:
    overlays: list[FootprintOverlay] = []
    for footprint in report_data["target_footprints"]:
        if not footprint.get("hit") or footprint.get("hit_center_m") is None:
            continue
        target_intersection = footprint["target_intersection"]
        overlays.append(
            FootprintOverlay(
                target_id=str(footprint["target_id"]),
                hit_center_m=_vec3(footprint["hit_center_m"], name="footprint.hit_center"),
                normal=_vec3(target_intersection["target_normal"], name="footprint.normal"),
                major_radius_m=float(footprint["projected_footprint_major_radius_m"]),
                minor_radius_m=float(footprint["projected_footprint_minor_radius_m"]),
                major_axis_world=_vec3(
                    footprint["projected_footprint_major_axis_world"],
                    name="footprint.major_axis",
                ),
                minor_axis_world=_vec3(
                    footprint["projected_footprint_minor_axis_world"],
                    name="footprint.minor_axis",
                ),
                axis_convention=str(footprint["projected_footprint_axis_convention"]),
                area_m2=float(footprint["approximate_footprint_area_m2"]),
                power_on_target_w=float(footprint["estimated_power_on_target_w"]),
                clipped_by_target_bounds=bool(footprint["clipped_by_target_bounds"]),
                status="clipped" if footprint["clipped_by_target_bounds"] else "pass",
            )
        )
    return tuple(overlays)


def build_viewport_scene(
    project: Any,
    assembly: AssemblyPlacement | None = None,
    report: Phase2OpticalTrainReport | dict[str, Any] | None = None,
) -> ViewportScene:
    """Resolved config와 Phase 2.3 report에서 read-only viewport snapshot을 만든다."""

    resolved_assembly = assembly or resolve_assembly(
        project.active_scenario,
        project.catalog,
        source=str(project.project_path),
    )
    phase2_report = report or build_phase2_optical_train_report(project)
    report_data = _as_report_dict(phase2_report)
    stl_targets, stl_resolution_warnings = _resolve_active_stl_targets(project, report_data)
    components = _make_components(project, resolved_assembly, stl_targets)
    meshes, mesh_display_warnings = _make_meshes(stl_targets, report_data)
    mesh_hits, mesh_hit_warnings = _make_mesh_hits(stl_targets, report_data)
    warnings_list = [str(item) for item in report_data["accuracy"].get("warnings", ())]
    warnings_list.extend(stl_resolution_warnings)
    warnings_list.extend(mesh_display_warnings)
    warnings_list.extend(mesh_hit_warnings)
    if meshes:
        warnings_list.append(
            "Phase 4.1-M1 STL viewport는 전체 triangle을 사용한 CPU center-ray closest-hit의 "
            "geometry-only 결과입니다. STL footprint, radiometry, diffraction과 scatterer power는 "
            "표시하지 않습니다."
        )
    reciprocal_section = report_data.get("reciprocal_return")
    if isinstance(reciprocal_section, dict) and _reciprocal_path_records(report_data):
        return_power = reciprocal_section.get("return_power")
        fiber_coupling = _fiber_coupling_record(report_data)
        detector_boundary = _detector_boundary_record(report_data)
        if isinstance(return_power, dict):
            if fiber_coupling is None:
                warnings_list.append(
                    "Phase 2.4-R2 return overlay의 power는 작은 Lambertian footprint와 "
                    "center-ray aperture pass/miss를 사용한 scalar analytical plane power입니다. "
                    "Return beam radius, spatial aperture integral, coherent field와 fiber mode "
                    "coupling을 나타내지 않습니다."
                )
            else:
                warnings_list.append(
                    "Return ray segment의 power는 계속 Phase 2.4-R2 fiber-plane 이전의 "
                    "scalar analytical plane power입니다. Phase 2.4-R3 결합 결과는 fiber "
                    "reference point metadata에만 표시하며 새 ray/beam/field를 만들지 않습니다."
                )
            warnings_list.extend(str(item) for item in return_power.get("warnings", ()))
        else:
            warnings_list.append(
                "Phase 2.4-R1 return overlay는 center-ray geometry-only이며 power, radiance, "
                "diffraction 또는 fiber coupling을 나타내지 않습니다."
            )
        warnings_list.extend(str(item) for item in reciprocal_section.get("warnings", ()))
        if fiber_coupling is not None:
            warnings_list.append(
                "Phase 2.4-R3 gaussian_alignment_proxy는 Lambertian diffuse-return의 "
                "upper-bound/reference 정렬 지표이며 calibrated hardware prediction이 아닙니다. "
                "Mode overlap의 임의 기준 위상은 coherent output으로 사용할 수 없습니다."
            )
            warnings_list.extend(
                str(item) for item in fiber_coupling.get("warnings", ())
            )
        if detector_boundary is not None:
            warnings_list.append(
                "Phase 2.4-R4 detector 결과는 fiber output 뒤 passive duplexer의 "
                "비공간 optical boundary입니다. Viewport는 detector component, ray, beam 또는 "
                "field를 새로 만들지 않고 fiber reference metadata만 표시합니다. "
                "Detector response와 hardware calibration은 평가하지 않습니다."
            )
            warnings_list.extend(
                str(item) for item in detector_boundary.get("warnings", ())
            )
        for path in _reciprocal_path_records(report_data):
            warnings_list.extend(str(item) for item in path.get("warnings", ()))
    warnings = tuple(dict.fromkeys(warnings_list))
    return ViewportScene(
        project_id=str(project.project["project_id"]),
        scenario_id=str(project.active_scenario["scenario_id"]),
        config_hash=str(project.config_hash),
        model_scope=str(report_data["accuracy"]["scope"]),
        components=components,
        ports=_make_ports(resolved_assembly),
        guides=_make_guides(project, resolved_assembly, report_data, components),
        rays=_make_rays(report_data),
        footprints=_make_footprints(report_data),
        meshes=meshes,
        mesh_hits=mesh_hits,
        constraints=(),
        placement_edits=(),
        warnings=warnings,
    )
