"""NumPy/float64 기반 Gaussian beam과 second-moment 기준 구현."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from lidarsim.geometry.transform import normalize_vector


FloatArray = NDArray[np.float64]
_GAUSSIAN_PROFILES = {"circular_gaussian", "elliptical_gaussian", "line_gaussian"}
_PROPAGATION_MODELS = {"gaussian_m2", "second_moment"}


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


def rayleigh_range_m(wavelength_m: float, waist_radius_m: float, m2: float = 1.0) -> float:
    """M²를 포함한 effective Rayleigh range를 반환한다."""

    wavelength = _positive(wavelength_m, name="wavelength_m")
    waist = _positive(waist_radius_m, name="waist_radius_m")
    quality = _finite(m2, name="m2")
    if quality < 1.0:
        raise ValueError("m2는 1 이상이어야 합니다.")
    return math.pi * waist * waist / (quality * wavelength)


def divergence_half_angle_rad(
    wavelength_m: float,
    waist_radius_m: float,
    m2: float = 1.0,
) -> float:
    """Far-field 1/e² radius divergence half-angle을 반환한다."""

    wavelength = _positive(wavelength_m, name="wavelength_m")
    waist = _positive(waist_radius_m, name="waist_radius_m")
    quality = _finite(m2, name="m2")
    if quality < 1.0:
        raise ValueError("m2는 1 이상이어야 합니다.")
    return quality * wavelength / (math.pi * waist)


def gaussian_radius_m(
    distance_from_waist_m: float | NDArray[np.float64],
    wavelength_m: float,
    waist_radius_m: float,
    m2: float = 1.0,
) -> float | FloatArray:
    """Waist로부터 거리에서의 1/e² intensity radius를 계산한다."""

    distance = np.asarray(distance_from_waist_m, dtype=np.float64)
    if not np.all(np.isfinite(distance)):
        raise ValueError("distance_from_waist_m에는 유한한 숫자만 사용할 수 있습니다.")
    rayleigh = rayleigh_range_m(wavelength_m, waist_radius_m, m2)
    radius = float(waist_radius_m) * np.sqrt(1.0 + np.square(distance / rayleigh))
    if radius.ndim == 0:
        return float(radius)
    return np.asarray(radius, dtype=np.float64)


@dataclass(frozen=True, slots=True, eq=False)
class SecondMoment1D:
    """한 transverse axis의 `[position, angle]` covariance reference."""

    covariance: FloatArray
    wavelength_m: float

    def __post_init__(self) -> None:
        covariance = np.array(self.covariance, dtype=np.float64, copy=True)
        if covariance.shape != (2, 2) or not np.all(np.isfinite(covariance)):
            raise ValueError("covariance는 유한한 2x2 matrix여야 합니다.")
        if not np.allclose(covariance, covariance.T, rtol=0.0, atol=1e-15):
            raise ValueError("covariance는 symmetric matrix여야 합니다.")
        eigenvalues = np.linalg.eigvalsh(covariance)
        if float(np.min(eigenvalues)) < -1e-18:
            raise ValueError("covariance는 positive semidefinite여야 합니다.")
        covariance.setflags(write=False)
        object.__setattr__(self, "covariance", covariance)
        object.__setattr__(
            self,
            "wavelength_m",
            _positive(self.wavelength_m, name="wavelength_m"),
        )

    @classmethod
    def from_waist(
        cls,
        waist_radius_m: float,
        wavelength_m: float,
        m2: float = 1.0,
    ) -> "SecondMoment1D":
        waist = _positive(waist_radius_m, name="waist_radius_m")
        divergence = divergence_half_angle_rad(wavelength_m, waist, m2)
        covariance = np.diag((waist * waist / 4.0, divergence * divergence / 4.0))
        return cls(covariance, wavelength_m)

    @property
    def radius_m(self) -> float:
        return 2.0 * math.sqrt(max(float(self.covariance[0, 0]), 0.0))

    @property
    def divergence_rad(self) -> float:
        return 2.0 * math.sqrt(max(float(self.covariance[1, 1]), 0.0))

    @property
    def m2(self) -> float:
        determinant = max(float(np.linalg.det(self.covariance)), 0.0)
        return 4.0 * math.pi * math.sqrt(determinant) / self.wavelength_m

    def propagate(self, distance_m: float) -> "SecondMoment1D":
        distance = _finite(distance_m, name="distance_m")
        transfer = np.array(((1.0, distance), (0.0, 1.0)), dtype=np.float64)
        return SecondMoment1D(transfer @ self.covariance @ transfer.T, self.wavelength_m)


@dataclass(frozen=True, slots=True, eq=False)
class GaussianProfileSample:
    """한 plane의 local transverse irradiance sample."""

    x_m: FloatArray
    y_m: FloatArray
    irradiance_w_m2: FloatArray
    radius_x_m: float
    radius_y_m: float
    requested_power_w: float
    integrated_power_w: float

    @property
    def relative_power_error(self) -> float:
        return abs(self.integrated_power_w - self.requested_power_w) / self.requested_power_w


@dataclass(frozen=True, slots=True, eq=False)
class BeamState:
    """한 reference plane에서의 불변 Gaussian beam state."""

    time_s: float
    origin_m: FloatArray
    direction: FloatArray
    transverse_x_axis: FloatArray
    wavelength_m: float
    power_w: float
    waist_radius_x_m: float
    waist_radius_y_m: float
    m2_x: float = 1.0
    m2_y: float = 1.0
    profile_kind: str = "circular_gaussian"
    propagation_model: str = "gaussian_m2"
    polarization: str = "scalar_unspecified"
    distance_from_waist_m: float = 0.0
    optical_path_length_m: float = 0.0
    accumulated_transmission: float = 1.0
    source_component_id: str | None = None
    source_component_ref: str | None = None
    optical_path_id: str | None = None
    transverse_y_axis: FloatArray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        direction = normalize_vector(self.direction, name="beam direction")
        x_candidate = np.asarray(self.transverse_x_axis, dtype=np.float64)
        if x_candidate.shape != (3,) or not np.all(np.isfinite(x_candidate)):
            raise ValueError("transverse_x_axis는 유한한 vec3여야 합니다.")
        x_axis = normalize_vector(
            x_candidate - float(np.dot(x_candidate, direction)) * direction,
            name="beam transverse x axis",
        )
        y_axis = normalize_vector(np.cross(direction, x_axis), name="beam transverse y axis")
        origin = np.array(self.origin_m, dtype=np.float64, copy=True)
        if origin.shape != (3,) or not np.all(np.isfinite(origin)):
            raise ValueError("origin_m은 유한한 vec3여야 합니다.")
        origin.setflags(write=False)
        object.__setattr__(self, "origin_m", origin)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "transverse_x_axis", x_axis)
        object.__setattr__(self, "transverse_y_axis", y_axis)
        object.__setattr__(self, "time_s", _finite(self.time_s, name="time_s"))
        object.__setattr__(self, "wavelength_m", _positive(self.wavelength_m, name="wavelength_m"))
        object.__setattr__(self, "power_w", _positive(self.power_w, name="power_w"))
        object.__setattr__(
            self,
            "waist_radius_x_m",
            _positive(self.waist_radius_x_m, name="waist_radius_x_m"),
        )
        object.__setattr__(
            self,
            "waist_radius_y_m",
            _positive(self.waist_radius_y_m, name="waist_radius_y_m"),
        )
        for name in ("m2_x", "m2_y"):
            value = _finite(getattr(self, name), name=name)
            if value < 1.0:
                raise ValueError(f"{name}는 1 이상이어야 합니다.")
            object.__setattr__(self, name, value)
        if self.profile_kind not in _GAUSSIAN_PROFILES:
            raise ValueError(f"지원하지 않는 Gaussian profile_kind입니다: {self.profile_kind!r}")
        if self.propagation_model not in _PROPAGATION_MODELS:
            raise ValueError(f"지원하지 않는 propagation_model입니다: {self.propagation_model!r}")
        if self.profile_kind == "circular_gaussian" and not (
            math.isclose(self.waist_radius_x_m, self.waist_radius_y_m, rel_tol=1e-12)
            and math.isclose(self.m2_x, self.m2_y, rel_tol=1e-12)
        ):
            raise ValueError("circular_gaussian은 x/y waist radius와 M²가 같아야 합니다.")
        if self.profile_kind == "line_gaussian" and math.isclose(
            self.waist_radius_x_m,
            self.waist_radius_y_m,
            rel_tol=1e-12,
        ):
            raise ValueError("line_gaussian은 서로 다른 x/y waist radius가 필요합니다.")
        object.__setattr__(
            self,
            "distance_from_waist_m",
            _finite(self.distance_from_waist_m, name="distance_from_waist_m"),
        )
        object.__setattr__(
            self,
            "optical_path_length_m",
            _positive(
                self.optical_path_length_m,
                name="optical_path_length_m",
                allow_zero=True,
            ),
        )
        transmission = _finite(self.accumulated_transmission, name="accumulated_transmission")
        if not 0.0 <= transmission <= 1.0:
            raise ValueError("accumulated_transmission은 0과 1 사이여야 합니다.")
        object.__setattr__(self, "accumulated_transmission", transmission)

    @property
    def rayleigh_range_x_m(self) -> float:
        return rayleigh_range_m(self.wavelength_m, self.waist_radius_x_m, self.m2_x)

    @property
    def rayleigh_range_y_m(self) -> float:
        return rayleigh_range_m(self.wavelength_m, self.waist_radius_y_m, self.m2_y)

    @property
    def divergence_x_rad(self) -> float:
        return divergence_half_angle_rad(self.wavelength_m, self.waist_radius_x_m, self.m2_x)

    @property
    def divergence_y_rad(self) -> float:
        return divergence_half_angle_rad(self.wavelength_m, self.waist_radius_y_m, self.m2_y)

    @property
    def radius_x_m(self) -> float:
        return float(
            gaussian_radius_m(
                self.distance_from_waist_m,
                self.wavelength_m,
                self.waist_radius_x_m,
                self.m2_x,
            )
        )

    @property
    def radius_y_m(self) -> float:
        return float(
            gaussian_radius_m(
                self.distance_from_waist_m,
                self.wavelength_m,
                self.waist_radius_y_m,
                self.m2_y,
            )
        )

    @property
    def q_x_m(self) -> complex:
        return complex(self.distance_from_waist_m, self.rayleigh_range_x_m)

    @property
    def q_y_m(self) -> complex:
        return complex(self.distance_from_waist_m, self.rayleigh_range_y_m)

    def radius_at(self, distance_m: float | FloatArray) -> tuple[float | FloatArray, float | FloatArray]:
        distance = np.asarray(distance_m, dtype=np.float64)
        if not np.all(np.isfinite(distance)):
            raise ValueError("distance_m에는 유한한 숫자만 사용할 수 있습니다.")
        from_waist = self.distance_from_waist_m + distance
        return (
            gaussian_radius_m(from_waist, self.wavelength_m, self.waist_radius_x_m, self.m2_x),
            gaussian_radius_m(from_waist, self.wavelength_m, self.waist_radius_y_m, self.m2_y),
        )

    def second_moments(self) -> tuple[SecondMoment1D, SecondMoment1D]:
        return (
            SecondMoment1D.from_waist(
                self.waist_radius_x_m,
                self.wavelength_m,
                self.m2_x,
            ).propagate(self.distance_from_waist_m),
            SecondMoment1D.from_waist(
                self.waist_radius_y_m,
                self.wavelength_m,
                self.m2_y,
            ).propagate(self.distance_from_waist_m),
        )

    def propagate_free_space(self, distance_m: float) -> "BeamState":
        """Forward free-space propagation으로 새 state를 반환한다."""

        distance = _positive(distance_m, name="distance_m", allow_zero=True)
        return replace(
            self,
            origin_m=self.origin_m + distance * self.direction,
            distance_from_waist_m=self.distance_from_waist_m + distance,
            optical_path_length_m=self.optical_path_length_m + distance,
        )

    def irradiance(
        self,
        x_m: ArrayLike,
        y_m: ArrayLike,
        *,
        distance_m: float = 0.0,
    ) -> FloatArray:
        """Local transverse coordinate의 power-normalized irradiance를 계산한다."""

        radius_x, radius_y = self.radius_at(distance_m)
        wx = float(radius_x)
        wy = float(radius_y)
        x = np.asarray(x_m, dtype=np.float64)
        y = np.asarray(y_m, dtype=np.float64)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("profile coordinate에는 유한한 숫자만 사용할 수 있습니다.")
        peak = 2.0 * self.power_w / (math.pi * wx * wy)
        return np.asarray(
            peak * np.exp(-2.0 * (np.square(x / wx) + np.square(y / wy))),
            dtype=np.float64,
        )

    def amplitude_weight(
        self,
        x_m: ArrayLike,
        y_m: ArrayLike,
        *,
        distance_m: float = 0.0,
    ) -> FloatArray:
        """Dimensionless Gaussian field-amplitude weight를 반환한다."""

        radius_x, radius_y = self.radius_at(distance_m)
        x = np.asarray(x_m, dtype=np.float64)
        y = np.asarray(y_m, dtype=np.float64)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("profile coordinate에는 유한한 숫자만 사용할 수 있습니다.")
        return np.asarray(
            np.exp(-1.0 * (np.square(x / float(radius_x)) + np.square(y / float(radius_y)))),
            dtype=np.float64,
        )

    def sample_profile(
        self,
        *,
        distance_m: float = 0.0,
        grid_size: int = 301,
        extent_radii: float = 4.0,
    ) -> GaussianProfileSample:
        """Power integration과 plot용 regular local grid를 만든다."""

        if int(grid_size) < 11:
            raise ValueError("grid_size는 11 이상이어야 합니다.")
        if int(grid_size) % 2 == 0:
            raise ValueError("grid_size는 beam center를 포함하도록 홀수여야 합니다.")
        extent = _positive(extent_radii, name="extent_radii")
        radius_x, radius_y = self.radius_at(distance_m)
        wx = float(radius_x)
        wy = float(radius_y)
        x = np.linspace(-extent * wx, extent * wx, int(grid_size), dtype=np.float64)
        y = np.linspace(-extent * wy, extent * wy, int(grid_size), dtype=np.float64)
        mesh_x, mesh_y = np.meshgrid(x, y, indexing="xy")
        irradiance = self.irradiance(mesh_x, mesh_y, distance_m=distance_m)
        integrated_x = np.trapezoid(irradiance, x=x, axis=1)
        integrated_power = float(np.trapezoid(integrated_x, x=y))
        for array in (x, y, irradiance):
            array.setflags(write=False)
        return GaussianProfileSample(
            x_m=x,
            y_m=y,
            irradiance_w_m2=irradiance,
            radius_x_m=wx,
            radius_y_m=wy,
            requested_power_w=self.power_w,
            integrated_power_w=integrated_power,
        )

    def to_dict(self) -> dict[str, Any]:
        """구조화 report용 SI-unit mapping을 반환한다."""

        return {
            "time_s": self.time_s,
            "origin_m": self.origin_m.tolist(),
            "direction": self.direction.tolist(),
            "transverse_x_axis": self.transverse_x_axis.tolist(),
            "transverse_y_axis": self.transverse_y_axis.tolist(),
            "wavelength_m": self.wavelength_m,
            "power_w": self.power_w,
            "profile_kind": self.profile_kind,
            "propagation_model": self.propagation_model,
            "waist_radius_x_m": self.waist_radius_x_m,
            "waist_radius_y_m": self.waist_radius_y_m,
            "m2_x": self.m2_x,
            "m2_y": self.m2_y,
            "rayleigh_range_x_m": self.rayleigh_range_x_m,
            "rayleigh_range_y_m": self.rayleigh_range_y_m,
            "divergence_x_rad": self.divergence_x_rad,
            "divergence_y_rad": self.divergence_y_rad,
            "distance_from_waist_m": self.distance_from_waist_m,
            "radius_x_m": self.radius_x_m,
            "radius_y_m": self.radius_y_m,
            "polarization": self.polarization,
            "optical_path_length_m": self.optical_path_length_m,
            "accumulated_transmission": self.accumulated_transmission,
            "source_component_id": self.source_component_id,
            "source_component_ref": self.source_component_ref,
            "optical_path_id": self.optical_path_id,
        }
