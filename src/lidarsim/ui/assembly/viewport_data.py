"""3D optical bench viewport data contract.

이 module은 UI가 숨겨진 source of truth가 되지 않도록, resolved config와
structured report에서만 viewport snapshot을 만든다. Streamlit, Plotly,
Three.js 또는 Matplotlib renderer는 이 contract만 소비한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from lidarsim.geometry import AssemblyPlacement, resolve_assembly
from lidarsim.geometry.transform import normalize_vector
from lidarsim.results import Phase2OpticalTrainReport, build_phase2_optical_train_report
from lidarsim.scene.targets import rectangle_plane_axes


Vec3 = tuple[float, float, float]
Mat3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


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


def _frame_from_target_normal(normal: Any, *, name: str) -> Mat3:
    unit_normal = normalize_vector(normal, name=name)
    width_axis, _ = rectangle_plane_axes(unit_normal)
    height_axis = normalize_vector(
        np.cross(unit_normal, width_axis),
        name=f"{name} frame y axis",
    )
    return _matrix3(
        np.column_stack((width_axis, height_axis, unit_normal)),
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
    power_w: float
    radius_start_m: float | None
    radius_end_m: float | None
    status: str
    label: str

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
        }


@dataclass(frozen=True, slots=True)
class FootprintOverlay:
    """Target surface 위 projected footprint 표시 단위."""

    target_id: str
    hit_center_m: Vec3
    normal: Vec3
    major_radius_m: float
    minor_radius_m: float
    orientation_axis_world: Vec3
    area_m2: float
    power_on_target_w: float
    clipped_by_target_bounds: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "hit_center_m": list(self.hit_center_m),
            "normal": list(self.normal),
            "major_radius_m": self.major_radius_m,
            "minor_radius_m": self.minor_radius_m,
            "orientation_axis_world": list(self.orientation_axis_world),
            "area_m2": self.area_m2,
            "power_on_target_w": self.power_on_target_w,
            "clipped_by_target_bounds": self.clipped_by_target_bounds,
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
    constraints: tuple[PlacementConstraint, ...]
    placement_edits: tuple[PlacementEdit, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "scenario_id": self.scenario_id,
            "config_hash": self.config_hash,
            "model_scope": self.model_scope,
            "components": [component.to_dict() for component in self.components],
            "ports": [port.to_dict() for port in self.ports],
            "guides": [guide.to_dict() for guide in self.guides],
            "rays": [ray.to_dict() for ray in self.rays],
            "footprints": [footprint.to_dict() for footprint in self.footprints],
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "placement_edits": [edit.to_dict() for edit in self.placement_edits],
            "warnings": list(self.warnings),
        }


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


def _make_components(project: Any, assembly: AssemblyPlacement) -> tuple[ViewportComponent, ...]:
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
                    name=f"{target['id']}.normal",
                ),
                bounds_m=_target_bounds(dict(geometry)),
                display_role="target",
                editable=True,
            )
        )

    receiver = scenario["receiver"]
    components.append(
        ViewportComponent(
            element_id="receiver",
            component_ref=f"scenario:{scenario['scenario_id']}:receiver",
            component_type=str(receiver["architecture"]),
            model_level=str(receiver["model_level"]),
            origin_world_m=_vec3(receiver["position_m"], name="receiver.position"),
            rotation_world_from_component=_frame_from_z_axis(
                receiver["direction"],
                name="receiver.direction",
            ),
            bounds_m=((-0.0125, -0.0125, -0.001), (0.0125, 0.0125, 0.001)),
            display_role="receiver",
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
    for footprint in report_data["target_footprints"]:
        hit = footprint.get("hit_center_m")
        if hit is not None:
            distances.append(float(np.linalg.norm(np.asarray(hit, dtype=np.float64) - final_origin)))
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
        )
    )


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
) -> tuple[GuideLine, ...]:
    guides: list[GuideLine] = []
    length = max(_guide_length(report_data), 0.5)
    axis_length = min(max(length * 0.04, 0.05), 0.5)
    for component in _make_components(project, assembly):
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
        reference = np.array((0.0, 0.0, 1.0), dtype=np.float64)
        if abs(float(np.dot(normal, reference))) > 0.95:
            reference = np.array((0.0, 1.0, 0.0), dtype=np.float64)
        axis_u = normalize_vector(np.cross(normal, reference), name="target u")
        axis_v = normalize_vector(np.cross(normal, axis_u), name="target v")
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
    receiver_position = np.asarray(receiver["position_m"], dtype=np.float64)
    for index, direction in enumerate(_receiver_fov_directions(receiver)):
        _add_line(
            guides,
            guide_id=f"receiver.fov.{index}",
            guide_type="receiver_fov",
            start=receiver_position,
            end=receiver_position + length * direction,
            color="#ae3ec9",
            label="receiver FOV",
            source="scenario",
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
                orientation_axis_world=_vec3(
                    target_intersection["width_axis_world"],
                    name="footprint.orientation",
                ),
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
    warnings = tuple(str(item) for item in report_data["accuracy"].get("warnings", ()))
    return ViewportScene(
        project_id=str(project.project["project_id"]),
        scenario_id=str(project.active_scenario["scenario_id"]),
        config_hash=str(project.config_hash),
        model_scope=str(report_data["accuracy"]["scope"]),
        components=_make_components(project, resolved_assembly),
        ports=_make_ports(resolved_assembly),
        guides=_make_guides(project, resolved_assembly, report_data),
        rays=_make_rays(report_data),
        footprints=_make_footprints(report_data),
        constraints=(),
        placement_edits=(),
        warnings=warnings,
    )
