"""Analytical target primitive intersection for Phase 2.2."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
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


def rectangle_plane_axes(
    normal: Iterable[float],
    width_axis: Iterable[float] | None = None,
    *,
    orthogonality_tolerance: float = 1e-9,
) -> tuple[np.ndarray, np.ndarray]:
    """Normal과 optional width axis에서 right-handed rectangle frame을 만든다."""

    unit_normal = normalize_vector(normal, name="target normal")
    if width_axis is not None:
        unit_width = normalize_vector(width_axis, name="target width axis")
        dot = float(np.dot(unit_normal, unit_width))
        if abs(dot) > float(orthogonality_tolerance):
            raise ValueError(
                "target width_axis는 normal에 수직이어야 합니다: "
                f"|dot|={abs(dot):.9g}, tolerance={orthogonality_tolerance:.9g}"
            )
        height_axis = normalize_vector(
            np.cross(unit_normal, unit_width),
            name="target height axis",
        )
        return unit_width, height_axis
    for candidate in (
        np.array([0.0, 1.0, 0.0], dtype=np.float64),
        np.array([0.0, 0.0, 1.0], dtype=np.float64),
        np.array([1.0, 0.0, 0.0], dtype=np.float64),
    ):
        projected = candidate - float(np.dot(candidate, unit_normal)) * unit_normal
        if float(np.linalg.norm(projected)) > 1e-12:
            width_axis = normalize_vector(projected, name="target width axis")
            height_axis = normalize_vector(
                np.cross(unit_normal, width_axis),
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
    target_normal_input: np.ndarray
    target_normal: np.ndarray
    target_width_axis_input: np.ndarray | None
    width_axis_source: str
    width_axis: np.ndarray
    height_axis: np.ndarray
    surface_sidedness: str
    front_face: bool | None
    radiometric_normal: np.ndarray
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
            "incidence_angle_convention": (
                "angle_from_radiometric_surface_normal_radians"
            ),
            "incidence_cosine": self.incidence_cosine,
            "local_coordinates_m": (
                None if self.local_coordinates_m is None else list(self.local_coordinates_m)
            ),
            "target_center_m": self.target_center_m.tolist(),
            "target_normal_input": self.target_normal_input.tolist(),
            "target_normal": self.target_normal.tolist(),
            "target_width_axis_input": (
                None
                if self.target_width_axis_input is None
                else self.target_width_axis_input.tolist()
            ),
            "width_axis_source": self.width_axis_source,
            "width_axis_world": self.width_axis.tolist(),
            "height_axis_world": self.height_axis.tolist(),
            "surface_sidedness": self.surface_sidedness,
            "front_face": self.front_face,
            "radiometric_normal_world": self.radiometric_normal.tolist(),
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
    normal_input: np.ndarray | None = None,
    normal: np.ndarray,
    width_axis_input: np.ndarray | None = None,
    width_axis_source: str = "deterministic_default",
    width_axis: np.ndarray,
    height_axis: np.ndarray,
    surface_sidedness: str = "two_sided",
    front_face: bool | None = None,
    radiometric_normal: np.ndarray | None = None,
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
        target_normal_input=normal if normal_input is None else normal_input,
        target_normal=normal,
        target_width_axis_input=width_axis_input,
        width_axis_source=width_axis_source,
        width_axis=width_axis,
        height_axis=height_axis,
        surface_sidedness=surface_sidedness,
        front_face=front_face,
        radiometric_normal=normal if radiometric_normal is None else radiometric_normal,
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
    width_axis: Iterable[float] | None = None,
    width_m: float,
    height_m: float,
    surface_sidedness: str = "two_sided",
    epsilon: float = 1e-12,
) -> TargetIntersection:
    """Beam center ray와 rectangle plane의 첫 교차를 계산한다."""

    center = _vec3(center_m, name="target center_m")
    normal_input = _vec3(normal, name="target normal input")
    unit_normal = normalize_vector(normal_input, name="target normal")
    width_axis_input = (
        None
        if width_axis is None
        else _vec3(width_axis, name="target width_axis input")
    )
    sidedness = str(surface_sidedness)
    if sidedness not in {"one_sided", "two_sided"}:
        raise ValueError(
            "surface_sidedness는 'one_sided' 또는 'two_sided'여야 합니다."
        )
    width = _positive(width_m, name="target width_m")
    height = _positive(height_m, name="target height_m")
    resolved_width_axis, height_axis = rectangle_plane_axes(
        unit_normal,
        width_axis_input,
    )
    width_axis_source = "scenario" if width_axis_input is not None else "deterministic_default"
    assumptions = (
        "rectangle_plane target은 완전 평면 primitive로 취급합니다.",
        (
            "Target local frame은 width_axis × height_axis = geometric normal인 "
            "right-handed frame입니다."
        ),
        f"Surface sidedness는 material optical.surface_sidedness={sidedness!r}를 따릅니다.",
        "STL visibility, occlusion, roughness와 curved-surface intersection은 계산하지 않습니다.",
    )
    base_warnings: tuple[str, ...] = (
        (
            "geometry.width_axis가 없어 target roll을 deterministic default axis로 "
            "해석했습니다. 재현 가능한 roll을 위해 width_axis를 명시하세요."
        ),
    ) if width_axis_input is None else ()

    denominator = float(np.dot(beam.direction, unit_normal))
    if abs(denominator) <= float(epsilon):
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="parallel_to_plane",
            center=center,
            normal_input=normal_input,
            normal=unit_normal,
            width_axis_input=width_axis_input,
            width_axis_source=width_axis_source,
            width_axis=resolved_width_axis,
            height_axis=height_axis,
            surface_sidedness=sidedness,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
            warnings=base_warnings,
        )

    distance = float(np.dot(center - beam.origin_m, unit_normal) / denominator)
    if distance <= float(epsilon):
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="intersection_behind_beam",
            center=center,
            normal_input=normal_input,
            normal=unit_normal,
            width_axis_input=width_axis_input,
            width_axis_source=width_axis_source,
            width_axis=resolved_width_axis,
            height_axis=height_axis,
            surface_sidedness=sidedness,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
            warnings=base_warnings,
        )

    front_face = denominator < 0.0
    radiometric_normal = (
        unit_normal
        if front_face
        else normalize_vector(-unit_normal, name="target backside radiometric normal")
    )
    if not front_face and sidedness == "one_sided":
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="backface_culled",
            center=center,
            normal_input=normal_input,
            normal=unit_normal,
            width_axis_input=width_axis_input,
            width_axis_source=width_axis_source,
            width_axis=resolved_width_axis,
            height_axis=height_axis,
            surface_sidedness=sidedness,
            front_face=False,
            radiometric_normal=unit_normal,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
            warnings=base_warnings,
        )

    hit = beam.origin_m + distance * beam.direction
    offset = hit - center
    local_u = float(np.dot(offset, resolved_width_axis))
    local_v = float(np.dot(offset, height_axis))
    if abs(local_u) > 0.5 * width + float(epsilon) or abs(local_v) > 0.5 * height + float(epsilon):
        return _miss(
            target_id=target_id,
            material_ref=material_ref,
            geometry_type="rectangle_plane",
            reason="outside_rectangle_bounds",
            center=center,
            normal_input=normal_input,
            normal=unit_normal,
            width_axis_input=width_axis_input,
            width_axis_source=width_axis_source,
            width_axis=resolved_width_axis,
            height_axis=height_axis,
            surface_sidedness=sidedness,
            front_face=front_face,
            radiometric_normal=radiometric_normal,
            width_m=width,
            height_m=height,
            assumptions=assumptions,
            warnings=base_warnings,
        )

    incidence_cosine = abs(denominator)
    incidence_angle = math.acos(min(max(incidence_cosine, 0.0), 1.0))
    hit.setflags(write=False)
    warnings = list(base_warnings)
    if not front_face:
        warnings.append(
            "Beam이 geometric normal의 뒷면에서 접근했습니다. two_sided 정책에 따라 "
            "radiometric normal을 입사면 쪽으로 뒤집었습니다."
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
        target_normal_input=normal_input,
        target_normal=unit_normal,
        target_width_axis_input=width_axis_input,
        width_axis_source=width_axis_source,
        width_axis=resolved_width_axis,
        height_axis=height_axis,
        surface_sidedness=sidedness,
        front_face=front_face,
        radiometric_normal=radiometric_normal,
        width_m=width,
        height_m=height,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )


def evaluate_target_footprints(
    project: Any,
    beam: BeamState,
    *,
    blocked_reason: str | None = None,
) -> tuple[Any, ...]:
    """Active scenario targets를 읽고 rectangle-plane footprint들을 평가한다."""

    from lidarsim.scene.footprint import estimate_rectangle_plane_footprint

    footprints: list[Any] = []
    for target in project.active_scenario["scene"]["targets"]:
        geometry = target["geometry"]
        target_id = str(target["id"])
        material_ref = str(target["material_ref"])
        geometry_type = str(geometry["type"])
        material = project.catalog[material_ref].data
        surface_sidedness = str(
            material["optical"].get("surface_sidedness", "two_sided")
        )
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
                surface_sidedness=surface_sidedness,
                width_m=1.0,
                height_m=1.0,
                assumptions=("STL/CAD target hit detection은 이번 Phase 2.2 patch 범위 밖입니다.",),
            )
            footprints.append(estimate_rectangle_plane_footprint(beam, intersection))
            continue
        if blocked_reason is not None:
            center = _vec3(geometry["center_m"], name="target center_m")
            normal_input = _vec3(geometry["normal"], name="target normal input")
            normal = normalize_vector(normal_input, name="target normal")
            width_axis_input = (
                None
                if geometry.get("width_axis") is None
                else _vec3(geometry["width_axis"], name="target width_axis input")
            )
            width_axis, height_axis = rectangle_plane_axes(normal, width_axis_input)
            intersection = _miss(
                target_id=target_id,
                material_ref=material_ref,
                geometry_type=geometry_type,
                reason=f"upstream_optical_train_terminated:{blocked_reason}",
                center=center,
                normal_input=normal_input,
                normal=normal,
                width_axis_input=width_axis_input,
                width_axis_source=(
                    "scenario"
                    if width_axis_input is not None
                    else "deterministic_default"
                ),
                width_axis=width_axis,
                height_axis=height_axis,
                surface_sidedness=surface_sidedness,
                width_m=_positive(geometry["width_m"], name="target width_m"),
                height_m=_positive(geometry["height_m"], name="target height_m"),
                assumptions=(
                    "Upstream optical train termination 때문에 target intersection을 "
                    "평가하지 않습니다.",
                ),
            )
            footprints.append(estimate_rectangle_plane_footprint(beam, intersection))
            continue
        intersection = intersect_rectangle_plane(
            beam,
            target_id=target_id,
            material_ref=material_ref,
            center_m=geometry["center_m"],
            normal=geometry["normal"],
            width_axis=geometry.get("width_axis"),
            width_m=geometry["width_m"],
            height_m=geometry["height_m"],
            surface_sidedness=surface_sidedness,
        )
        footprints.append(estimate_rectangle_plane_footprint(beam, intersection))
    visible_candidates = [
        (index, footprint)
        for index, footprint in enumerate(footprints)
        if footprint.hit and footprint.intersection.distance_to_target_m is not None
    ]
    if not visible_candidates:
        return tuple(footprints)

    visible_index, visible = min(
        visible_candidates,
        key=lambda item: (
            float(item[1].intersection.distance_to_target_m),
            str(item[1].target_id),
        ),
    )
    resolved: list[Any] = []
    for index, footprint in enumerate(footprints):
        if not footprint.hit:
            resolved.append(footprint)
            continue
        if index == visible_index:
            resolved.append(
                replace(
                    footprint,
                    visibility_status="visible_nearest",
                    contributes_to_scene_energy=True,
                    occluded_by_target_id=None,
                )
            )
            continue
        resolved.append(
            replace(
                footprint,
                estimated_power_on_target_w=0.0,
                visibility_status="occluded_by_nearer_target",
                contributes_to_scene_energy=False,
                occluded_by_target_id=str(visible.target_id),
                warnings=(
                    *footprint.warnings,
                    f"Center ray의 더 가까운 target {visible.target_id!r}에 가려져 "
                    "scene energy contribution을 0으로 둡니다.",
                ),
            )
        )
    return tuple(resolved)
