"""Ideal flat mirror reflection과 rectangular aperture clipping."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np

from lidarsim.beam import BeamState
from lidarsim.geometry.transform import normalize_vector


@dataclass(frozen=True, slots=True)
class MirrorClipResult:
    """Flat mirror rectangular clear aperture의 Gaussian power throughput."""

    clear_width_m: float
    clear_height_m: float
    beam_center_u_m: float
    beam_center_v_m: float
    incidence_cosine: float
    incidence_angle_rad: float
    transmission_fraction: float
    clipped_fraction: float
    input_power_w: float
    output_power_w: float
    loss_w: float
    loss_db: float | None
    status: str
    quadrature_order: int
    method: str

    def to_dict(self) -> dict[str, float | int | str | None]:
        return {
            "clear_width_m": self.clear_width_m,
            "clear_height_m": self.clear_height_m,
            "beam_center_u_m": self.beam_center_u_m,
            "beam_center_v_m": self.beam_center_v_m,
            "incidence_cosine": self.incidence_cosine,
            "incidence_angle_rad": self.incidence_angle_rad,
            "incidence_angle_convention": "angle_from_surface_normal_radians",
            "transmission_fraction": self.transmission_fraction,
            "clipped_fraction": self.clipped_fraction,
            "input_power_w": self.input_power_w,
            "output_power_w": self.output_power_w,
            "loss_w": self.loss_w,
            "loss_db": self.loss_db,
            "status": self.status,
            "quadrature_order": self.quadrature_order,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class MirrorInteractionResult:
    """Flat mirror interaction 결과."""

    output_beam: BeamState
    aperture_clip: MirrorClipResult
    reflected_direction: np.ndarray
    surface_normal: np.ndarray
    aperture_x_axis: np.ndarray
    aperture_y_axis: np.ndarray


def _positive(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 유한한 값이어야 합니다.")
    return result


def reflect_vector(vector: Iterable[float], surface_normal: Iterable[float]) -> np.ndarray:
    """Vector reflection `v - 2(v·n)n`을 반환한다."""

    incoming = normalize_vector(vector, name="incident vector")
    normal = normalize_vector(surface_normal, name="surface normal")
    return normalize_vector(incoming - 2.0 * float(np.dot(incoming, normal)) * normal)


def rectangular_mirror_clip(
    beam: BeamState,
    *,
    surface_normal: Iterable[float],
    aperture_x_axis: Iterable[float],
    aperture_y_axis: Iterable[float],
    clear_width_m: float,
    clear_height_m: float,
    beam_center_u_m: float = 0.0,
    beam_center_v_m: float = 0.0,
    quadrature_order: int = 80,
    integration_extent_radii: float = 6.0,
) -> MirrorClipResult:
    """Mirror plane의 centered rectangular aperture가 통과시키는 power를 적분한다."""

    normal = normalize_vector(surface_normal, name="surface normal")
    x_axis = normalize_vector(aperture_x_axis, name="mirror aperture x axis")
    y_axis = normalize_vector(aperture_y_axis, name="mirror aperture y axis")
    width = _positive(clear_width_m, name="clear_width_m")
    height = _positive(clear_height_m, name="clear_height_m")
    center_u = float(beam_center_u_m)
    center_v = float(beam_center_v_m)
    if not math.isfinite(center_u) or not math.isfinite(center_v):
        raise ValueError("Mirror beam center aperture 좌표는 유한해야 합니다.")
    order = int(quadrature_order)
    if order < 16:
        raise ValueError("quadrature_order는 16 이상이어야 합니다.")
    extent = float(integration_extent_radii)
    if not math.isfinite(extent) or extent <= 0.0:
        raise ValueError("integration_extent_radii는 0보다 큰 유한한 값이어야 합니다.")

    incidence_cosine = abs(float(np.dot(beam.direction, normal)))
    if incidence_cosine <= 1e-12:
        raise ValueError("Grazing incidence mirror clipping은 현재 reference path에서 지원하지 않습니다.")

    # Surface area dA on the mirror contributes projected area |d·n| dA
    # in the beam-normal plane. Integrate only the useful Gaussian core window
    # when the clear aperture is much larger than the beam; otherwise a fixed
    # global quadrature grid can miss a millimeter or micrometer scale core.
    radius_x = beam.radius_x_m
    radius_y = beam.radius_y_m
    projection = np.array(
        [
            [float(np.dot(x_axis, beam.transverse_x_axis)), float(np.dot(y_axis, beam.transverse_x_axis))],
            [float(np.dot(x_axis, beam.transverse_y_axis)), float(np.dot(y_axis, beam.transverse_y_axis))],
        ],
        dtype=np.float64,
    )
    metric = projection.T @ np.diag([1.0 / (radius_x * radius_x), 1.0 / (radius_y * radius_y)]) @ projection
    metric_inverse = np.linalg.pinv(metric)
    radius_u = math.sqrt(max(float(metric_inverse[0, 0]), 0.0))
    radius_v = math.sqrt(max(float(metric_inverse[1, 1]), 0.0))
    u_min = max(-0.5 * width, center_u - extent * max(radius_u, 1e-15))
    u_max = min(0.5 * width, center_u + extent * max(radius_u, 1e-15))
    v_min = max(-0.5 * height, center_v - extent * max(radius_v, 1e-15))
    v_max = min(0.5 * height, center_v + extent * max(radius_v, 1e-15))
    if u_min >= u_max or v_min >= v_max:
        fraction = 0.0
        output_power = 0.0
        loss = beam.power_w
        return MirrorClipResult(
            clear_width_m=width,
            clear_height_m=height,
            beam_center_u_m=center_u,
            beam_center_v_m=center_v,
            incidence_cosine=incidence_cosine,
            incidence_angle_rad=math.acos(min(max(incidence_cosine, 0.0), 1.0)),
            transmission_fraction=fraction,
            clipped_fraction=1.0,
            input_power_w=beam.power_w,
            output_power_w=output_power,
            loss_w=loss,
            loss_db=None,
            status="fail",
            quadrature_order=order,
            method="surface_projected_rectangular_gauss_legendre_windowed",
        )
    nodes, weights = np.polynomial.legendre.leggauss(order)
    u = 0.5 * (u_max - u_min) * nodes + 0.5 * (u_max + u_min)
    v = 0.5 * (v_max - v_min) * nodes + 0.5 * (v_max + v_min)
    wu = 0.5 * (u_max - u_min) * weights
    wv = 0.5 * (v_max - v_min) * weights
    uu, vv = np.meshgrid(u, v, indexing="xy")
    surface_points = (
        (uu - center_u)[..., None] * x_axis
        + (vv - center_v)[..., None] * y_axis
    )
    beam_x = np.tensordot(surface_points, beam.transverse_x_axis, axes=([-1], [0]))
    beam_y = np.tensordot(surface_points, beam.transverse_y_axis, axes=([-1], [0]))
    integration_beam = beam if beam.power_w > 0.0 else replace(beam, power_w=1.0)
    irradiance = integration_beam.irradiance(beam_x, beam_y)
    area_weights = np.outer(wv, wu)
    integrated_power = float(np.sum(irradiance * incidence_cosine * area_weights))
    fraction = min(max(integrated_power / integration_beam.power_w, 0.0), 1.0)
    output_power = beam.power_w * fraction
    loss = beam.power_w - output_power
    loss_db = None if fraction <= 0.0 else -10.0 * math.log10(fraction)
    status = "pass" if 1.0 - fraction <= 1e-9 else "warning" if fraction > 0.0 else "fail"

    return MirrorClipResult(
        clear_width_m=width,
        clear_height_m=height,
        beam_center_u_m=center_u,
        beam_center_v_m=center_v,
        incidence_cosine=incidence_cosine,
        incidence_angle_rad=math.acos(min(max(incidence_cosine, 0.0), 1.0)),
        transmission_fraction=fraction,
        clipped_fraction=1.0 - fraction,
        input_power_w=beam.power_w,
        output_power_w=output_power,
        loss_w=loss,
        loss_db=loss_db,
        status=status,
        quadrature_order=order,
        method="surface_projected_rectangular_gauss_legendre_windowed",
    )


def interact_flat_mirror(
    beam: BeamState,
    *,
    surface_origin_m: Iterable[float],
    surface_normal: Iterable[float],
    aperture_x_axis: Iterable[float],
    aperture_y_axis: Iterable[float],
    clear_width_m: float,
    clear_height_m: float,
    power_reflectivity: float,
    beam_center_u_m: float = 0.0,
    beam_center_v_m: float = 0.0,
    quadrature_order: int = 80,
) -> MirrorInteractionResult:
    """현재 plane의 beam을 ideal flat mirror에서 반사시킨다."""

    reflectivity = float(power_reflectivity)
    if not math.isfinite(reflectivity) or not 0.0 <= reflectivity <= 1.0:
        raise ValueError("power_reflectivity는 0 이상 1 이하이어야 합니다.")
    normal = normalize_vector(surface_normal, name="surface normal")
    reflected_direction = reflect_vector(beam.direction, normal)
    reflected_x_axis = reflect_vector(beam.transverse_x_axis, normal)
    clip = rectangular_mirror_clip(
        beam,
        surface_normal=normal,
        aperture_x_axis=aperture_x_axis,
        aperture_y_axis=aperture_y_axis,
        clear_width_m=clear_width_m,
        clear_height_m=clear_height_m,
        beam_center_u_m=beam_center_u_m,
        beam_center_v_m=beam_center_v_m,
        quadrature_order=quadrature_order,
    )
    total_transmission = clip.transmission_fraction * reflectivity
    origin = np.asarray(surface_origin_m, dtype=np.float64)
    if origin.shape != (3,) or not np.all(np.isfinite(origin)):
        raise ValueError("surface_origin_m은 유한한 vec3여야 합니다.")
    output = replace(
        beam,
        origin_m=origin,
        direction=reflected_direction,
        transverse_x_axis=reflected_x_axis,
        power_w=beam.power_w * total_transmission,
        accumulated_transmission=beam.accumulated_transmission * total_transmission,
    )
    return MirrorInteractionResult(
        output_beam=output,
        aperture_clip=clip,
        reflected_direction=reflected_direction,
        surface_normal=normal,
        aperture_x_axis=normalize_vector(aperture_x_axis, name="mirror aperture x axis"),
        aperture_y_axis=normalize_vector(aperture_y_axis, name="mirror aperture y axis"),
    )
