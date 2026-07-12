"""Plotly 기반 interactive optical bench renderer."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np

from lidarsim.geometry.transform import normalize_vector
from lidarsim.ui.assembly.snapping import MirrorTargetMatePreview
from lidarsim.ui.assembly.viewport_data import ViewportComponent, ViewportScene


DEFAULT_GUIDE_TYPES = frozenset(
    {
        "port_axis",
        "mirror_normal",
        "target_plane_edge",
        "receiver_fov",
    }
)

_COMPONENT_COLORS = {
    "fiber_source": "#2f6fed",
    "beam_source": "#2f6fed",
    "collimator": "#19a974",
    "scanner_mirror": "#8c5de8",
    "rectangle_plane_target": "#d97706",
    "virtual_monostatic": "#c026d3",
    "virtual_aperture": "#c026d3",
}

_GUIDE_COLORS = {
    "component_local_frame": "#7c8798",
    "port_axis": "#14b8a6",
    "mirror_normal": "#22c55e",
    "reflected_direction": "#f59e0b",
    "target_plane_edge": "#d97706",
    "receiver_fov": "#c026d3",
    "receiver_look": "#c026d3",
}

VIEW_MODES = frozenset({"full_scene", "transmitter_closeup", "selected_component"})


def _point(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _component_vertices(component: ViewportComponent) -> np.ndarray | None:
    if component.bounds_m is None:
        return None
    lower = np.asarray(component.bounds_m[0], dtype=np.float64)
    upper = np.asarray(component.bounds_m[1], dtype=np.float64)
    local = np.array(
        [
            (x, y, z)
            for x in (lower[0], upper[0])
            for y in (lower[1], upper[1])
            for z in (lower[2], upper[2])
        ],
        dtype=np.float64,
    )
    rotation = np.asarray(component.rotation_world_from_component, dtype=np.float64)
    origin = np.asarray(component.origin_world_m, dtype=np.float64)
    return local @ rotation.T + origin


def _wireframe_coordinates(vertices: np.ndarray) -> tuple[list[float | None], ...]:
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
    coordinates: list[list[float | None]] = [[], [], []]
    for start, end in edges:
        for axis in range(3):
            coordinates[axis].extend((float(vertices[start, axis]), float(vertices[end, axis]), None))
    return tuple(coordinates)  # type: ignore[return-value]


def _footprint_coordinates(footprint: Any, *, samples: int = 72) -> np.ndarray:
    normal = normalize_vector(footprint.normal, name="footprint normal")
    major = np.asarray(footprint.orientation_axis_world, dtype=np.float64)
    major = major - float(np.dot(major, normal)) * normal
    major = normalize_vector(major, name="footprint major axis")
    minor = normalize_vector(np.cross(normal, major), name="footprint minor axis")
    center = np.asarray(footprint.hit_center_m, dtype=np.float64)
    angles = np.linspace(0.0, 2.0 * math.pi, samples, endpoint=True)
    return (
        center
        + footprint.major_radius_m * np.cos(angles)[:, None] * major
        + footprint.minor_radius_m * np.sin(angles)[:, None] * minor
    )


def _view_ranges(
    scene: ViewportScene,
    *,
    view_mode: str,
    selected_element_id: str | None,
) -> dict[str, list[float]] | None:
    """근거리 optical head와 선택 부품을 물리적으로 같은 축척으로 확대한다."""

    if view_mode == "full_scene":
        return None
    if view_mode == "transmitter_closeup":
        components = [
            component
            for component in scene.components
            if component.display_role == "optical_component"
        ]
    else:
        components = [
            component
            for component in scene.components
            if component.element_id == selected_element_id
        ]
    if not components:
        return None

    points: list[np.ndarray] = []
    for component in components:
        points.append(np.asarray(component.origin_world_m, dtype=np.float64))
        vertices = _component_vertices(component)
        if vertices is not None:
            points.extend(vertices)
    coordinates = np.asarray(points, dtype=np.float64)
    lower = np.min(coordinates, axis=0)
    upper = np.max(coordinates, axis=0)
    center = 0.5 * (lower + upper)
    largest_span = max(float(np.max(upper - lower)), 0.04)
    half_span = 0.65 * largest_span
    return {
        axis: [float(center[index] - half_span), float(center[index] + half_span)]
        for index, axis in enumerate("xyz")
    }


def build_interactive_viewport_figure(
    scene: ViewportScene,
    *,
    selected_element_id: str | None = None,
    visible_guide_types: Iterable[str] | None = None,
    mirror_mate_preview: MirrorTargetMatePreview | None = None,
    view_mode: str = "full_scene",
) -> Any:
    """ViewportScene을 orbit/zoom 가능한 Plotly Figure로 변환한다."""

    import plotly.graph_objects as go

    if view_mode not in VIEW_MODES:
        raise ValueError(f"지원하지 않는 3D view mode입니다: {view_mode!r}")

    guide_types = set(DEFAULT_GUIDE_TYPES if visible_guide_types is None else visible_guide_types)
    figure = go.Figure()

    origins = np.asarray([component.origin_world_m for component in scene.components], dtype=np.float64)
    show_all_labels = view_mode != "full_scene"
    labels = [
        component.element_id
        if show_all_labels or component.element_id == selected_element_id
        else ""
        for component in scene.components
    ]
    customdata = [[component.element_id] for component in scene.components]
    colors = [
        _COMPONENT_COLORS.get(component.component_type, "#64748b")
        for component in scene.components
    ]
    sizes = [
        19
        if component.element_id == selected_element_id and view_mode != "full_scene"
        else 15
        if component.element_id == selected_element_id
        else 13
        if view_mode != "full_scene" and component.display_role == "optical_component"
        else 9
        for component in scene.components
    ]
    hover = [
        (
            f"<b>{component.element_id}</b><br>"
            f"type: {component.component_type}<br>"
            f"ref: {component.component_ref}<br>"
            f"origin: ({component.origin_world_m[0]:.6g}, "
            f"{component.origin_world_m[1]:.6g}, {component.origin_world_m[2]:.6g}) m"
        )
        for component in scene.components
    ]
    figure.add_trace(
        go.Scatter3d(
            x=origins[:, 0],
            y=origins[:, 1],
            z=origins[:, 2],
            mode="markers+text",
            text=labels,
            textposition="top center",
            customdata=customdata,
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            marker={
                "size": sizes,
                "color": colors,
                "line": {"color": "#f8fafc", "width": 2},
                "opacity": 1.0,
            },
            name="Components",
        )
    )

    for component in scene.components:
        vertices = _component_vertices(component)
        if vertices is None:
            continue
        x_values, y_values, z_values = _wireframe_coordinates(vertices)
        selected = component.element_id == selected_element_id
        figure.add_trace(
            go.Scatter3d(
                x=x_values,
                y=y_values,
                z=z_values,
                mode="lines",
                line={
                    "color": _COMPONENT_COLORS.get(component.component_type, "#64748b"),
                    "width": 7 if selected else 3,
                },
                opacity=1.0 if selected else 0.65,
                hoverinfo="skip",
                name=component.element_id,
                legendgroup="component_geometry",
                showlegend=False,
            )
        )

    guides_by_type: dict[str, list[Any]] = {}
    for guide in scene.guides:
        if guide.enabled and guide.guide_type in guide_types:
            guides_by_type.setdefault(guide.guide_type, []).append(guide)
    for guide_type, guides in guides_by_type.items():
        if guide_type == "receiver_fov" and len(guides) > 4:
            step = max(1, math.ceil(len(guides) / 4))
            guides = guides[::step]
        x_values: list[float | None] = []
        y_values: list[float | None] = []
        z_values: list[float | None] = []
        labels_for_hover: list[str | None] = []
        for guide in guides:
            start = guide.start_m
            end = guide.end_m
            x_values.extend((start[0], end[0], None))
            y_values.extend((start[1], end[1], None))
            z_values.extend((start[2], end[2], None))
            labels_for_hover.extend((guide.label, guide.label, None))
        figure.add_trace(
            go.Scatter3d(
                x=x_values,
                y=y_values,
                z=z_values,
                mode="lines",
                line={"color": _GUIDE_COLORS.get(guide_type, "#94a3b8"), "width": 3},
                hovertext=labels_for_hover,
                hovertemplate="%{hovertext}<extra></extra>",
                name=guide_type.replace("_", " "),
                legendgroup=f"guide:{guide_type}",
                showlegend=False,
            )
        )

    for ray in scene.rays:
        start = ray.start_m
        end = ray.end_m
        color = "#f59e0b" if ray.status == "target_hit" else "#ef4444"
        figure.add_trace(
            go.Scatter3d(
                x=(start[0], end[0]),
                y=(start[1], end[1]),
                z=(start[2], end[2]),
                mode="lines",
                line={"color": color, "width": 7},
                hovertemplate=(
                    f"<b>{ray.label}</b><br>power: {ray.power_w:.6g} W"
                    f"<br>length: {ray.length_m:.6g} m<extra></extra>"
                ),
                name="Beam path",
                legendgroup="beam_path",
                showlegend=ray is scene.rays[0],
            )
        )

    for footprint in scene.footprints:
        points = _footprint_coordinates(footprint)
        figure.add_trace(
            go.Scatter3d(
                x=points[:, 0],
                y=points[:, 1],
                z=points[:, 2],
                mode="lines",
                line={"color": "#ef4444", "width": 7},
                hovertemplate=(
                    f"<b>{footprint.target_id} footprint</b><br>"
                    f"major: {footprint.major_radius_m:.6g} m<br>"
                    f"minor: {footprint.minor_radius_m:.6g} m<br>"
                    f"power: {footprint.power_on_target_w:.6g} W<extra></extra>"
                ),
                name="Target footprint",
            )
        )

    if mirror_mate_preview is not None:
        start = np.asarray(mirror_mate_preview.mirror_origin_m, dtype=np.float64)
        target = np.asarray(mirror_mate_preview.target_center_m, dtype=np.float64)
        distance = float(np.linalg.norm(target - start))
        normal_length = min(max(distance * 0.08, 0.05), 1.0)
        normal_end = start + normal_length * np.asarray(
            mirror_mate_preview.required_surface_normal_world,
            dtype=np.float64,
        )
        figure.add_trace(
            go.Scatter3d(
                x=(start[0], normal_end[0]),
                y=(start[1], normal_end[1]),
                z=(start[2], normal_end[2]),
                mode="lines",
                line={"color": "#2563eb", "width": 6, "dash": "dot"},
                hovertemplate="MirrorTargetMate required normal<extra></extra>",
                name="Recommended normal",
            )
        )
        figure.add_trace(
            go.Scatter3d(
                x=(start[0], target[0]),
                y=(start[1], target[1]),
                z=(start[2], target[2]),
                mode="lines",
                line={"color": "#2563eb", "width": 4, "dash": "dash"},
                hovertemplate=(
                    "MirrorTargetMate target-center ray<br>"
                    f"current residual: {math.degrees(mirror_mate_preview.current_residual_angle_rad):.6g} deg"
                    "<extra></extra>"
                ),
                name="Mate preview",
            )
        )

    ranges = _view_ranges(
        scene,
        view_mode=view_mode,
        selected_element_id=selected_element_id,
    )
    axes = {
        axis: {
            "title": f"{axis.upper()} (m)",
            "showspikes": False,
            **({"range": ranges[axis]} if ranges is not None else {}),
        }
        for axis in "xyz"
    }
    figure.update_layout(
        height=560,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        clickmode="event+select",
        hovermode="closest",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.0, "xanchor": "left", "x": 0.0},
        scene={
            "aspectmode": "data" if ranges is None else "cube",
            "dragmode": "orbit",
            "xaxis": axes["x"],
            "yaxis": axes["y"],
            "zaxis": axes["z"],
            "camera": {"eye": {"x": 1.35, "y": 1.55, "z": 0.8}},
        },
        uirevision=f"{scene.config_hash}:{view_mode}:{selected_element_id}",
    )
    return figure


__all__ = ["DEFAULT_GUIDE_TYPES", "VIEW_MODES", "build_interactive_viewport_figure"]
