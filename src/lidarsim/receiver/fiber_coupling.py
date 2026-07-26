"""Single-mode Gaussian-to-Gaussian fiber coupling reference model.

The calculation is deliberately limited to two normalized scalar Gaussian fields
defined on one common receive plane.  ``mode_radius_*_m`` is the 1/e field
amplitude radius, equivalently the 1/e^2 intensity radius and half the Gaussian
mode-field diameter (MFD).  The complex field overlap is kept separate from its
power efficiency and from the available optical power.  A coherent output field
is produced only when the caller supplies an explicit coherent input field; this
module never invents a zero phase from radiometric power.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from typing import Any, Iterable


PairInput = float | Iterable[float]
WavefrontInput = float | None | Iterable[float | None]


def _finite(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name}에는 유한한 숫자만 사용할 수 있습니다.")
    return result


def _positive(value: float, *, name: str) -> float:
    result = _finite(value, name=name)
    if result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 값이어야 합니다.")
    return result


def _nonnegative(value: float, *, name: str) -> float:
    result = _finite(value, name=name)
    if result < 0.0:
        raise ValueError(f"{name}은 0 이상이어야 합니다.")
    return result


def _pair(value: PairInput, *, name: str, positive: bool = False) -> tuple[float, float]:
    if isinstance(value, (int, float)):
        raw = (float(value), float(value))
    else:
        raw = tuple(float(item) for item in value)
        if len(raw) != 2:
            raise ValueError(f"{name}은 scalar 또는 길이 2의 x/y 값이어야 합니다.")
    validator = _positive if positive else _finite
    return (
        validator(raw[0], name=f"{name}[0]"),
        validator(raw[1], name=f"{name}[1]"),
    )


def _wavefront_pair(value: WavefrontInput, *, name: str) -> tuple[float | None, float | None]:
    if value is None:
        raw: tuple[float | None, float | None] = (None, None)
    elif isinstance(value, (int, float)):
        raw = (float(value), float(value))
    else:
        items = tuple(value)
        if len(items) != 2:
            raise ValueError(f"{name}은 scalar, None 또는 길이 2의 x/y 값이어야 합니다.")
        raw = (
            None if items[0] is None else float(items[0]),
            None if items[1] is None else float(items[1]),
        )

    resolved: list[float | None] = []
    for index, item in enumerate(raw):
        if item is None:
            resolved.append(None)
            continue
        radius = _finite(item, name=f"{name}[{index}]")
        if radius == 0.0:
            raise ValueError(
                f"{name}[{index}]은 0일 수 없습니다. 평면 wavefront는 None으로 표시하세요."
            )
        resolved.append(radius)
    return resolved[0], resolved[1]


def _complex_overlap_dict(value: complex) -> dict[str, float]:
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "magnitude": float(abs(value)),
    }


def _complex_field_dict(value: complex | None) -> dict[str, float] | None:
    if value is None:
        return None
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "magnitude_sqrt_w": float(abs(value)),
        "power_w": float(abs(value) ** 2),
    }


def _field_amplitude(value: complex, *, name: str) -> complex:
    result = complex(value)
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise ValueError(f"{name}의 실수부와 허수부는 유한해야 합니다.")
    return result


@dataclass(frozen=True, slots=True)
class GaussianModeAtPlane:
    """One scalar Gaussian mode resolved at a common transverse plane.

    Radii use the Gaussian 1/e^2 intensity convention.  ``None`` wavefront
    radius means infinite radius (a planar wavefront/waist at this plane).
    Positive and negative finite wavefront radii retain propagation direction
    information.  Center and angle fields are expressed in the same local x/y
    frame for both modes.
    """

    mode_radius_x_m: float
    mode_radius_y_m: float
    center_offset_x_m: float = 0.0
    center_offset_y_m: float = 0.0
    angle_x_rad: float = 0.0
    angle_y_rad: float = 0.0
    wavefront_radius_x_m: float | None = None
    wavefront_radius_y_m: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mode_radius_x_m",
            _positive(self.mode_radius_x_m, name="mode_radius_x_m"),
        )
        object.__setattr__(
            self,
            "mode_radius_y_m",
            _positive(self.mode_radius_y_m, name="mode_radius_y_m"),
        )
        for field_name in (
            "center_offset_x_m",
            "center_offset_y_m",
            "angle_x_rad",
            "angle_y_rad",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite(getattr(self, field_name), name=field_name),
            )
        wavefront = _wavefront_pair(
            (self.wavefront_radius_x_m, self.wavefront_radius_y_m),
            name="wavefront_radius_m",
        )
        object.__setattr__(self, "wavefront_radius_x_m", wavefront[0])
        object.__setattr__(self, "wavefront_radius_y_m", wavefront[1])

    @classmethod
    def circular(
        cls,
        mode_radius_m: float,
        *,
        center_offset_m: PairInput = (0.0, 0.0),
        angular_offset_rad: PairInput = (0.0, 0.0),
        wavefront_radius_m: WavefrontInput = None,
    ) -> "GaussianModeAtPlane":
        """Create a circular mode from its 1/e^2 intensity radius."""

        radius = _positive(mode_radius_m, name="mode_radius_m")
        center = _pair(center_offset_m, name="center_offset_m")
        angle = _pair(angular_offset_rad, name="angular_offset_rad")
        wavefront = _wavefront_pair(wavefront_radius_m, name="wavefront_radius_m")
        return cls(
            mode_radius_x_m=radius,
            mode_radius_y_m=radius,
            center_offset_x_m=center[0],
            center_offset_y_m=center[1],
            angle_x_rad=angle[0],
            angle_y_rad=angle[1],
            wavefront_radius_x_m=wavefront[0],
            wavefront_radius_y_m=wavefront[1],
        )

    @classmethod
    def from_mode_field_diameter(
        cls,
        mode_field_diameter_m: PairInput,
        *,
        center_offset_m: PairInput = (0.0, 0.0),
        angular_offset_rad: PairInput = (0.0, 0.0),
        wavefront_radius_m: WavefrontInput = None,
    ) -> "GaussianModeAtPlane":
        """Create a mode from Gaussian 1/e^2 intensity MFD x/y values."""

        diameter = _pair(
            mode_field_diameter_m,
            name="mode_field_diameter_m",
            positive=True,
        )
        center = _pair(center_offset_m, name="center_offset_m")
        angle = _pair(angular_offset_rad, name="angular_offset_rad")
        wavefront = _wavefront_pair(wavefront_radius_m, name="wavefront_radius_m")
        return cls(
            mode_radius_x_m=0.5 * diameter[0],
            mode_radius_y_m=0.5 * diameter[1],
            center_offset_x_m=center[0],
            center_offset_y_m=center[1],
            angle_x_rad=angle[0],
            angle_y_rad=angle[1],
            wavefront_radius_x_m=wavefront[0],
            wavefront_radius_y_m=wavefront[1],
        )

    @classmethod
    def from_waist_at_plane(
        cls,
        waist_radius_m: PairInput,
        *,
        wavelength_m: float,
        distance_from_waist_m: PairInput = (0.0, 0.0),
        center_offset_m: PairInput = (0.0, 0.0),
        angular_offset_rad: PairInput = (0.0, 0.0),
    ) -> "GaussianModeAtPlane":
        """Propagate ideal M²=1 waist data to the coupling evaluation plane.

        ``distance_from_waist_m`` is signed: positive means the evaluation plane
        is after the waist in the mode propagation direction.  This constructor
        provides an explicit focus-mismatch input without introducing a separate
        propagation engine into the overlap calculation.
        """

        wavelength = _positive(wavelength_m, name="wavelength_m")
        waist = _pair(waist_radius_m, name="waist_radius_m", positive=True)
        distance = _pair(distance_from_waist_m, name="distance_from_waist_m")
        center = _pair(center_offset_m, name="center_offset_m")
        angle = _pair(angular_offset_rad, name="angular_offset_rad")

        radii: list[float] = []
        wavefronts: list[float | None] = []
        for waist_axis, distance_axis in zip(waist, distance, strict=True):
            rayleigh_range = math.pi * waist_axis * waist_axis / wavelength
            radii.append(
                waist_axis * math.sqrt(1.0 + (distance_axis / rayleigh_range) ** 2)
            )
            if distance_axis == 0.0:
                wavefronts.append(None)
            else:
                wavefronts.append(
                    distance_axis * (1.0 + (rayleigh_range / distance_axis) ** 2)
                )

        return cls(
            mode_radius_x_m=radii[0],
            mode_radius_y_m=radii[1],
            center_offset_x_m=center[0],
            center_offset_y_m=center[1],
            angle_x_rad=angle[0],
            angle_y_rad=angle[1],
            wavefront_radius_x_m=wavefronts[0],
            wavefront_radius_y_m=wavefronts[1],
        )

    @property
    def mode_field_diameter_x_m(self) -> float:
        return 2.0 * self.mode_radius_x_m

    @property
    def mode_field_diameter_y_m(self) -> float:
        return 2.0 * self.mode_radius_y_m

    def to_dict(self) -> dict[str, float | None]:
        return {
            "mode_radius_x_m": self.mode_radius_x_m,
            "mode_radius_y_m": self.mode_radius_y_m,
            "mode_field_diameter_x_m": self.mode_field_diameter_x_m,
            "mode_field_diameter_y_m": self.mode_field_diameter_y_m,
            "center_offset_x_m": self.center_offset_x_m,
            "center_offset_y_m": self.center_offset_y_m,
            "angle_x_rad": self.angle_x_rad,
            "angle_y_rad": self.angle_y_rad,
            "wavefront_radius_x_m": self.wavefront_radius_x_m,
            "wavefront_radius_y_m": self.wavefront_radius_y_m,
        }


@dataclass(frozen=True, slots=True)
class FiberCouplingResult:
    """Normalized Gaussian field overlap and its distinct power quantities."""

    model: str
    model_scope: str
    input_power_interpretation: str
    wavelength_m: float
    receive_mode: GaussianModeAtPlane
    fiber_mode: GaussianModeAtPlane
    available_power_at_fiber_plane_w: float
    normalized_field_overlap: complex
    input_field_amplitude_sqrt_w: complex | None
    coupled_field_amplitude_sqrt_w: complex | None
    coherent_field_status: str
    fiber_coupling_efficiency: float
    power_coupled_into_fiber_w: float
    status: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "model_scope": self.model_scope,
            "input_power_interpretation": self.input_power_interpretation,
            "wavelength_m": self.wavelength_m,
            "receive_mode": self.receive_mode.to_dict(),
            "fiber_mode": self.fiber_mode.to_dict(),
            "available_power_at_fiber_plane_w": self.available_power_at_fiber_plane_w,
            "normalized_field_overlap": _complex_overlap_dict(
                self.normalized_field_overlap
            ),
            "input_field_amplitude_sqrt_w": _complex_field_dict(
                self.input_field_amplitude_sqrt_w
            ),
            "coupled_field_amplitude_sqrt_w": _complex_field_dict(
                self.coupled_field_amplitude_sqrt_w
            ),
            "coherent_field_status": self.coherent_field_status,
            "fiber_coupling_efficiency": self.fiber_coupling_efficiency,
            "power_coupled_into_fiber_w": self.power_coupled_into_fiber_w,
            "status": self.status,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _inverse_wavefront_radius(radius_m: float | None) -> float:
    return 0.0 if radius_m is None else 1.0 / radius_m


def _axis_field_overlap(
    *,
    wavelength_m: float,
    receive_radius_m: float,
    fiber_radius_m: float,
    receive_center_m: float,
    fiber_center_m: float,
    receive_angle_rad: float,
    fiber_angle_rad: float,
    receive_wavefront_radius_m: float | None,
    fiber_wavefront_radius_m: float | None,
) -> complex:
    """Return one-axis normalized field overlap in a fiber-centered phase frame."""

    wave_number = math.tau / wavelength_m
    receive_quadratic = complex(
        1.0 / (receive_radius_m * receive_radius_m),
        0.5 * wave_number * _inverse_wavefront_radius(receive_wavefront_radius_m),
    )
    # The fiber field is conjugated in <fiber|receive>.
    fiber_quadratic_conjugate = complex(
        1.0 / (fiber_radius_m * fiber_radius_m),
        -0.5 * wave_number * _inverse_wavefront_radius(fiber_wavefront_radius_m),
    )
    combined = receive_quadratic + fiber_quadratic_conjugate
    center_delta = receive_center_m - fiber_center_m
    angular_phase = 1j * wave_number * (receive_angle_rad - fiber_angle_rad)

    # Algebraically reduced form avoids subtracting two very large center terms.
    exponent = (
        -receive_quadratic
        * fiber_quadratic_conjugate
        * center_delta
        * center_delta
        + receive_quadratic * center_delta * angular_phase
        + 0.25 * angular_phase * angular_phase
    ) / combined
    normalization = math.sqrt(
        2.0 / (math.pi * receive_radius_m * fiber_radius_m)
    )
    return normalization * cmath.sqrt(math.pi / combined) * cmath.exp(exponent)


def estimate_single_mode_fiber_coupling(
    *,
    available_power_at_fiber_plane_w: float,
    wavelength_m: float,
    receive_mode: GaussianModeAtPlane,
    fiber_mode: GaussianModeAtPlane,
    input_field_amplitude_sqrt_w: complex | None = None,
) -> FiberCouplingResult:
    """Calculate normalized scalar Gaussian overlap at a fiber reference plane.

    The input power is a separate power-ledger quantity carried by the declared
    deterministic Gaussian ``receive_mode`` at the evaluation plane.  It is not
    inferred from the dimensionless normalized overlap.

    ``input_field_amplitude_sqrt_w`` is optional.  When omitted, only overlap,
    efficiency and coupled power are evaluated; both field-amplitude results are
    ``None``.  When provided, it must have units sqrt(W) and ``abs(E)**2`` must
    match ``available_power_at_fiber_plane_w``.  Only then is the coupled complex
    field calculated.  In particular, callers must not manufacture an arbitrary
    zero-phase field from a Lambertian radiometric power result.
    """

    power = _nonnegative(
        available_power_at_fiber_plane_w,
        name="available_power_at_fiber_plane_w",
    )
    wavelength = _positive(wavelength_m, name="wavelength_m")
    if not isinstance(receive_mode, GaussianModeAtPlane):
        raise TypeError("receive_mode는 GaussianModeAtPlane이어야 합니다.")
    if not isinstance(fiber_mode, GaussianModeAtPlane):
        raise TypeError("fiber_mode는 GaussianModeAtPlane이어야 합니다.")
    input_field = (
        None
        if input_field_amplitude_sqrt_w is None
        else _field_amplitude(
            input_field_amplitude_sqrt_w,
            name="input_field_amplitude_sqrt_w",
        )
    )
    if input_field is not None:
        input_field_power = float(abs(input_field) ** 2)
        consistent = (
            input_field == 0.0j
            if power == 0.0
            else math.isclose(
                input_field_power,
                power,
                rel_tol=1.0e-12,
                abs_tol=0.0,
            )
        )
        if not consistent:
            raise ValueError(
                "input_field_amplitude_sqrt_w는 sqrt(W) 단위여야 하며 "
                "abs(field)**2가 available_power_at_fiber_plane_w와 일치해야 합니다."
            )

    overlap_x = _axis_field_overlap(
        wavelength_m=wavelength,
        receive_radius_m=receive_mode.mode_radius_x_m,
        fiber_radius_m=fiber_mode.mode_radius_x_m,
        receive_center_m=receive_mode.center_offset_x_m,
        fiber_center_m=fiber_mode.center_offset_x_m,
        receive_angle_rad=receive_mode.angle_x_rad,
        fiber_angle_rad=fiber_mode.angle_x_rad,
        receive_wavefront_radius_m=receive_mode.wavefront_radius_x_m,
        fiber_wavefront_radius_m=fiber_mode.wavefront_radius_x_m,
    )
    overlap_y = _axis_field_overlap(
        wavelength_m=wavelength,
        receive_radius_m=receive_mode.mode_radius_y_m,
        fiber_radius_m=fiber_mode.mode_radius_y_m,
        receive_center_m=receive_mode.center_offset_y_m,
        fiber_center_m=fiber_mode.center_offset_y_m,
        receive_angle_rad=receive_mode.angle_y_rad,
        fiber_angle_rad=fiber_mode.angle_y_rad,
        receive_wavefront_radius_m=receive_mode.wavefront_radius_y_m,
        fiber_wavefront_radius_m=fiber_mode.wavefront_radius_y_m,
    )
    overlap = overlap_x * overlap_y
    raw_efficiency = float(abs(overlap) ** 2)
    if not math.isfinite(raw_efficiency):
        raise ValueError("Gaussian mode overlap 계산 결과가 유한하지 않습니다.")
    # Cauchy-Schwarz guarantees [0, 1]; clamp only floating-point roundoff.
    if raw_efficiency > 1.0 + 1e-12:
        raise ValueError("정규화 Gaussian overlap이 물리적 상한 1을 초과했습니다.")
    efficiency = min(max(raw_efficiency, 0.0), 1.0)
    coupled_power = power * efficiency
    coupled_field = None if input_field is None else input_field * overlap

    assumptions = (
        "두 mode는 같은 평가면과 같은 local x/y frame의 정규화 scalar Gaussian field입니다.",
        "mode radius는 Gaussian 1/e^2 intensity radius이며 MFD의 절반입니다.",
        "available_power_at_fiber_plane_w는 선언된 deterministic Gaussian receive_mode가 운반하는 power로 해석합니다.",
        "Angular mismatch는 paraxial linear phase k*theta*x로 모델링합니다.",
        "Wavefront radius None은 평가면의 planar wavefront를 뜻하며 polarization overlap은 1로 둡니다.",
        "Input power는 이미 fiber plane에 도달한 별도 ledger 값이며 aperture clipping, aberration과 transmission은 이 함수 밖에서 계산합니다.",
        "Normalized overlap의 complex phase는 fiber-centered transverse phase gauge를 사용하며 절대 optical phase가 아닙니다.",
    )
    warnings = [
        "Lambertian 또는 rough target 반환광은 일반적으로 하나의 deterministic Gaussian mode가 아닙니다. Radiometric return 전체를 완전한 Gaussian으로 간주하지 말고 reciprocity/mode decomposition으로 얻은 mode 성분에만 이 overlap을 적용해야 합니다."
    ]
    if input_field is None:
        warnings.append(
            "Coherent input field가 제공되지 않아 coupled complex field를 계산하지 않았습니다. "
            "Radiometric power에 임의의 zero phase를 부여해 coherent FMCW field로 전달하면 안 됩니다."
        )
    else:
        warnings.append(
            "Coupled complex field는 caller가 제공한 coherent phase reference와 이 함수의 "
            "fiber-centered phase gauge에만 유효합니다. 서로 다른 phase reference의 field를 직접 합산하면 안 됩니다."
        )
    if max(
        abs(receive_mode.angle_x_rad - fiber_mode.angle_x_rad),
        abs(receive_mode.angle_y_rad - fiber_mode.angle_y_rad),
    ) > 0.1:
        warnings.append(
            "Angular mismatch가 0.1 rad를 초과하여 paraxial linear-phase 근사의 유효성을 별도로 검증해야 합니다."
        )

    return FiberCouplingResult(
        model="normalized_scalar_gaussian_overlap",
        model_scope="deterministic_gaussian_to_gaussian_only",
        input_power_interpretation=(
            "power_carried_by_declared_deterministic_gaussian_receive_mode"
        ),
        wavelength_m=wavelength,
        receive_mode=receive_mode,
        fiber_mode=fiber_mode,
        available_power_at_fiber_plane_w=power,
        normalized_field_overlap=overlap,
        input_field_amplitude_sqrt_w=input_field,
        coupled_field_amplitude_sqrt_w=coupled_field,
        coherent_field_status=(
            "not_provided" if input_field is None else "evaluated"
        ),
        fiber_coupling_efficiency=efficiency,
        power_coupled_into_fiber_w=coupled_power,
        status="zero_available_power" if power == 0.0 else "pass",
        assumptions=assumptions,
        warnings=tuple(warnings),
    )
