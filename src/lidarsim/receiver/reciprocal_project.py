"""Active project를 Phase 2.4-R1 reciprocal center-ray geometry에 연결한다.

이 module은 resolved assembly, transmitter component report와 nearest-visible
target footprint를 하나의 명시적인 return path로 조립한다. 실제 ray-plane
교차는 :mod:`lidarsim.receiver.reciprocal`의 순수 geometry API가 수행한다.
R1은 power, fiber overlap과 detector response를 의도적으로 계산하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np

from lidarsim.config.immutable import deep_freeze
from lidarsim.geometry import AssemblyPlacement, intersect_ray_plane, resolve_assembly
from lidarsim.geometry.transform import normalize_vector
from lidarsim.optics import OpticalTrainResult
from lidarsim.optics.mirror import reflect_vector
from lidarsim.scene import TargetFootprint

from .reciprocal import (
    ReciprocalCenterRayResult,
    ResolvedPlaneFrame,
    trace_reciprocal_center_ray,
)


RECIPROCAL_ARCHITECTURE = "reciprocal_single_mode_fiber"


@dataclass(frozen=True, slots=True)
class ProjectReciprocalReturn:
    """한 active project의 single nearest-visible reciprocal R1 결과."""

    status: str
    architecture: str
    return_path: Mapping[str, Any] | None
    target_id: str | None
    path: ReciprocalCenterRayResult | None
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.return_path is not None:
            object.__setattr__(
                self,
                "return_path",
                deep_freeze(dict(self.return_path)),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "reciprocal_center_ray_geometry",
            "status": self.status,
            "architecture": self.architecture,
            "return_path": None if self.return_path is None else dict(self.return_path),
            "target_id": self.target_id,
            "path": None if self.path is None else self.path.to_dict(),
            "power_status": "not_evaluated",
            "fiber_coupling_status": "not_evaluated",
            "detector_status": "not_evaluated",
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _element_specs(scenario: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(element["id"]): element
        for element in scenario["optical_assembly"]["elements"]
    }


def _component_report(
    train: OpticalTrainResult,
    element_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (
            report
            for report in train.component_reports
            if str(report.get("element_id", "")) == element_id
        ),
        None,
    )


def _visible_footprint(
    footprints: tuple[TargetFootprint, ...],
) -> TargetFootprint | None:
    return next(
        (
            footprint
            for footprint in footprints
            if footprint.hit and footprint.contributes_to_scene_energy
        ),
        None,
    )


def _port_frame(element: Any, port_id: str) -> ResolvedPlaneFrame:
    transform = element.world_from_port(port_id)
    return ResolvedPlaneFrame(
        origin_m=transform.translation_m,
        normal=transform.rotation[:, 2],
        x_axis=transform.rotation[:, 0],
    )


def reverse_ideal_thin_lens_center_ray(
    incident_direction: Iterable[float],
    interaction_point_m: Iterable[float],
    receive_plane: ResolvedPlaneFrame,
    *,
    focal_length_m: float,
) -> np.ndarray:
    """Reverse-oriented paraxial thin-lens chief-ray direction을 계산한다.

    ``receive_plane.normal``은 catalog port의 forward +axis다. Return traversal의
    optical axis는 그 반대이며 local y도 이 reverse frame에서 다시 구성한다.
    이 규약은 off-axis exact retrace에서 forward lens law의 정확한 역방향을
    만든다.
    """

    focal_length = float(focal_length_m)
    if not np.isfinite(focal_length) or focal_length == 0.0:
        raise ValueError("focal_length_m은 0이 아닌 유한한 값이어야 합니다.")
    incoming = normalize_vector(incident_direction, name="reverse lens incident direction")
    point = np.asarray(interaction_point_m, dtype=np.float64)
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise ValueError("interaction_point_m은 유한한 vec3여야 합니다.")
    reverse_axis = normalize_vector(-receive_plane.normal, name="reverse lens axis")
    reverse_x = receive_plane.x_axis
    reverse_y = normalize_vector(
        np.cross(reverse_axis, reverse_x),
        name="reverse lens y axis",
    )
    axial_cosine = float(np.dot(incoming, reverse_axis))
    if axial_cosine <= 1.0e-12:
        raise ValueError("Reverse thin-lens ray는 receive plane의 reverse +axis 방향으로 입사해야 합니다.")
    offset = point - receive_plane.origin_m
    u_m = float(np.dot(offset, reverse_x))
    v_m = float(np.dot(offset, reverse_y))
    slope_x = float(np.dot(incoming, reverse_x)) / axial_cosine
    slope_y = float(np.dot(incoming, reverse_y)) / axial_cosine
    return normalize_vector(
        reverse_axis
        + (slope_x - u_m / focal_length) * reverse_x
        + (slope_y - v_m / focal_length) * reverse_y,
        name="reverse thin-lens output direction",
    )


def evaluate_project_reciprocal_return(
    project: Any,
    train: OpticalTrainResult,
    footprints: tuple[TargetFootprint, ...],
    *,
    assembly: AssemblyPlacement | None = None,
    position_tolerance_m: float = 1.0e-9,
    angular_tolerance_rad: float = 1.0e-9,
) -> ProjectReciprocalReturn:
    """Resolved active project에서 R1 single center-ray return을 계산한다.

    ``return_path``의 element ID는 config semantic validation을 통과했다고
    가정하되 이 함수도 잘못된 programmatic input을 ``ValueError``로 거부한다.
    Target는 현재 scene visibility policy가 선택한 nearest positive center-ray
    hit 하나만 사용한다.
    """

    scenario = project.active_scenario
    receiver = scenario["receiver"]
    architecture = str(receiver["architecture"])
    assumptions = (
        "Nearest-visible target footprint 중심에서 송신 mirror hit를 향하는 reciprocal center ray 하나만 계산합니다.",
        "동일한 static scanner mirror, collimator reference plane과 source fiber reference plane을 재사용합니다.",
        "Reverse collimator는 exact-retrace paraxial center ray 방향만 적용하며 diffraction과 aberration은 계산하지 않습니다.",
        "R1은 geometry 전용입니다. Return power, fiber mode overlap, duplexer와 detector response는 계산하지 않습니다.",
    )
    if architecture != RECIPROCAL_ARCHITECTURE:
        return ProjectReciprocalReturn(
            status="not_evaluated",
            architecture=architecture,
            return_path=None,
            target_id=None,
            path=None,
            assumptions=assumptions,
            warnings=(
                "receiver.architecture가 reciprocal_single_mode_fiber가 아니므로 R1 reciprocal path를 계산하지 않았습니다.",
            ),
        )

    path_config = receiver.get("return_path")
    if not isinstance(path_config, Mapping):
        raise ValueError("reciprocal receiver에는 receiver.return_path가 필요합니다.")
    return_path = {
        "target_ref": str(path_config["target_ref"]),
        "scanner_element_id": str(path_config["scanner_element_id"]),
        "collimator_element_id": str(path_config["collimator_element_id"]),
        "fiber_element_id": str(path_config["fiber_element_id"]),
        "reuse_transmit_path": bool(path_config["reuse_transmit_path"]),
    }
    if not return_path["reuse_transmit_path"]:
        raise ValueError("R1은 receiver.return_path.reuse_transmit_path=true만 지원합니다.")

    target = _visible_footprint(footprints)
    if target is None or target.intersection.hit_center_m is None:
        return ProjectReciprocalReturn(
            status="not_evaluated",
            architecture=architecture,
            return_path=return_path,
            target_id=str(return_path["target_ref"]),
            path=None,
            assumptions=assumptions,
            warnings=(
                "Nearest-visible target center-ray hit가 없어 reciprocal return geometry를 시작할 수 없습니다.",
            ),
        )
    configured_target_id = str(return_path["target_ref"])
    if target.target_id != configured_target_id:
        return ProjectReciprocalReturn(
            status="not_evaluated",
            architecture=architecture,
            return_path=return_path,
            target_id=configured_target_id,
            path=None,
            assumptions=assumptions,
            warnings=(
                f"Configured return target {configured_target_id!r}가 nearest-visible target가 아닙니다. "
                f"현재 visible target은 {target.target_id!r}이며 암묵적으로 대체하지 않았습니다.",
            ),
        )

    resolved = assembly or resolve_assembly(
        scenario,
        project.catalog,
        source=str(project.project_path),
    )
    specs = _element_specs(scenario)
    scanner_id = str(return_path["scanner_element_id"])
    collimator_id = str(return_path["collimator_element_id"])
    fiber_id = str(return_path["fiber_element_id"])
    missing = [
        element_id
        for element_id in (scanner_id, collimator_id, fiber_id)
        if element_id not in specs or element_id not in resolved.elements
    ]
    if missing:
        raise ValueError(
            "receiver.return_path가 존재하지 않는 assembly element를 참조합니다: "
            + ", ".join(missing)
        )

    mirror_report = _component_report(train, scanner_id)
    collimator_report = _component_report(train, collimator_id)
    if mirror_report is None or collimator_report is None:
        missing_reports = [
            name
            for name, report in (
                (scanner_id, mirror_report),
                (collimator_id, collimator_report),
            )
            if report is None
        ]
        return ProjectReciprocalReturn(
            status="not_evaluated",
            architecture=architecture,
            return_path=return_path,
            target_id=target.target_id,
            path=None,
            assumptions=assumptions,
            warnings=(
                "Forward transmitter train에서 필요한 component report가 없어 R1을 계산하지 않았습니다: "
                + ", ".join(missing_reports),
            ),
        )

    mirror_component = project.catalog[str(specs[scanner_id]["component_ref"])].data
    collimator_component = project.catalog[
        str(specs[collimator_id]["component_ref"])
    ].data
    mirror_optical = mirror_component["optical"]
    collimator_optical = collimator_component["optical"]
    mirror_plane = ResolvedPlaneFrame(
        origin_m=mirror_report["surface_origin_world_m"],
        normal=mirror_report["surface_normal_world"],
        x_axis=mirror_report["aperture_x_axis_world"],
    )
    collimator_plane = _port_frame(resolved[collimator_id], "output")
    fiber_plane = _port_frame(resolved[fiber_id], "output")

    target_to_mirror_direction = normalize_vector(
        np.asarray(mirror_report["interaction_point_world_m"], dtype=np.float64)
        - target.intersection.hit_center_m,
        name="target-to-mirror return direction",
    )
    mirror_return_direction = reflect_vector(
        target_to_mirror_direction,
        mirror_plane.normal,
    )
    predicted_collimator_hit = intersect_ray_plane(
        mirror_report["interaction_point_world_m"],
        mirror_return_direction,
        collimator_plane.origin_m,
        collimator_plane.normal,
    )
    fiber_bound_direction = -collimator_plane.normal
    if predicted_collimator_hit.hit and predicted_collimator_hit.point_m is not None:
        fiber_bound_direction = reverse_ideal_thin_lens_center_ray(
            mirror_return_direction,
            predicted_collimator_hit.point_m,
            collimator_plane,
            focal_length_m=float(collimator_optical["effective_focal_length_m"]),
        )
    result = trace_reciprocal_center_ray(
        target_hit_m=target.intersection.hit_center_m,
        transmit_mirror_hit_m=mirror_report["interaction_point_world_m"],
        transmit_incident_direction=mirror_report["incident_direction"],
        mirror_plane=mirror_plane,
        mirror_clear_width_m=float(mirror_optical["clear_width_m"]),
        mirror_clear_height_m=float(mirror_optical["clear_height_m"]),
        collimator_receive_plane=collimator_plane,
        collimator_receive_axis=-collimator_plane.normal,
        expected_collimator_hit_m=collimator_report["interaction_point_world_m"],
        collimator_clear_aperture_diameter_m=float(
            collimator_optical["clear_aperture_diameter_m"]
        ),
        fiber_reference_plane=fiber_plane,
        fiber_receive_axis=-fiber_plane.normal,
        expected_fiber_hit_m=fiber_plane.origin_m,
        fiber_bound_direction=fiber_bound_direction,
        position_tolerance_m=position_tolerance_m,
        angular_tolerance_rad=angular_tolerance_rad,
    )
    warnings = list(result.warnings)
    warnings.append(
        "power_at_virtual_aperture_w는 별도 regression intermediate이며 이 R1 geometry path의 power가 아닙니다."
    )
    return ProjectReciprocalReturn(
        status=result.status,
        architecture=architecture,
        return_path=return_path,
        target_id=target.target_id,
        path=result,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )


__all__ = [
    "ProjectReciprocalReturn",
    "RECIPROCAL_ARCHITECTURE",
    "evaluate_project_reciprocal_return",
    "reverse_ideal_thin_lens_center_ray",
]
