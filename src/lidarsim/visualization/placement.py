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
from lidarsim.geometry.transform import normalize_vector


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
        scanner_position = resolved_assembly[
            str(scenario["scanner"]["element_id"])
        ].T_world_from_component.translation_m
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

    receiver = np.asarray(scenario["receiver"]["position_m"], dtype=np.float64)
    full_scene_points.append(receiver.reshape(1, 3))
    axis_3d.scatter(*receiver, marker="^", color="#e377c2", s=55, label="receiver")

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
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=int(dpi), facecolor="white")
    plt.close(figure)
    return destination
