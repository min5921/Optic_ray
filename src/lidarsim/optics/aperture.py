"""Gaussian beam의 centered circular aperture clipping 계산."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np

from lidarsim.beam import BeamState
from lidarsim.geometry.transform import normalize_vector


@dataclass(frozen=True, slots=True)
class ApertureClipResult:
    """Circular aperture가 Gaussian power를 통과시키는 비율."""

    aperture_radius_m: float
    beam_radius_x_m: float
    beam_radius_y_m: float
    beam_center_u_m: float
    beam_center_v_m: float
    incidence_cosine: float
    transmission_fraction: float
    clipped_fraction: float
    input_power_w: float
    output_power_w: float
    loss_w: float
    loss_db: float | None
    quadrature_order: int | None
    method: str

    def to_dict(self) -> dict[str, float | int | str | None]:
        return {
            "aperture_radius_m": self.aperture_radius_m,
            "beam_radius_x_m": self.beam_radius_x_m,
            "beam_radius_y_m": self.beam_radius_y_m,
            "beam_center_u_m": self.beam_center_u_m,
            "beam_center_v_m": self.beam_center_v_m,
            "incidence_cosine": self.incidence_cosine,
            "transmission_fraction": self.transmission_fraction,
            "clipped_fraction": self.clipped_fraction,
            "input_power_w": self.input_power_w,
            "output_power_w": self.output_power_w,
            "loss_w": self.loss_w,
            "loss_db": self.loss_db,
            "quadrature_order": self.quadrature_order,
            "method": self.method,
        }


def _positive(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 유한한 값이어야 합니다.")
    return result


def circular_aperture_transmission_fraction(
    aperture_radius_m: float,
    beam_radius_x_m: float,
    beam_radius_y_m: float,
    *,
    radial_order: int = 96,
) -> tuple[float, str]:
    """Centered circular aperture가 통과시키는 Gaussian power fraction.

    원형 Gaussian은 closed form `1 - exp(-2 a² / w²)`를 사용한다. 타원/라인
    Gaussian은 같은 식을 억지 적용하지 않고, polar Gauss-Legendre quadrature로
    normalized irradiance를 적분한다.
    """

    aperture_radius = _positive(aperture_radius_m, name="aperture_radius_m")
    wx = _positive(beam_radius_x_m, name="beam_radius_x_m")
    wy = _positive(beam_radius_y_m, name="beam_radius_y_m")
    if math.isclose(wx, wy, rel_tol=1e-12, abs_tol=0.0):
        fraction = 1.0 - math.exp(-2.0 * (aperture_radius / wx) ** 2)
        return min(max(fraction, 0.0), 1.0), "closed_form_circular_gaussian"

    order = int(radial_order)
    if order < 16:
        raise ValueError("radial_order는 16 이상이어야 합니다.")
    nodes, weights = np.polynomial.legendre.leggauss(order)
    radii = 0.5 * aperture_radius * (nodes + 1.0)
    radial_weights = 0.5 * aperture_radius * weights
    inverse_x2 = 1.0 / (wx * wx)
    inverse_y2 = 1.0 / (wy * wy)
    sum_term = inverse_x2 + inverse_y2
    diff_term = inverse_x2 - inverse_y2
    argument = np.square(radii) * diff_term
    integrand = (
        4.0
        * radii
        / (wx * wy)
        * np.exp(-np.square(radii) * sum_term)
        * np.i0(argument)
    )
    fraction = float(np.sum(radial_weights * integrand))
    return min(max(fraction, 0.0), 1.0), "polar_gauss_legendre_elliptical_gaussian"


def circular_aperture_clip(
    beam: BeamState,
    *,
    aperture_diameter_m: float,
    radial_order: int = 96,
    surface_normal: Iterable[float] | None = None,
    aperture_x_axis: Iterable[float] | None = None,
    aperture_y_axis: Iterable[float] | None = None,
    beam_center_u_m: float = 0.0,
    beam_center_v_m: float = 0.0,
) -> ApertureClipResult:
    """현재 beam plane에서 circular aperture clipping ledger 값을 계산한다."""

    diameter = _positive(aperture_diameter_m, name="aperture_diameter_m")
    center_u = float(beam_center_u_m)
    center_v = float(beam_center_v_m)
    if not math.isfinite(center_u) or not math.isfinite(center_v):
        raise ValueError("beam center aperture 좌표는 유한해야 합니다.")
    surface_values = (surface_normal, aperture_x_axis, aperture_y_axis)
    if all(value is None for value in surface_values):
        if abs(center_u) > 0.0 or abs(center_v) > 0.0:
            raise ValueError("Decentered aperture clipping에는 surface frame이 필요합니다.")
        fraction, method = circular_aperture_transmission_fraction(
            diameter / 2.0,
            beam.radius_x_m,
            beam.radius_y_m,
            radial_order=radial_order,
        )
        incidence_cosine = 1.0
        used_order: int | None = None
    elif any(value is None for value in surface_values):
        raise ValueError(
            "surface_normal, aperture_x_axis와 aperture_y_axis를 모두 제공해야 합니다."
        )
    else:
        normal = normalize_vector(surface_normal, name="aperture surface normal")
        x_axis = normalize_vector(aperture_x_axis, name="aperture x axis")
        y_axis = normalize_vector(aperture_y_axis, name="aperture y axis")
        incidence_cosine = abs(float(np.dot(beam.direction, normal)))
        if incidence_cosine <= 1.0e-12:
            raise ValueError("Grazing circular aperture clipping은 지원하지 않습니다.")
        order = int(radial_order)
        if order < 16:
            raise ValueError("radial_order는 16 이상이어야 합니다.")
        nodes, weights = np.polynomial.legendre.leggauss(order)
        aperture_radius = 0.5 * diameter
        radii = 0.5 * aperture_radius * (nodes + 1.0)
        radial_weights = 0.5 * aperture_radius * weights
        angular_order = 2 * order
        theta = np.linspace(
            0.0,
            2.0 * math.pi,
            angular_order,
            endpoint=False,
            dtype=np.float64,
        )
        rr, tt = np.meshgrid(radii, theta, indexing="xy")
        uu = rr * np.cos(tt)
        vv = rr * np.sin(tt)
        surface_offsets = (
            (uu - center_u)[..., None] * x_axis
            + (vv - center_v)[..., None] * y_axis
        )
        beam_x = np.tensordot(
            surface_offsets,
            beam.transverse_x_axis,
            axes=([-1], [0]),
        )
        beam_y = np.tensordot(
            surface_offsets,
            beam.transverse_y_axis,
            axes=([-1], [0]),
        )
        integration_beam = beam if beam.power_w > 0.0 else replace(beam, power_w=1.0)
        irradiance = integration_beam.irradiance(beam_x, beam_y)
        radial_area_weights = radial_weights * radii
        integrated_power = float(
            np.sum(irradiance * radial_area_weights[None, :])
            * incidence_cosine
            * (2.0 * math.pi / angular_order)
        )
        fraction = min(
            max(integrated_power / integration_beam.power_w, 0.0),
            1.0,
        )
        method = "surface_projected_decentered_circular_gauss_legendre"
        used_order = order
    output_power = beam.power_w * fraction
    loss = beam.power_w - output_power
    loss_db = None if fraction <= 0.0 else -10.0 * math.log10(fraction)
    return ApertureClipResult(
        aperture_radius_m=diameter / 2.0,
        beam_radius_x_m=beam.radius_x_m,
        beam_radius_y_m=beam.radius_y_m,
        beam_center_u_m=center_u,
        beam_center_v_m=center_v,
        incidence_cosine=incidence_cosine,
        transmission_fraction=fraction,
        clipped_fraction=1.0 - fraction,
        input_power_w=beam.power_w,
        output_power_w=output_power,
        loss_w=loss,
        loss_db=loss_db,
        quadrature_order=used_order,
        method=method,
    )
