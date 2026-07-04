"""Headless 환경에서 저장 가능한 최소 2D/3D placement viewer."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "optic-ray-matplotlib"),
)

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from lidarsim.geometry import AssemblyPlacement, resolve_assembly
from lidarsim.geometry.transform import RigidTransform, normalize_vector


_ELEMENT_COLORS = {
    "fiber_source": "#1f77b4",
    "collimator": "#ff7f0e",
    "scanner_mirror": "#2ca02c",
}


def _configure_korean_font() -> bool:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            font_manager.fontManager.addfont(path)
            family = font_manager.FontProperties(fname=path).get_name()
        except (OSError, RuntimeError):
            continue
        matplotlib.rcParams["font.family"] = family
        matplotlib.rcParams["axes.unicode_minus"] = False
        return True
    return False


_KOREAN_FONT = _configure_korean_font()


def _label(korean: str, english: str) -> str:
    return korean if _KOREAN_FONT else english


def _element_color(project: Any, component_ref: str) -> str:
    component_type = str(project.catalog[component_ref].data.get("component_type", "unknown"))
    return _ELEMENT_COLORS.get(component_type, "#9467bd")


def _target_polygon(target: Any) -> np.ndarray | None:
    geometry = target["geometry"]
    if geometry["type"] != "rectangle_plane":
        return None
    center = np.asarray(geometry["center_m"], dtype=np.float64)
    normal = normalize_vector(geometry["normal"], name=f"target {target['id']} normal")
    reference = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    if abs(float(np.dot(normal, reference))) > 0.95:
        reference = np.array((0.0, 1.0, 0.0), dtype=np.float64)
    axis_u = normalize_vector(np.cross(normal, reference), name="target plane u axis")
    axis_v = normalize_vector(np.cross(normal, axis_u), name="target plane v axis")
    half_width = float(geometry["width_m"]) / 2.0
    half_height = float(geometry["height_m"]) / 2.0
    return np.asarray(
        [
            center - half_width * axis_u - half_height * axis_v,
            center + half_width * axis_u - half_height * axis_v,
            center + half_width * axis_u + half_height * axis_v,
            center - half_width * axis_u + half_height * axis_v,
        ]
    )


def _box_corners(bounds_m: np.ndarray, transform: Any) -> np.ndarray:
    minimum, maximum = bounds_m
    corners = np.asarray(
        [
            (x, y, z)
            for x in (minimum[0], maximum[0])
            for y in (minimum[1], maximum[1])
            for z in (minimum[2], maximum[2])
        ],
        dtype=np.float64,
    )
    return np.asarray([transform.transform_point(corner) for corner in corners])


def _draw_box(ax: Any, corners: np.ndarray, *, color: str = "#8c564b") -> None:
    edges = (
        (0, 1),
        (0, 2),
        (0, 4),
        (1, 3),
        (1, 5),
        (2, 3),
        (2, 6),
        (3, 7),
        (4, 5),
        (4, 6),
        (5, 7),
        (6, 7),
    )
    for start, end in edges:
        segment = corners[[start, end]]
        ax.plot(segment[:, 0], segment[:, 1], segment[:, 2], color=color, linewidth=1.0)


def _set_3d_limits(ax: Any, points: list[np.ndarray]) -> None:
    stacked = np.vstack(points) if points else np.zeros((1, 3), dtype=np.float64)
    minimum = np.min(stacked, axis=0)
    maximum = np.max(stacked, axis=0)
    center = (minimum + maximum) / 2.0
    extent = maximum - minimum
    extent = np.maximum(extent, max(float(np.max(extent)) * 0.05, 0.1))
    padded = extent * 1.1
    ax.set_xlim(center[0] - padded[0] / 2.0, center[0] + padded[0] / 2.0)
    ax.set_ylim(center[1] - padded[1] / 2.0, center[1] + padded[1] / 2.0)
    ax.set_zlim(center[2] - padded[2] / 2.0, center[2] + padded[2] / 2.0)
    ax.set_box_aspect(padded)


def _draw_optical_paths(ax: Any, scenario: Any, assembly: AssemblyPlacement) -> None:
    for optical_path in scenario["optical_assembly"]["optical_paths"]:
        points = np.asarray(
            [
                assembly[str(element_id)].T_world_from_component.translation_m
                for element_id in optical_path["elements"]
            ]
        )
        ax.plot(
            points[:, 0],
            points[:, 1],
            points[:, 2],
            color="#d62728",
            linewidth=1.8,
            label=f"optical path: {optical_path['id']}",
        )


def _reflect(direction: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Unit incident direction을 flat-mirror normal로 반사한다."""

    incident = normalize_vector(direction, name="incident direction")
    surface_normal = normalize_vector(normal, name="mirror normal")
    return normalize_vector(
        incident - 2.0 * float(np.dot(incident, surface_normal)) * surface_normal,
        name="reflected direction",
    )


def _scene_guide_range(scenario: Any, scanner_position: np.ndarray) -> float:
    ranges = []
    for target in scenario["scene"]["targets"]:
        geometry = target["geometry"]
        if geometry["type"] == "rectangle_plane":
            center = np.asarray(geometry["center_m"], dtype=np.float64)
            ranges.append(float(np.linalg.norm(center - scanner_position)))
    return max(ranges, default=10.0)


def _scanner_geometry(
    project: Any,
    scenario: Any,
    assembly: AssemblyPlacement,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    """Mirror polygon, zero normal과 declared scan-limit directions를 계산한다."""

    scanner = scenario["scanner"]
    element = assembly[str(scanner["element_id"])]
    record = project.catalog[element.component_ref].data
    optical = record["optical"]
    mechanical = record["mechanical"]
    transform = element.T_world_from_component
    pivot_local = np.asarray(mechanical["pivot_local_m"], dtype=np.float64)
    pivot_world = transform.transform_point(pivot_local)
    normal_world = transform.transform_normal(mechanical["surface_normal_local"])
    axis_world = normalize_vector(scanner["rotation_axis_world"], name="scanner axis")
    transverse_world = normalize_vector(
        np.cross(axis_world, normal_world),
        name="mirror transverse axis",
    )
    half_width = float(optical["clear_width_m"]) / 2.0
    half_height = float(optical["clear_height_m"]) / 2.0
    polygon = np.asarray(
        [
            pivot_world - half_width * transverse_world - half_height * axis_world,
            pivot_world + half_width * transverse_world - half_height * axis_world,
            pivot_world + half_width * transverse_world + half_height * axis_world,
            pivot_world - half_width * transverse_world + half_height * axis_world,
        ]
    )

    incident: np.ndarray | None = None
    scanner_id = str(scanner["element_id"])
    for optical_path in scenario["optical_assembly"]["optical_paths"]:
        element_ids = [str(value) for value in optical_path["elements"]]
        if scanner_id not in element_ids:
            continue
        index = element_ids.index(scanner_id)
        if index > 0:
            previous = assembly[element_ids[index - 1]].T_world_from_component.translation_m
            incident = normalize_vector(pivot_world - previous, name="scanner incident direction")
            break
    if incident is None:
        incident = transform.transform_direction((0.0, 0.0, 1.0), normalize=True)

    amplitude = float(scanner["mechanical_amplitude_rad"])
    directions = []
    for angle in (-amplitude, 0.0, amplitude):
        rotation = RigidTransform.from_axis_angle(axis_world, angle)
        rotated_normal = rotation.transform_normal(normal_world)
        directions.append(_reflect(incident, rotated_normal))
    return pivot_world, polygon, normal_world, tuple(directions)


def _receiver_fov_directions(receiver: Any, *, segments: int = 12) -> tuple[np.ndarray, ...]:
    """Receiver full FOV를 원뿔 경계 unit direction들로 변환한다."""

    look = normalize_vector(receiver["direction"], name="receiver direction")
    reference = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    if abs(float(np.dot(look, reference))) > 0.95:
        reference = np.array((0.0, 1.0, 0.0), dtype=np.float64)
    axis_u = normalize_vector(np.cross(look, reference), name="receiver FOV u axis")
    axis_v = normalize_vector(np.cross(look, axis_u), name="receiver FOV v axis")
    half_angle = float(receiver["full_fov_rad"]) / 2.0
    return tuple(
        normalize_vector(
            np.cos(half_angle) * look
            + np.sin(half_angle)
            * (np.cos(angle) * axis_u + np.sin(angle) * axis_v),
            name="receiver FOV boundary",
        )
        for angle in np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    )


def render_placement_view(
    project: Any,
    output_path: str | Path,
    assembly: AssemblyPlacement | None = None,
    *,
    dpi: int = 150,
) -> Path:
    """Active scenario의 full 3D scene와 X-Z assembly detail을 PNG로 저장한다."""

    resolved_assembly = assembly or resolve_assembly(
        project.active_scenario,
        project.catalog,
        source=str(project.project_path),
    )
    scenario = project.active_scenario
    figure = plt.figure(figsize=(13.0, 6.2), constrained_layout=True)
    axis_3d = figure.add_subplot(1, 2, 1, projection="3d")
    axis_2d = figure.add_subplot(1, 2, 2)
    full_scene_points: list[np.ndarray] = []

    scanner_position, mirror_polygon, mirror_normal, scan_directions = _scanner_geometry(
        project,
        scenario,
        resolved_assembly,
    )
    guide_range = _scene_guide_range(scenario, scanner_position)

    _draw_optical_paths(axis_3d, scenario, resolved_assembly)
    assembly_positions: list[np.ndarray] = []
    for element_id, element in resolved_assembly.elements.items():
        position = element.T_world_from_component.translation_m
        assembly_positions.append(position)
        full_scene_points.append(position.reshape(1, 3))
        color = _element_color(project, element.component_ref)
        axis_3d.scatter(*position, color=color, s=45, depthshade=False)
        axis_2d.scatter(position[0], position[2], color=color, s=50, zorder=3)
        axis_2d.annotate(element_id, (position[0], position[2]), xytext=(5, 4), textcoords="offset points")

        for port_id in element.ports:
            port_transform = element.world_from_port(port_id)
            origin = port_transform.translation_m
            direction = port_transform.rotation[:, 2]
            axis_3d.quiver(
                *origin,
                *direction,
                length=0.25,
                normalize=True,
                color="#17becf",
                linewidth=1.0,
            )
            axis_2d.quiver(
                origin[0],
                origin[2],
                direction[0],
                direction[2],
                angles="xy",
                scale_units="xy",
                scale=100.0,
                color="#17becf",
                width=0.006,
                zorder=2,
            )

    assembly_center = np.mean(np.asarray(assembly_positions), axis=0)
    axis_3d.text(*assembly_center, " optical assembly", fontsize=8)

    full_scene_points.append(mirror_polygon)
    axis_3d.add_collection3d(
        Poly3DCollection(
            [mirror_polygon],
            facecolors="#9be7a3",
            edgecolors="#167c2d",
            alpha=0.75,
        )
    )
    normal_end = scanner_position + mirror_normal * max(guide_range * 0.05, 0.10)
    axis_3d.plot(
        [scanner_position[0], normal_end[0]],
        [scanner_position[1], normal_end[1]],
        [scanner_position[2], normal_end[2]],
        color="#167c2d",
        linewidth=1.2,
        label="mirror zero normal",
    )
    for index, direction in enumerate(scan_directions):
        endpoint = scanner_position + direction * guide_range
        full_scene_points.append(endpoint.reshape(1, 3))
        axis_3d.plot(
            [scanner_position[0], endpoint[0]],
            [scanner_position[1], endpoint[1]],
            [scanner_position[2], endpoint[2]],
            color="#f59f00" if index != 1 else "#e03131",
            linestyle="--" if index != 1 else ":",
            linewidth=1.3,
            label="declared scan limits" if index == 0 else "zero-angle guide" if index == 1 else None,
        )

    axis_2d.plot(
        mirror_polygon[[0, 1, 2, 3, 0], 0],
        mirror_polygon[[0, 1, 2, 3, 0], 2],
        color="#167c2d",
        linewidth=2.0,
        zorder=4,
    )
    detail_length = max(float(np.ptp(np.asarray(assembly_positions)[:, [0, 2]])) * 0.18, 0.015)
    axis_2d.quiver(
        scanner_position[0],
        scanner_position[2],
        mirror_normal[0],
        mirror_normal[2],
        angles="xy",
        scale_units="xy",
        scale=1.0 / detail_length,
        color="#167c2d",
        width=0.008,
        zorder=5,
    )
    for direction in scan_directions:
        axis_2d.quiver(
            scanner_position[0],
            scanner_position[2],
            direction[0],
            direction[2],
            angles="xy",
            scale_units="xy",
            scale=1.0 / detail_length,
            color="#f59f00",
            width=0.005,
            alpha=0.8,
            zorder=4,
        )

    for optical_path in scenario["optical_assembly"]["optical_paths"]:
        points = np.asarray(
            [
                resolved_assembly[str(element_id)].T_world_from_component.translation_m
                for element_id in optical_path["elements"]
            ]
        )
        axis_2d.plot(points[:, 0], points[:, 2], color="#d62728", linewidth=1.5, zorder=1)

    for target in scenario["scene"]["targets"]:
        polygon = _target_polygon(target)
        if polygon is None:
            continue
        full_scene_points.append(polygon)
        collection = Poly3DCollection(
            [polygon],
            facecolors="#bcbd22",
            edgecolors="#7f7f00",
            alpha=0.25,
        )
        axis_3d.add_collection3d(collection)
        center = np.mean(polygon, axis=0)
        axis_3d.text(*center, f" {target['id']}", fontsize=8)
        guide = np.vstack((scanner_position, center))
        axis_3d.plot(
            guide[:, 0],
            guide[:, 1],
            guide[:, 2],
            linestyle="--",
            color="#7f7f7f",
            linewidth=1.0,
            label="scanner-target guide",
        )

        receiver_position = np.asarray(scenario["receiver"]["position_m"], dtype=np.float64)
        return_guide = np.vstack((center, receiver_position))
        axis_3d.plot(
            return_guide[:, 0],
            return_guide[:, 1],
            return_guide[:, 2],
            linestyle=":",
            color="#c2255c",
            linewidth=1.1,
            label="return-path guide",
        )

    receiver = np.asarray(scenario["receiver"]["position_m"], dtype=np.float64)
    full_scene_points.append(receiver.reshape(1, 3))
    axis_3d.scatter(*receiver, marker="^", color="#e377c2", s=55, label="receiver")
    for index, direction in enumerate(_receiver_fov_directions(scenario["receiver"])):
        endpoint = receiver + direction * guide_range
        full_scene_points.append(endpoint.reshape(1, 3))
        axis_3d.plot(
            [receiver[0], endpoint[0]],
            [receiver[1], endpoint[1]],
            [receiver[2], endpoint[2]],
            color="#ae3ec9",
            linewidth=0.6,
            alpha=0.45,
            label="declared receiver FOV" if index == 0 else None,
        )

    for asset in project.assets.meshes.values():
        if asset.data["placement"]["parent_frame"] != "world":
            continue
        corners = _box_corners(asset.audit.bounds_m, asset.T_parent_from_mesh)
        full_scene_points.append(corners)
        _draw_box(axis_3d, corners)

    _set_3d_limits(axis_3d, full_scene_points)
    axis_3d.set_title(_label("3D 전체 scene", "3D full scene"))
    axis_3d.set_xlabel("X (m)")
    axis_3d.set_ylabel("Y (m)")
    axis_3d.set_zlabel("Z (m)")
    handles, labels = axis_3d.get_legend_handles_labels()
    if handles:
        unique = dict(zip(labels, handles, strict=False))
        axis_3d.legend(unique.values(), unique.keys(), loc="upper left", fontsize=7)

    positions = np.asarray(assembly_positions)
    x_min, x_max = float(np.min(positions[:, 0])), float(np.max(positions[:, 0]))
    z_min, z_max = float(np.min(positions[:, 2])), float(np.max(positions[:, 2]))
    span = max(x_max - x_min, z_max - z_min, 0.02)
    padding = span * 0.25
    axis_2d.set_xlim(x_min - padding, x_max + padding)
    axis_2d.set_ylim(z_min - padding, z_max + padding)
    axis_2d.set_aspect("equal", adjustable="box")
    axis_2d.grid(True, alpha=0.3)
    axis_2d.set_title(_label("광학 assembly X-Z 상세", "Optical assembly X-Z detail"))
    axis_2d.set_xlabel("X (m)")
    axis_2d.set_ylabel("Z (m)")

    figure.suptitle(
        f"{project.project['project_id']} / {scenario['scenario_id']}\n"
        + _label(
            f"config {project.config_hash[:12]}… | 빨강=optical path, 청록=port +z axis",
            f"config {project.config_hash[:12]}... | red=optical path, cyan=port +z axis",
        ),
        fontsize=11,
    )
    figure.text(
        0.5,
        0.01,
        _label(
            "점선 scan/FOV/return은 설정값 기반 기하학 가이드이며, 전파·수신광 계산 결과가 아닙니다.",
            "Dashed scan/FOV/return lines are configuration guides, not propagated-power results.",
        ),
        ha="center",
        fontsize=8,
        color="#854d0e",
    )
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=int(dpi), facecolor="white")
    plt.close(figure)
    return destination
