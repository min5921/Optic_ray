"""Gaussian q-parameter용 paraxial ABCD transform."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np

from lidarsim.beam import BeamState
from lidarsim.geometry.transform import normalize_vector


def _finite(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name}에는 유한한 숫자만 사용할 수 있습니다.")
    return result


def _positive(value: float, *, name: str, allow_zero: bool = False) -> float:
    result = _finite(value, name=name)
    invalid = result < 0.0 if allow_zero else result <= 0.0
    if invalid:
        relation = "0 이상" if allow_zero else "0보다 큰 값"
        raise ValueError(f"{name}은 {relation}이어야 합니다.")
    return result


@dataclass(frozen=True, slots=True)
class ABCDMatrix:
    """동일 매질 내 paraxial ray/q-parameter transform.

    Matrix는 `q_out = (A q_in + B) / (C q_in + D)` convention을 사용한다.
    현재 Phase 2 reference path는 determinant가 1인 free-space와 thin-lens
    transform만 생성한다.
    """

    A: float
    B: float
    C: float
    D: float

    def __post_init__(self) -> None:
        for name in ("A", "B", "C", "D"):
            object.__setattr__(self, name, _finite(getattr(self, name), name=name))
        determinant = self.determinant
        if abs(determinant) <= 1e-15:
            raise ValueError("ABCD matrix determinant는 0일 수 없습니다.")

    @classmethod
    def free_space(cls, distance_m: float) -> "ABCDMatrix":
        """길이 `distance_m`의 자유공간 propagation matrix를 만든다."""

        distance = _positive(distance_m, name="distance_m", allow_zero=True)
        return cls(1.0, distance, 0.0, 1.0)

    @classmethod
    def thin_lens(cls, focal_length_m: float) -> "ABCDMatrix":
        """초점거리 `focal_length_m`의 ideal zero-thickness thin lens matrix."""

        focal_length = _positive(focal_length_m, name="focal_length_m")
        return cls(1.0, 0.0, -1.0 / focal_length, 1.0)

    @property
    def determinant(self) -> float:
        return self.A * self.D - self.B * self.C

    def as_nested_list(self) -> list[list[float]]:
        return [[self.A, self.B], [self.C, self.D]]

    def compose_after(self, previous: "ABCDMatrix") -> "ABCDMatrix":
        """`previous` 다음에 현재 matrix를 적용하는 합성 matrix를 반환한다."""

        return ABCDMatrix(
            self.A * previous.A + self.B * previous.C,
            self.A * previous.B + self.B * previous.D,
            self.C * previous.A + self.D * previous.C,
            self.C * previous.B + self.D * previous.D,
        )

    def apply_q(self, q_m: complex) -> complex:
        """Complex q-parameter에 matrix를 적용한다."""

        q = complex(q_m)
        denominator = self.C * q + self.D
        if abs(denominator) <= 1e-15:
            raise ValueError("ABCD q-transform denominator가 0에 가깝습니다.")
        result = (self.A * q + self.B) / denominator
        if not math.isfinite(result.real) or not math.isfinite(result.imag):
            raise ValueError("ABCD q-transform 결과가 유한하지 않습니다.")
        if result.imag <= 0.0:
            raise ValueError("ABCD q-transform 결과의 Rayleigh range가 양수가 아닙니다.")
        return result


def _axis(value: Iterable[float] | np.ndarray | None, fallback: np.ndarray, *, name: str) -> np.ndarray:
    if value is None:
        return fallback
    return normalize_vector(value, name=name)


def _origin(value: Iterable[float] | np.ndarray | None, fallback: np.ndarray) -> np.ndarray:
    if value is None:
        return fallback
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError("origin_m은 유한한 vec3여야 합니다.")
    return result


def _waist_radius_from_q_imag(q_imag_m: float, wavelength_m: float, m2: float) -> float:
    return math.sqrt(float(m2) * float(wavelength_m) * q_imag_m / math.pi)


def apply_abcd_to_beam(
    beam: BeamState,
    matrix: ABCDMatrix,
    *,
    origin_m: Iterable[float] | np.ndarray | None = None,
    direction: Iterable[float] | np.ndarray | None = None,
    transverse_x_axis: Iterable[float] | np.ndarray | None = None,
    optical_path_increment_m: float = 0.0,
    power_transmission: float = 1.0,
) -> BeamState:
    """BeamState의 x/y q-parameter에 같은 ABCD transform을 적용한다.

    Thin lens처럼 reference plane 위치가 바뀌지 않는 요소는
    `optical_path_increment_m=0`으로 둔다. Aperture/transmission loss는
    `power_transmission`으로만 반영하며, truncated profile diffraction은
    현재 Phase 2 reference path에서 계산하지 않는다.
    """

    path_increment = _positive(
        optical_path_increment_m,
        name="optical_path_increment_m",
        allow_zero=True,
    )
    transmission = _finite(power_transmission, name="power_transmission")
    if not 0.0 < transmission <= 1.0:
        raise ValueError("power_transmission은 0보다 크고 1 이하이어야 합니다.")

    q_x = matrix.apply_q(beam.q_x_m)
    q_y = matrix.apply_q(beam.q_y_m)
    if not math.isclose(q_x.real, q_y.real, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(
            "현재 BeamState는 x/y waist 위치가 다른 astigmatic post-lens beam을 "
            "정확히 표현하지 못합니다. Phase 2 first slice에서는 circular Gaussian "
            "또는 x/y q real이 같은 경우만 지원합니다."
        )
    new_origin = _origin(origin_m, beam.origin_m)
    new_direction = _axis(direction, beam.direction, name="beam direction")
    new_x_axis = _axis(transverse_x_axis, beam.transverse_x_axis, name="beam transverse x axis")

    return replace(
        beam,
        origin_m=new_origin,
        direction=new_direction,
        transverse_x_axis=new_x_axis,
        power_w=beam.power_w * transmission,
        waist_radius_x_m=_waist_radius_from_q_imag(q_x.imag, beam.wavelength_m, beam.m2_x),
        waist_radius_y_m=_waist_radius_from_q_imag(q_y.imag, beam.wavelength_m, beam.m2_y),
        distance_from_waist_m=q_x.real,
        optical_path_length_m=beam.optical_path_length_m + path_increment,
        accumulated_transmission=beam.accumulated_transmission * transmission,
    )
