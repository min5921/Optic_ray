"""Gaussian beam의 centered circular aperture clipping 계산."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from lidarsim.beam import BeamState


@dataclass(frozen=True, slots=True)
class ApertureClipResult:
    """Circular aperture가 Gaussian power를 통과시키는 비율."""

    aperture_radius_m: float
    beam_radius_x_m: float
    beam_radius_y_m: float
    transmission_fraction: float
    clipped_fraction: float
    input_power_w: float
    output_power_w: float
    loss_w: float
    loss_db: float
    method: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "aperture_radius_m": self.aperture_radius_m,
            "beam_radius_x_m": self.beam_radius_x_m,
            "beam_radius_y_m": self.beam_radius_y_m,
            "transmission_fraction": self.transmission_fraction,
            "clipped_fraction": self.clipped_fraction,
            "input_power_w": self.input_power_w,
            "output_power_w": self.output_power_w,
            "loss_w": self.loss_w,
            "loss_db": self.loss_db,
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
) -> ApertureClipResult:
    """현재 beam plane에서 circular aperture clipping ledger 값을 계산한다."""

    diameter = _positive(aperture_diameter_m, name="aperture_diameter_m")
    fraction, method = circular_aperture_transmission_fraction(
        diameter / 2.0,
        beam.radius_x_m,
        beam.radius_y_m,
        radial_order=radial_order,
    )
    output_power = beam.power_w * fraction
    loss = beam.power_w - output_power
    loss_db = math.inf if fraction <= 0.0 else -10.0 * math.log10(fraction)
    return ApertureClipResult(
        aperture_radius_m=diameter / 2.0,
        beam_radius_x_m=beam.radius_x_m,
        beam_radius_y_m=beam.radius_y_m,
        transmission_fraction=fraction,
        clipped_fraction=1.0 - fraction,
        input_power_w=beam.power_w,
        output_power_w=output_power,
        loss_w=loss,
        loss_db=loss_db,
        method=method,
    )
