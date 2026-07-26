"""Gaussian footprint estimation on analytical target primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from lidarsim.beam import BeamState
from lidarsim.scene.targets import TargetIntersection


FOOTPRINT_AXIS_CONVENTION = (
    "unit_orthogonal_right_handed_major_minor_target_normal"
)


@dataclass(frozen=True, slots=True, eq=False)
class TargetFootprint:
    """Rectangle-plane target 위의 first-order Gaussian footprint report."""

    intersection: TargetIntersection
    beam_radius_x_m: float | None
    beam_radius_y_m: float | None
    projected_footprint_major_radius_m: float | None
    projected_footprint_minor_radius_m: float | None
    projected_footprint_major_axis_local_uv: tuple[float, float] | None
    projected_footprint_minor_axis_local_uv: tuple[float, float] | None
    projected_footprint_major_axis_world: tuple[float, float, float] | None
    projected_footprint_minor_axis_world: tuple[float, float, float] | None
    projected_radius_u_m: float | None
    projected_radius_v_m: float | None
    approximate_footprint_area_m2: float | None
    peak_irradiance_w_m2: float | None
    candidate_estimated_power_on_target_w: float
    estimated_power_on_target_w: float
    visibility_status: str
    contributes_to_scene_energy: bool
    occluded_by_target_id: str | None
    clipped_by_target_bounds: bool
    quadrature_order: int
    refined_quadrature_order: int
    base_estimated_power_on_target_w: float
    refined_estimated_power_on_target_w: float
    quadrature_relative_residual: float
    quadrature_tolerance: float
    convergence_status: str
    integration_extent_radii: float
    method: str
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def target_id(self) -> str:
        return self.intersection.target_id

    @property
    def material_ref(self) -> str:
        return self.intersection.material_ref

    @property
    def hit(self) -> bool:
        return self.intersection.hit

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "material_ref": self.material_ref,
            "hit": self.hit,
            "miss_reason": self.intersection.miss_reason,
            "hit_center_m": (
                None
                if self.intersection.hit_center_m is None
                else self.intersection.hit_center_m.tolist()
            ),
            "distance_to_target_m": self.intersection.distance_to_target_m,
            "incidence_angle_rad": self.intersection.incidence_angle_rad,
            "incidence_angle_convention": (
                "angle_from_radiometric_surface_normal_radians"
            ),
            "local_coordinates_m": (
                None
                if self.intersection.local_coordinates_m is None
                else list(self.intersection.local_coordinates_m)
            ),
            "beam_radius_x_m": self.beam_radius_x_m,
            "beam_radius_y_m": self.beam_radius_y_m,
            "projected_footprint_major_radius_m": self.projected_footprint_major_radius_m,
            "projected_footprint_minor_radius_m": self.projected_footprint_minor_radius_m,
            "projected_footprint_major_axis_local_uv": (
                None
                if self.projected_footprint_major_axis_local_uv is None
                else list(self.projected_footprint_major_axis_local_uv)
            ),
            "projected_footprint_minor_axis_local_uv": (
                None
                if self.projected_footprint_minor_axis_local_uv is None
                else list(self.projected_footprint_minor_axis_local_uv)
            ),
            "projected_footprint_major_axis_world": (
                None
                if self.projected_footprint_major_axis_world is None
                else list(self.projected_footprint_major_axis_world)
            ),
            "projected_footprint_minor_axis_world": (
                None
                if self.projected_footprint_minor_axis_world is None
                else list(self.projected_footprint_minor_axis_world)
            ),
            "projected_footprint_axis_convention": FOOTPRINT_AXIS_CONVENTION,
            "projected_radius_u_m": self.projected_radius_u_m,
            "projected_radius_v_m": self.projected_radius_v_m,
            "approximate_footprint_area_m2": self.approximate_footprint_area_m2,
            "peak_irradiance_w_m2": self.peak_irradiance_w_m2,
            "candidate_estimated_power_on_target_w": (
                self.candidate_estimated_power_on_target_w
            ),
            "estimated_power_on_target_w": self.estimated_power_on_target_w,
            "visibility_status": self.visibility_status,
            "contributes_to_scene_energy": self.contributes_to_scene_energy,
            "occluded_by_target_id": self.occluded_by_target_id,
            "clipped_by_target_bounds": self.clipped_by_target_bounds,
            "quadrature_order": self.quadrature_order,
            "refined_quadrature_order": self.refined_quadrature_order,
            "base_estimated_power_on_target_w": (
                self.base_estimated_power_on_target_w
            ),
            "refined_estimated_power_on_target_w": (
                self.refined_estimated_power_on_target_w
            ),
            "quadrature_relative_residual": self.quadrature_relative_residual,
            "quadrature_tolerance": self.quadrature_tolerance,
            "convergence_status": self.convergence_status,
            "integration_extent_radii": self.integration_extent_radii,
            "method": self.method,
            "target_intersection": self.intersection.to_dict(),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _projected_ellipse_matrix(
    beam: BeamState,
    intersection: TargetIntersection,
    *,
    distance_m: float,
) -> tuple[np.ndarray, float, float]:
    radius_x, radius_y = beam.radius_at(distance_m)
    wx = float(radius_x)
    wy = float(radius_y)
    projection = np.array(
        [
            [
                float(np.dot(intersection.width_axis, beam.transverse_x_axis)),
                float(np.dot(intersection.height_axis, beam.transverse_x_axis)),
            ],
            [
                float(np.dot(intersection.width_axis, beam.transverse_y_axis)),
                float(np.dot(intersection.height_axis, beam.transverse_y_axis)),
            ],
        ],
        dtype=np.float64,
    )
    metric = projection.T @ np.diag([1.0 / (wx * wx), 1.0 / (wy * wy)]) @ projection
    return metric, wx, wy


def _projected_ellipse_eigensystem(
    metric: np.ndarray,
    intersection: TargetIntersection,
    *,
    eigenvalue_floor: float = 1.0e-30,
    degeneracy_tolerance: float = 1.0e-12,
) -> tuple[
    np.ndarray,
    tuple[float, float],
    tuple[float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    bool,
]:
    """Ellipse metric의 ordered, deterministic, right-handed eigensystem을 반환한다."""

    eigenvalues, eigenvectors = np.linalg.eigh(metric)
    nearly_singular = float(np.min(eigenvalues)) <= eigenvalue_floor
    safe_eigenvalues = np.maximum(eigenvalues, eigenvalue_floor)
    scale = max(float(np.max(np.abs(safe_eigenvalues))), eigenvalue_floor)
    degenerate = (
        abs(float(safe_eigenvalues[1] - safe_eigenvalues[0]))
        <= degeneracy_tolerance * scale
    )

    if degenerate:
        # 원형 footprint의 axis는 물리적으로 유일하지 않으므로 target local frame을
        # deterministic convention으로 사용한다.
        major_local = np.array((1.0, 0.0), dtype=np.float64)
    else:
        # eigh는 eigenvalue 오름차순이다. 가장 작은 eigenvalue의 eigenvector가
        # 가장 긴 ellipse radius 방향이다.
        major_local = np.array(eigenvectors[:, 0], dtype=np.float64, copy=True)
        major_local /= float(np.linalg.norm(major_local))
        dominant_index = int(np.argmax(np.abs(major_local)))
        if float(major_local[dominant_index]) < 0.0:
            major_local *= -1.0

    # Local (u, v, normal)은 right-handed다. 이 90도 회전은
    # cross(major_world, minor_world) == target_normal을 보장한다.
    minor_local = np.array((-major_local[1], major_local[0]), dtype=np.float64)
    major_world = (
        float(major_local[0]) * intersection.width_axis
        + float(major_local[1]) * intersection.height_axis
    )
    minor_world = (
        float(minor_local[0]) * intersection.width_axis
        + float(minor_local[1]) * intersection.height_axis
    )
    major_world /= float(np.linalg.norm(major_world))
    minor_world /= float(np.linalg.norm(minor_world))
    return (
        safe_eigenvalues,
        (float(major_local[0]), float(major_local[1])),
        (float(minor_local[0]), float(minor_local[1])),
        tuple(float(value) for value in major_world),
        tuple(float(value) for value in minor_world),
        nearly_singular,
    )


def _integrate_power_on_target(
    beam: BeamState,
    intersection: TargetIntersection,
    metric_inverse: np.ndarray,
    *,
    distance_m: float,
    incidence_cosine: float,
    quadrature_order: int,
    integration_extent_radii: float,
) -> tuple[float, bool]:
    assert intersection.local_coordinates_m is not None
    hit_u, hit_v = intersection.local_coordinates_m
    radius_u = math.sqrt(max(float(metric_inverse[0, 0]), 0.0))
    radius_v = math.sqrt(max(float(metric_inverse[1, 1]), 0.0))
    half_width = 0.5 * intersection.width_m
    half_height = 0.5 * intersection.height_m
    clipped_by_1e2_bounds = (
        abs(hit_u) + radius_u > half_width or abs(hit_v) + radius_v > half_height
    )

    u_min_target = -half_width - hit_u
    u_max_target = half_width - hit_u
    v_min_target = -half_height - hit_v
    v_max_target = half_height - hit_v
    u_extent = integration_extent_radii * max(radius_u, 1e-15)
    v_extent = integration_extent_radii * max(radius_v, 1e-15)
    u_min = max(u_min_target, -u_extent)
    u_max = min(u_max_target, u_extent)
    v_min = max(v_min_target, -v_extent)
    v_max = min(v_max_target, v_extent)
    if u_min >= u_max or v_min >= v_max:
        return 0.0, True

    nodes, weights = np.polynomial.legendre.leggauss(int(quadrature_order))
    u = 0.5 * (u_max - u_min) * nodes + 0.5 * (u_max + u_min)
    v = 0.5 * (v_max - v_min) * nodes + 0.5 * (v_max + v_min)
    wu = 0.5 * (u_max - u_min) * weights
    wv = 0.5 * (v_max - v_min) * weights
    uu, vv = np.meshgrid(u, v, indexing="xy")
    surface_offsets = (
        uu[..., None] * intersection.width_axis + vv[..., None] * intersection.height_axis
    )
    beam_x = np.tensordot(surface_offsets, beam.transverse_x_axis, axes=([-1], [0]))
    beam_y = np.tensordot(surface_offsets, beam.transverse_y_axis, axes=([-1], [0]))
    irradiance = beam.irradiance(beam_x, beam_y, distance_m=distance_m)
    area_weights = np.outer(wv, wu)
    power = float(np.sum(irradiance * incidence_cosine * area_weights))
    return min(max(power, 0.0), beam.power_w), clipped_by_1e2_bounds


def estimate_rectangle_plane_footprint(
    beam: BeamState,
    intersection: TargetIntersection,
    *,
    quadrature_order: int = 96,
    integration_extent_radii: float = 6.0,
    quadrature_tolerance: float = 1e-8,
    refinement_factor: int = 2,
) -> TargetFootprint:
    """Rectangle-plane hit에서 projected Gaussian footprint와 intercepted power를 추정한다."""

    order = int(quadrature_order)
    if order < 16:
        raise ValueError("quadrature_order는 16 이상이어야 합니다.")
    factor = int(refinement_factor)
    if factor < 2:
        raise ValueError("refinement_factor는 2 이상이어야 합니다.")
    refined_order = order * factor
    tolerance = float(quadrature_tolerance)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("quadrature_tolerance는 0보다 큰 유한한 값이어야 합니다.")
    extent = float(integration_extent_radii)
    if not math.isfinite(extent) or extent <= 0.0:
        raise ValueError("integration_extent_radii는 0보다 큰 유한한 값이어야 합니다.")
    assumptions = [
        "Beam 중심 ray와 rectangle_plane의 교차점을 footprint 중심으로 사용합니다.",
        "Gaussian profile은 target plane에 1차 투영하며 diffraction, aberration, speckle은 계산하지 않습니다.",
        (
            "Footprint major/minor axis는 정규화·직교하며 "
            "cross(major_world, minor_world)=target_normal인 오른손 좌표계입니다. "
            "Major radius는 항상 minor radius 이상입니다."
        ),
        "Power-on-target 적분은 beam core 주변 유효 window에서 수행하며 먼 Gaussian tail은 무시합니다.",
    ]
    warnings = list(intersection.warnings)

    if not intersection.hit:
        return TargetFootprint(
            intersection=intersection,
            beam_radius_x_m=None,
            beam_radius_y_m=None,
            projected_footprint_major_radius_m=None,
            projected_footprint_minor_radius_m=None,
            projected_footprint_major_axis_local_uv=None,
            projected_footprint_minor_axis_local_uv=None,
            projected_footprint_major_axis_world=None,
            projected_footprint_minor_axis_world=None,
            projected_radius_u_m=None,
            projected_radius_v_m=None,
            approximate_footprint_area_m2=None,
            peak_irradiance_w_m2=None,
            candidate_estimated_power_on_target_w=0.0,
            estimated_power_on_target_w=0.0,
            visibility_status="miss",
            contributes_to_scene_energy=False,
            occluded_by_target_id=None,
            clipped_by_target_bounds=False,
            quadrature_order=order,
            refined_quadrature_order=refined_order,
            base_estimated_power_on_target_w=0.0,
            refined_estimated_power_on_target_w=0.0,
            quadrature_relative_residual=0.0,
            quadrature_tolerance=tolerance,
            convergence_status="not_evaluated",
            integration_extent_radii=extent,
            method="miss_no_footprint",
            assumptions=tuple(assumptions),
            warnings=tuple(warnings),
        )

    assert intersection.distance_to_target_m is not None
    assert intersection.incidence_cosine is not None
    metric, radius_x, radius_y = _projected_ellipse_matrix(
        beam,
        intersection,
        distance_m=intersection.distance_to_target_m,
    )
    (
        eigenvalues,
        major_axis_local,
        minor_axis_local,
        major_axis_world,
        minor_axis_world,
        nearly_singular,
    ) = _projected_ellipse_eigensystem(metric, intersection)
    if nearly_singular:
        warnings.append(
            "Grazing 또는 nearly singular projection입니다. Footprint 값을 reference warning으로 취급하세요."
        )
    radii = 1.0 / np.sqrt(eigenvalues)
    major = float(radii[0])
    minor = float(radii[1])
    metric_inverse = np.linalg.pinv(metric)
    radius_u = math.sqrt(max(float(metric_inverse[0, 0]), 0.0))
    radius_v = math.sqrt(max(float(metric_inverse[1, 1]), 0.0))
    area = math.pi * major * minor
    peak = float(beam.irradiance(0.0, 0.0, distance_m=intersection.distance_to_target_m))
    peak_surface = peak * float(intersection.incidence_cosine)
    base_power_on_target, clipped = _integrate_power_on_target(
        beam,
        intersection,
        metric_inverse,
        distance_m=intersection.distance_to_target_m,
        incidence_cosine=float(intersection.incidence_cosine),
        quadrature_order=order,
        integration_extent_radii=extent,
    )
    refined_power_on_target, refined_clipped = _integrate_power_on_target(
        beam,
        intersection,
        metric_inverse,
        distance_m=intersection.distance_to_target_m,
        incidence_cosine=float(intersection.incidence_cosine),
        quadrature_order=refined_order,
        integration_extent_radii=extent,
    )
    clipped = clipped or refined_clipped
    residual = abs(refined_power_on_target - base_power_on_target) / max(
        abs(refined_power_on_target),
        max(abs(beam.power_w), 1.0) * 1e-15,
    )
    convergence_status = "pass" if residual <= tolerance else "warning"
    if clipped:
        warnings.append("Projected 1/e² footprint가 rectangle target bounds에 걸립니다.")
    if convergence_status != "pass":
        warnings.append(
            "Target footprint base/refined quadrature relative residual "
            f"{residual:.3e}이 tolerance {tolerance:.3e}을 초과했습니다."
        )

    return TargetFootprint(
        intersection=intersection,
        beam_radius_x_m=radius_x,
        beam_radius_y_m=radius_y,
        projected_footprint_major_radius_m=major,
        projected_footprint_minor_radius_m=minor,
        projected_footprint_major_axis_local_uv=major_axis_local,
        projected_footprint_minor_axis_local_uv=minor_axis_local,
        projected_footprint_major_axis_world=major_axis_world,
        projected_footprint_minor_axis_world=minor_axis_world,
        projected_radius_u_m=radius_u,
        projected_radius_v_m=radius_v,
        approximate_footprint_area_m2=area,
        peak_irradiance_w_m2=peak_surface,
        candidate_estimated_power_on_target_w=refined_power_on_target,
        estimated_power_on_target_w=refined_power_on_target,
        visibility_status="candidate_unresolved",
        contributes_to_scene_energy=False,
        occluded_by_target_id=None,
        clipped_by_target_bounds=clipped,
        quadrature_order=order,
        refined_quadrature_order=refined_order,
        base_estimated_power_on_target_w=base_power_on_target,
        refined_estimated_power_on_target_w=refined_power_on_target,
        quadrature_relative_residual=residual,
        quadrature_tolerance=tolerance,
        convergence_status=convergence_status,
        integration_extent_radii=extent,
        method="projected_gaussian_rectangle_plane_first_order",
        assumptions=tuple(assumptions),
        warnings=tuple(warnings),
    )
