"""Read-only optical assembly workspace visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from lidarsim.geometry.transform import normalize_vector
from lidarsim.ui.assembly import ViewportScene


def _as_array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _scene_points(data: dict[str, Any]) -> np.ndarray:
    points: list[np.ndarray] = []
    for component in data["components"]:
        points.append(_as_array(component["origin_world_m"]))
    for port in data["ports"]:
        points.append(_as_array(port["origin_world_m"]))
    for guide in data["guides"]:
        points.append(_as_array(guide["start_m"]))
        points.append(_as_array(guide["end_m"]))
    for ray in data["rays"]:
        points.append(_as_array(ray["start_m"]))
        points.append(_as_array(ray["end_m"]))
    for footprint in data["footprints"]:
        points.append(_as_array(footprint["hit_center_m"]))
    for mesh in data.get("meshes", ()):
        triangles = _as_array(mesh["triangles_world_m"])
        points.extend(triangles.reshape(-1, 3))
    for hit in data.get("mesh_hits", ()):
        points.append(_as_array(hit["point_m"]))
        points.append(_as_array(hit["normal_end_m"]))
    if not points:
        return np.zeros((1, 3), dtype=np.float64)
    return np.vstack(points)


def _detail_points(data: dict[str, Any]) -> np.ndarray:
    points: list[np.ndarray] = []
    target_ids = {
        str(component["element_id"])
        for component in data["components"]
        if component.get("display_role") == "target"
    }
    for component in data["components"]:
        if component.get("display_role") != "target":
            points.append(_as_array(component["origin_world_m"]))
    for port in data["ports"]:
        points.append(_as_array(port["origin_world_m"]))
    for guide in data["guides"]:
        guide_id = str(guide["guide_id"])
        if any(guide_id.startswith(f"{target_id}.") for target_id in target_ids):
            continue
        if guide["guide_type"] in {"component_local_frame", "port_axis", "mirror_normal"}:
            points.append(_as_array(guide["start_m"]))
            points.append(_as_array(guide["end_m"]))
    if not points:
        return _scene_points(data)
    return np.vstack(points)


def _set_equal_limits(ax: Any, points: np.ndarray) -> None:
    minimum = np.min(points, axis=0)
    maximum = np.max(points, axis=0)
    center = 0.5 * (minimum + maximum)
    radius = 0.5 * float(np.max(maximum - minimum))
    radius = max(radius, 0.05)
    margin = 0.08 * radius
    radius += margin
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)


def _draw_wire_box(ax: Any, component: dict[str, Any], *, color: str) -> None:
    bounds = component.get("bounds_m")
    if bounds is None or component.get("display_role") == "target":
        return
    lower = _as_array(bounds[0])
    upper = _as_array(bounds[1])
    origin = _as_array(component["origin_world_m"])
    rotation = _as_array(component["rotation_world_from_component"])
    local_corners = np.array(
        [
            [lower[0], lower[1], lower[2]],
            [upper[0], lower[1], lower[2]],
            [upper[0], upper[1], lower[2]],
            [lower[0], upper[1], lower[2]],
            [lower[0], lower[1], upper[2]],
            [upper[0], lower[1], upper[2]],
            [upper[0], upper[1], upper[2]],
            [lower[0], upper[1], upper[2]],
        ],
        dtype=np.float64,
    )
    corners = np.array([origin + rotation @ corner for corner in local_corners])
    edges = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )
    for start, end in edges:
        segment = corners[[start, end]]
        ax.plot(segment[:, 0], segment[:, 1], segment[:, 2], color=color, linewidth=0.8, alpha=0.7)


def _component_color(component: dict[str, Any]) -> str:
    role = str(component.get("display_role", "optical_component"))
    component_type = str(component.get("component_type", "unknown"))
    if role == "target":
        return "#8a6d00"
    if role == "receiver":
        return "#7b2cbf"
    if component_type == "scanner_mirror":
        return "#2b8a3e"
    if component_type == "collimator":
        return "#1c7ed6"
    if "source" in component_type:
        return "#f08c00"
    return "#495057"


def _draw_components(ax: Any, data: dict[str, Any]) -> None:
    for component in data["components"]:
        origin = _as_array(component["origin_world_m"])
        color = _component_color(component)
        marker = "^" if component["display_role"] == "receiver" else "o"
        if component["display_role"] == "target":
            marker = "s"
        ax.scatter(
            origin[0],
            origin[1],
            origin[2],
            s=34,
            color=color,
            marker=marker,
            depthshade=True,
            label=str(component["element_id"]),
        )
        _draw_wire_box(ax, component, color=color)


def _draw_meshes(ax: Any, data: dict[str, Any]) -> None:
    for mesh in data.get("meshes", ()):
        triangles = _as_array(mesh["triangles_world_m"])
        collection = Poly3DCollection(
            triangles,
            facecolors="#d97706",
            edgecolors="#92400e",
            alpha=0.25,
            linewidths=0.35,
        )
        collection.set_label(
            f"{mesh['target_id']} STL mesh ({mesh['display_triangle_count']}/"
            f"{mesh['source_triangle_count']}; geometry-only)"
        )
        ax.add_collection3d(collection)


def _draw_mesh_hits(ax: Any, data: dict[str, Any]) -> None:
    for hit in data.get("mesh_hits", ()):
        point = _as_array(hit["point_m"])
        normal_end = _as_array(hit["normal_end_m"])
        color = "#06b6d4" if hit["contributes_to_center_ray_visibility"] else "#94a3b8"
        ax.plot(
            [point[0], normal_end[0]],
            [point[1], normal_end[1]],
            [point[2], normal_end[2]],
            color=color,
            linewidth=1.8,
            label="STL closest hit normal (geometry-only)",
        )
        ax.scatter(
            point[0],
            point[1],
            point[2],
            color=color,
            marker="x",
            s=52,
        )


def _draw_guides(ax: Any, data: dict[str, Any]) -> None:
    style_by_type = {
        "component_local_frame": {"linewidth": 0.8, "alpha": 0.45, "linestyle": "-"},
        "port_axis": {"linewidth": 0.8, "alpha": 0.55, "linestyle": "--"},
        "mirror_normal": {"linewidth": 1.7, "alpha": 0.95, "linestyle": "-"},
        "reflected_direction": {"linewidth": 1.1, "alpha": 0.4, "linestyle": ":"},
        "target_plane_edge": {"linewidth": 1.2, "alpha": 0.8, "linestyle": "-"},
        "receiver_fov": {"linewidth": 0.9, "alpha": 0.42, "linestyle": "--"},
        "return_hit_residual": {"linewidth": 1.3, "alpha": 0.95, "linestyle": ":"},
    }
    for guide in data["guides"]:
        if not guide["enabled"]:
            continue
        start = _as_array(guide["start_m"])
        end = _as_array(guide["end_m"])
        style = style_by_type.get(guide["guide_type"], {"linewidth": 0.8, "alpha": 0.4, "linestyle": "-"})
        ax.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            [start[2], end[2]],
            color=guide["color"],
            linewidth=style["linewidth"],
            alpha=style["alpha"],
            linestyle=style["linestyle"],
        )
        if guide["guide_type"] == "return_hit_residual":
            ax.scatter(start[0], start[1], start[2], color="#0ea5e9", marker="x", s=38)


def _draw_rays(ax: Any, data: dict[str, Any]) -> None:
    shown_roles: set[str] = set()
    return_power_labels: list[str] = []
    for ray in data["rays"]:
        start = _as_array(ray["start_m"])
        end = _as_array(ray["end_m"])
        role = str(ray.get("propagation_role", "transmit"))
        is_return = role == "return"
        is_stl_hit = ray["status"] == "stl_target_hit_geometry_only"
        is_target_hit = ray["status"] == "target_hit" or is_stl_hit
        has_return_power = is_return and ray.get("power_w") is not None
        color = "#0ea5e9" if is_return else "#e03131" if is_target_hit else "#ff6b00"
        linewidth = 2.0 if is_return else 2.2 if is_target_hit else 1.8
        legend_role = (
            "return_power"
            if has_return_power
            else "stl_hit"
            if is_stl_hit
            else role
        )
        ax.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            [start[2], end[2]],
            color=color,
            linewidth=linewidth,
            alpha=0.95,
            linestyle="--" if is_return else "-",
            label=(
                "Reciprocal return (analytical power)"
                if has_return_power and legend_role not in shown_roles
                else "Reciprocal return (geometry-only)"
                if is_return and legend_role not in shown_roles
                else "STL center ray (geometry-only)"
                if is_stl_hit and legend_role not in shown_roles
                else "Transmit beam path"
                if not is_return and role not in shown_roles
                else None
            ),
        )
        if has_return_power:
            plane_name = str(ray.get("plane_power_name") or "return_power")
            return_power_labels.append(f"{plane_name}: {float(ray['power_w']):.3g} W")
        shown_roles.add(legend_role)
    if return_power_labels and hasattr(ax, "text2D"):
        keyword_arguments: dict[str, Any] = {
            "color": "#0369a1",
            "fontsize": 6,
            "verticalalignment": "bottom",
            "bbox": {"facecolor": "white", "edgecolor": "#7dd3fc", "alpha": 0.78},
        }
        if hasattr(ax, "transAxes"):
            keyword_arguments["transform"] = ax.transAxes
        ax.text2D(
            0.02,
            0.02,
            "R2 reciprocal plane power\n" + "\n".join(return_power_labels),
            **keyword_arguments,
        )


def _footprint_polygon(footprint: dict[str, Any], *, samples: int = 96) -> np.ndarray:
    center = _as_array(footprint["hit_center_m"])
    normal = normalize_vector(footprint["normal"], name="footprint normal")
    major_axis = normalize_vector(footprint["major_axis_world"], name="footprint major axis")
    minor_axis = normalize_vector(footprint["minor_axis_world"], name="footprint minor axis")
    if abs(float(np.dot(major_axis, minor_axis))) > 1.0e-9:
        raise ValueError("Footprint major/minor world axis는 서로 직교해야 합니다.")
    if not np.isclose(
        float(np.dot(np.cross(major_axis, minor_axis), normal)),
        1.0,
        rtol=0.0,
        atol=1.0e-9,
    ):
        raise ValueError("Footprint world axes는 target normal과 오른손 좌표계여야 합니다.")
    angles = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    return np.array(
        [
            center
            + float(footprint["major_radius_m"]) * np.cos(angle) * major_axis
            + float(footprint["minor_radius_m"]) * np.sin(angle) * minor_axis
            for angle in angles
        ],
        dtype=np.float64,
    )


def _draw_footprints(ax: Any, data: dict[str, Any]) -> None:
    for footprint in data["footprints"]:
        polygon = _footprint_polygon(footprint)
        color = "#ff922b" if footprint["status"] == "pass" else "#d9480f"
        ax.add_collection3d(
            Poly3DCollection(
                [polygon],
                facecolors=color,
                edgecolors="#d9480f",
                alpha=0.25,
                linewidths=1.1,
            )
        )
        center = _as_array(footprint["hit_center_m"])
        ax.scatter(center[0], center[1], center[2], color="#d9480f", marker="x", s=45)


def render_viewport_scene(
    scene: ViewportScene | dict[str, Any],
    output_path: Path,
    *,
    dpi: int = 150,
) -> Path:
    """ViewportScene을 headless 3D optical bench PNG로 저장한다."""

    data = scene.to_dict() if hasattr(scene, "to_dict") else dict(scene)
    fig = plt.figure(figsize=(13.2, 6.8))
    full_ax = fig.add_subplot(121, projection="3d")
    detail_ax = fig.add_subplot(122, projection="3d")
    full_points = _scene_points(data)
    detail_points = _detail_points(data)
    for ax in (full_ax, detail_ax):
        _draw_meshes(ax, data)
        _draw_components(ax, data)
        _draw_guides(ax, data)
        _draw_rays(ax, data)
        _draw_footprints(ax, data)
        _draw_mesh_hits(ax, data)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.grid(True, alpha=0.22)
        ax.view_init(elev=22.0, azim=-58.0)
        ax.legend(loc="upper left", fontsize=7, framealpha=0.88)

    _set_equal_limits(full_ax, full_points)
    full_ax.set_title("Full optical bench")
    _set_equal_limits(detail_ax, detail_points)
    detail_ax.set_title("Optical head detail")
    fig.suptitle(
        "Optical Assembly Workspace | "
        f"{data['scenario_id']} | rays={len(data['rays'])} | "
        f"footprints={len(data['footprints'])} | meshes={len(data.get('meshes', ()))}"
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))

    resolved = output_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(resolved, dpi=dpi)
    plt.close(fig)
    return resolved


__all__ = ["render_viewport_scene"]
