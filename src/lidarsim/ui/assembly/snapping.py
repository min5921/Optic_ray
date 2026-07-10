"""광학 assembly 정렬 preview와 deterministic snap 계산.

이 module의 결과는 제안값일 뿐이다. UI가 사용자의 승인 없이 placement를
바꾸지 않도록 추천 transform과 residual만 반환한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from lidarsim.geometry import resolve_assembly
from lidarsim.geometry.transform import normalize_vector
from lidarsim.optics.mirror import reflect_vector
from lidarsim.results import Phase2OpticalTrainReport, build_phase2_optical_train_report


Vec3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


def _vec3(value: Any, *, name: str) -> Vec3:
    vector = normalize_vector(value, name=name)
    return (float(vector[0]), float(vector[1]), float(vector[2]))


def _point3(value: Any, *, name: str) -> Vec3:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name}은 유한한 vec3여야 합니다.")
    return (float(array[0]), float(array[1]), float(array[2]))


def _angle_between(first: Any, second: Any) -> float:
    a = normalize_vector(first, name="first direction")
    b = normalize_vector(second, name="second direction")
    return math.acos(float(np.clip(np.dot(a, b), -1.0, 1.0)))


def _rotate_about_axis(vector: Any, axis: Any, angle_rad: float) -> np.ndarray:
    value = normalize_vector(vector, name="rotation input")
    unit_axis = normalize_vector(axis, name="rotation axis")
    angle = float(angle_rad)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return normalize_vector(
        value * cosine
        + np.cross(unit_axis, value) * sine
        + unit_axis * float(np.dot(unit_axis, value)) * (1.0 - cosine),
        name="rotated direction",
    )


def _alignment_rotation(source: Any, destination: Any) -> np.ndarray:
    """Source vector를 destination으로 보내는 최소 active rotation을 만든다."""

    start = normalize_vector(source, name="alignment source")
    end = normalize_vector(destination, name="alignment destination")
    cosine = float(np.clip(np.dot(start, end), -1.0, 1.0))
    if cosine >= 1.0 - 1.0e-14:
        return np.eye(3, dtype=np.float64)
    if cosine <= -1.0 + 1.0e-14:
        candidates = (
            np.array((1.0, 0.0, 0.0), dtype=np.float64),
            np.array((0.0, 1.0, 0.0), dtype=np.float64),
            np.array((0.0, 0.0, 1.0), dtype=np.float64),
        )
        axis = max(candidates, key=lambda item: float(np.linalg.norm(np.cross(start, item))))
        axis = normalize_vector(np.cross(start, axis), name="opposite alignment axis")
        return -np.eye(3, dtype=np.float64) + 2.0 * np.outer(axis, axis)

    cross = np.cross(start, end)
    sine = float(np.linalg.norm(cross))
    axis = cross / sine
    x, y, z = axis
    skew = np.array(
        ((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)),
        dtype=np.float64,
    )
    return np.eye(3, dtype=np.float64) + sine * skew + (1.0 - cosine) * (skew @ skew)


def _quaternion_wxyz(rotation: Any) -> Quaternion:
    """Orthonormal rotation matrix를 stable `[w, x, y, z]` quaternion으로 바꾼다."""

    matrix = np.asarray(rotation, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("rotation은 유한한 3x3 matrix여야 합니다.")
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        values = np.array(
            (
                0.25 * scale,
                (matrix[2, 1] - matrix[1, 2]) / scale,
                (matrix[0, 2] - matrix[2, 0]) / scale,
                (matrix[1, 0] - matrix[0, 1]) / scale,
            ),
            dtype=np.float64,
        )
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            scale = math.sqrt(max(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2], 0.0)) * 2.0
            values = np.array(
                (
                    (matrix[2, 1] - matrix[1, 2]) / scale,
                    0.25 * scale,
                    (matrix[0, 1] + matrix[1, 0]) / scale,
                    (matrix[0, 2] + matrix[2, 0]) / scale,
                ),
                dtype=np.float64,
            )
        elif index == 1:
            scale = math.sqrt(max(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2], 0.0)) * 2.0
            values = np.array(
                (
                    (matrix[0, 2] - matrix[2, 0]) / scale,
                    (matrix[0, 1] + matrix[1, 0]) / scale,
                    0.25 * scale,
                    (matrix[1, 2] + matrix[2, 1]) / scale,
                ),
                dtype=np.float64,
            )
        else:
            scale = math.sqrt(max(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1], 0.0)) * 2.0
            values = np.array(
                (
                    (matrix[1, 0] - matrix[0, 1]) / scale,
                    (matrix[0, 2] + matrix[2, 0]) / scale,
                    (matrix[1, 2] + matrix[2, 1]) / scale,
                    0.25 * scale,
                ),
                dtype=np.float64,
            )
    values /= float(np.linalg.norm(values))
    if values[0] < 0.0:
        values *= -1.0
    return tuple(float(value) for value in values)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class MirrorTargetMatePreview:
    """Mirror가 target center를 향하도록 하는 적용 전 pose 제안."""

    constraint_id: str
    mirror_element_id: str
    target_id: str
    status: str
    can_apply: bool
    mirror_origin_m: Vec3
    target_center_m: Vec3
    incident_direction: Vec3
    desired_reflected_direction: Vec3
    current_surface_normal_world: Vec3
    required_surface_normal_world: Vec3
    current_reflected_direction: Vec3
    predicted_reflected_direction: Vec3
    current_residual_angle_rad: float
    required_rotation_angle_rad: float
    scanner_command_angle_rad: float
    recommended_scanner_rotation_axis_world: Vec3
    recommended_translation_m: Vec3
    recommended_quaternion_wxyz: Quaternion
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "constraint_type": "MirrorTargetMate",
            "mirror_element_id": self.mirror_element_id,
            "target_id": self.target_id,
            "status": self.status,
            "can_apply": self.can_apply,
            "mirror_origin_m": list(self.mirror_origin_m),
            "target_center_m": list(self.target_center_m),
            "incident_direction": list(self.incident_direction),
            "desired_reflected_direction": list(self.desired_reflected_direction),
            "current_surface_normal_world": list(self.current_surface_normal_world),
            "required_surface_normal_world": list(self.required_surface_normal_world),
            "current_reflected_direction": list(self.current_reflected_direction),
            "predicted_reflected_direction": list(self.predicted_reflected_direction),
            "current_residual_angle_rad": self.current_residual_angle_rad,
            "required_rotation_angle_rad": self.required_rotation_angle_rad,
            "scanner_command_angle_rad": self.scanner_command_angle_rad,
            "recommended_scanner_rotation_axis_world": list(
                self.recommended_scanner_rotation_axis_world
            ),
            "recommended_translation_m": list(self.recommended_translation_m),
            "recommended_quaternion_wxyz": list(self.recommended_quaternion_wxyz),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def preview_mirror_target_mate(
    project: Any,
    *,
    mirror_element_id: str | None = None,
    target_id: str | None = None,
    report: Phase2OpticalTrainReport | dict[str, Any] | None = None,
) -> MirrorTargetMatePreview:
    """Current incident ray를 target center로 반사하는 mirror pose를 계산한다."""

    scenario = project.active_scenario
    scanner = scenario["scanner"]
    selected_mirror = str(mirror_element_id or scanner["element_id"])
    targets = list(scenario["scene"]["targets"])
    selected_target = str(target_id or targets[0]["id"])
    target = next((item for item in targets if str(item["id"]) == selected_target), None)
    if target is None:
        raise ValueError(f"scene target을 찾을 수 없습니다: {selected_target!r}")
    if target["geometry"]["type"] != "rectangle_plane":
        raise ValueError("MirrorTargetMate preview는 rectangle_plane target만 지원합니다.")

    assembly = resolve_assembly(scenario, project.catalog, source=str(project.project_path))
    if selected_mirror not in assembly.elements:
        raise ValueError(f"assembly mirror element를 찾을 수 없습니다: {selected_mirror!r}")
    element = assembly[selected_mirror]
    component = project.catalog[element.component_ref].data
    if component["component_type"] != "scanner_mirror":
        raise ValueError(f"{selected_mirror!r}은 scanner_mirror component가 아닙니다.")

    report_value = report or build_phase2_optical_train_report(project)
    report_data = report_value.to_dict() if hasattr(report_value, "to_dict") else dict(report_value)
    mirror_report = next(
        (
            item
            for item in report_data["optical_train"]["component_reports"]
            if str(item.get("element_id")) == selected_mirror
            and item.get("component_type") == "scanner_mirror"
        ),
        None,
    )
    if mirror_report is None:
        raise ValueError(f"{selected_mirror!r} mirror interaction report가 없습니다.")

    mirror_origin = np.asarray(element.T_world_from_component.translation_m, dtype=np.float64)
    target_center = np.asarray(target["geometry"]["center_m"], dtype=np.float64)
    to_target = target_center - mirror_origin
    if float(np.linalg.norm(to_target)) <= 1.0e-12:
        raise ValueError("Target center와 mirror origin이 같아 MirrorTargetMate를 계산할 수 없습니다.")
    desired_reflected = normalize_vector(to_target, name="mirror to target direction")
    incident = normalize_vector(mirror_report["incident_direction"], name="incident direction")
    normal_difference = incident - desired_reflected
    if float(np.linalg.norm(normal_difference)) <= 1.0e-12:
        raise ValueError(
            "Incident ray와 target direction이 같아 유일하고 비-grazing인 mirror normal을 정할 수 없습니다."
        )

    current_effective_normal = normalize_vector(
        mirror_report["surface_normal_world"],
        name="current effective mirror normal",
    )
    required_effective_normal = normalize_vector(
        normal_difference,
        name="required effective mirror normal",
    )
    if float(np.dot(required_effective_normal, current_effective_normal)) < 0.0:
        required_effective_normal = -required_effective_normal

    command_angle = (
        float(scanner.get("static_command_angle_rad", 0.0))
        if str(scanner.get("element_id")) == selected_mirror
        else 0.0
    )
    configured_rotation_axis = normalize_vector(
        scanner["rotation_axis_world"],
        name="scanner rotation axis",
    )
    local_normal = normalize_vector(
        component["mechanical"]["surface_normal_local"],
        name="mirror local normal",
    )
    local_rotation_axis = normalize_vector(
        component["mechanical"]["default_rotation_axis_local"],
        name="mirror local rotation axis",
    )
    current_rotation = np.asarray(element.T_world_from_component.rotation, dtype=np.float64)
    local_commanded_normal = _rotate_about_axis(local_normal, local_rotation_axis, command_angle)
    current_pose_effective_normal = normalize_vector(
        current_rotation @ local_commanded_normal,
        name="current pose effective normal",
    )
    delta_rotation = _alignment_rotation(
        current_pose_effective_normal,
        required_effective_normal,
    )
    recommended_rotation = delta_rotation @ current_rotation
    recommended_quaternion = _quaternion_wxyz(recommended_rotation)
    recommended_rotation_axis = normalize_vector(
        recommended_rotation @ local_rotation_axis,
        name="recommended scanner rotation axis",
    )

    predicted_effective_normal = _rotate_about_axis(
        recommended_rotation @ local_normal,
        recommended_rotation_axis,
        command_angle,
    )
    current_reflected = reflect_vector(incident, current_effective_normal)
    predicted_reflected = reflect_vector(incident, predicted_effective_normal)
    current_residual = _angle_between(current_reflected, desired_reflected)
    predicted_residual = _angle_between(predicted_reflected, desired_reflected)
    if predicted_residual > 1.0e-8:
        raise ValueError(
            f"MirrorTargetMate 내부 reflection 검산이 실패했습니다: residual={predicted_residual:.6g} rad"
        )

    placement = next(
        item["placement"]
        for item in scenario["optical_assembly"]["elements"]
        if str(item["id"]) == selected_mirror
    )
    can_apply = str(placement["mode"]) == "absolute"
    warnings: list[str] = []
    current_local_axis_world = normalize_vector(
        current_rotation @ local_rotation_axis,
        name="current local rotation axis world",
    )
    if _angle_between(current_local_axis_world, configured_rotation_axis) > 1.0e-6:
        warnings.append(
            "현재 component local scanner axis와 scenario scanner.rotation_axis_world가 일치하지 않습니다. 추천 적용 시 두 값을 함께 정렬합니다."
        )
    if not can_apply:
        warnings.append(
            "첫 vertical slice는 absolute placement mirror만 저장할 수 있습니다. Port placement에는 별도 mate serialization이 필요합니다."
        )
    status = "aligned" if current_residual <= 1.0e-6 else "adjustment_required"
    return MirrorTargetMatePreview(
        constraint_id=f"mirror_target:{selected_mirror}:{selected_target}",
        mirror_element_id=selected_mirror,
        target_id=selected_target,
        status=status,
        can_apply=can_apply,
        mirror_origin_m=_point3(mirror_origin, name="mirror origin"),
        target_center_m=_point3(target_center, name="target center"),
        incident_direction=_vec3(incident, name="incident direction"),
        desired_reflected_direction=_vec3(desired_reflected, name="desired reflected direction"),
        current_surface_normal_world=_vec3(
            current_effective_normal,
            name="current surface normal",
        ),
        required_surface_normal_world=_vec3(
            required_effective_normal,
            name="required surface normal",
        ),
        current_reflected_direction=_vec3(current_reflected, name="current reflected direction"),
        predicted_reflected_direction=_vec3(
            predicted_reflected,
            name="predicted reflected direction",
        ),
        current_residual_angle_rad=current_residual,
        required_rotation_angle_rad=_angle_between(
            current_pose_effective_normal,
            required_effective_normal,
        ),
        scanner_command_angle_rad=command_angle,
        recommended_scanner_rotation_axis_world=_vec3(
            recommended_rotation_axis,
            name="recommended scanner rotation axis world",
        ),
        recommended_translation_m=_point3(mirror_origin, name="recommended translation"),
        recommended_quaternion_wxyz=recommended_quaternion,
        assumptions=(
            "Target의 rectangle center를 aim point로 사용합니다.",
            "현재 Phase 2 report의 mirror incident center ray를 사용합니다.",
            "Mirror pose는 현재 rotation에서 필요한 normal까지의 최소 회전으로 정합니다.",
            "Scanner static command angle을 유지한 상태에서 base pose와 world rotation axis를 함께 역산합니다.",
            "Dynamic scanner motion, occlusion과 STL surface hit는 계산하지 않습니다.",
        ),
        warnings=tuple(warnings),
    )


__all__ = ["MirrorTargetMatePreview", "preview_mirror_target_mate"]
