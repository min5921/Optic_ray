"""Phase 2.4-R4 duplexer and detector-input optical boundary.

This module terminates the reciprocal optical-power path at the detector input
plane.  It does not model a detector response.  Power and optional coherent
field amplitude remain separate physical quantities: a passive duplexer power
transmission ``T`` scales power by ``T`` and field amplitude by ``sqrt(T)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


_SUPPORTED_DUPLEXER_TYPES = frozenset(
    {
        "ideal_circulator",
        "fiber_coupler",
        "free_space_beamsplitter",
    }
)


def _nonnegative(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name}은 0 이상의 유한한 값이어야 합니다.")
    return result


def _positive(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name}은 0보다 큰 유한한 값이어야 합니다.")
    return result


def _fraction(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name}은 0 이상 1 이하의 유한한 값이어야 합니다.")
    return result


def _nonempty(value: str, *, name: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{name}은 빈 문자열이어서는 안 됩니다.")
    return result


def _field_amplitude(value: complex, *, name: str) -> complex:
    result = complex(value)
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise ValueError(f"{name}의 실수부와 허수부는 유한해야 합니다.")
    return result


def _complex_dict(value: complex | None) -> dict[str, float] | None:
    if value is None:
        return None
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "magnitude_sqrt_w": float(abs(value)),
        "power_w": float(abs(value) ** 2),
    }


def _link_loss_db(reference_power_w: float | None, output_power_w: float) -> float | None:
    if reference_power_w is None or reference_power_w <= 0.0 or output_power_w <= 0.0:
        return None
    loss = -10.0 * math.log10(output_power_w / reference_power_w)
    return 0.0 if abs(loss) <= 1.0e-15 else loss


@dataclass(frozen=True, slots=True)
class DetectorBoundaryPowerLedgerEntry:
    """One passive power transition from the fiber to detector input plane."""

    input_power_w: float
    loss_w: float
    output_power_w: float
    transmission_fraction: float
    mechanism: str
    input_plane: str
    output_plane: str
    model_source: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_power_w": self.input_power_w,
            "loss_w": self.loss_w,
            "output_power_w": self.output_power_w,
            "transmission_fraction": self.transmission_fraction,
            "mechanism": self.mechanism,
            "input_plane": self.input_plane,
            "output_plane": self.output_plane,
            "model_source": self.model_source,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class DetectorInputBoundaryResult:
    """Optical quantities at a detector input, before detector physics."""

    model: str
    status: str
    duplexer_type: str
    detector_model: str
    return_power_transmission: float
    power_on_target_w: float | None
    power_coupled_into_fiber_w: float
    power_lost_in_duplexer_w: float
    power_at_detector_input_w: float
    fiber_coupled_to_detector_input_link_loss_db: float | None
    target_to_detector_input_link_loss_db: float | None
    field_at_fiber_output_sqrt_w: complex | None
    field_at_detector_input_sqrt_w: complex | None
    power_ledger: tuple[DetectorBoundaryPowerLedgerEntry, ...]
    maximum_energy_residual_w: float
    energy_tolerance_w: float
    energy_check_status: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "status": self.status,
            "duplexer_type": self.duplexer_type,
            "detector_model": self.detector_model,
            "return_power_transmission": self.return_power_transmission,
            "power_on_target_w": self.power_on_target_w,
            "power_coupled_into_fiber_w": self.power_coupled_into_fiber_w,
            "power_lost_in_duplexer_w": self.power_lost_in_duplexer_w,
            "power_at_detector_input_w": self.power_at_detector_input_w,
            "fiber_coupled_to_detector_input_link_loss_db": (
                self.fiber_coupled_to_detector_input_link_loss_db
            ),
            "target_to_detector_input_link_loss_db": (
                self.target_to_detector_input_link_loss_db
            ),
            "field_at_fiber_output_sqrt_w": _complex_dict(
                self.field_at_fiber_output_sqrt_w
            ),
            "field_at_detector_input_sqrt_w": _complex_dict(
                self.field_at_detector_input_sqrt_w
            ),
            "power_ledger": [entry.to_dict() for entry in self.power_ledger],
            "maximum_energy_residual_w": self.maximum_energy_residual_w,
            "energy_tolerance_w": self.energy_tolerance_w,
            "energy_check_status": self.energy_check_status,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def apply_duplexer_detector_boundary(
    *,
    power_coupled_into_fiber_w: float,
    return_power_transmission: float,
    duplexer_type: str = "ideal_circulator",
    power_on_target_w: float | None = None,
    field_at_fiber_output_sqrt_w: complex | None = None,
    detector_model: str = "none",
    model_source: str = "receiver.duplexer.return_power_transmission",
    energy_tolerance_w: float = 1.0e-15,
) -> DetectorInputBoundaryResult:
    """Apply a passive duplexer and expose the detector-input optical boundary.

    ``power_coupled_into_fiber_w`` is the scalar optical power delivered by the
    preceding fiber-coupling stage.  ``field_at_fiber_output_sqrt_w`` is
    optional and, when provided, must use units sqrt(W) and satisfy
    ``abs(field)**2 == power`` within a strict relative numerical check.  For
    exactly zero input power, only the exact complex value ``0j`` is accepted;
    no absolute tolerance may turn a nonzero field into zero power.

    The detector itself is deliberately not evaluated.  Photocurrent,
    responsivity, saturation, noise, coherent mixing, beat signals and spectral
    processing belong to later stages.
    """

    input_power = _nonnegative(
        power_coupled_into_fiber_w,
        name="power_coupled_into_fiber_w",
    )
    transmission = _fraction(
        return_power_transmission,
        name="return_power_transmission",
    )
    resolved_duplexer_type = _nonempty(duplexer_type, name="duplexer_type")
    if resolved_duplexer_type not in _SUPPORTED_DUPLEXER_TYPES:
        allowed = ", ".join(sorted(_SUPPORTED_DUPLEXER_TYPES))
        raise ValueError(f"duplexer_type은 다음 중 하나여야 합니다: {allowed}.")
    resolved_detector_model = _nonempty(detector_model, name="detector_model")
    resolved_model_source = _nonempty(model_source, name="model_source")
    tolerance = _positive(energy_tolerance_w, name="energy_tolerance_w")

    target_power = (
        None
        if power_on_target_w is None
        else _nonnegative(power_on_target_w, name="power_on_target_w")
    )
    if target_power is not None:
        exceeds_target = (
            input_power > 0.0
            if target_power == 0.0
            else input_power > target_power + tolerance
        )
        if exceeds_target:
            raise ValueError(
                "수동 왕복 경로에서 power_coupled_into_fiber_w는 "
                "power_on_target_w를 초과할 수 없습니다."
            )

    input_field = (
        None
        if field_at_fiber_output_sqrt_w is None
        else _field_amplitude(
            field_at_fiber_output_sqrt_w,
            name="field_at_fiber_output_sqrt_w",
        )
    )
    if input_field is not None:
        field_power = float(abs(input_field) ** 2)
        field_matches_power = (
            input_field == 0.0j
            if input_power == 0.0
            else math.isclose(
                field_power,
                input_power,
                rel_tol=1.0e-12,
                abs_tol=0.0,
            )
        )
        if not field_matches_power:
            raise ValueError(
                "field_at_fiber_output_sqrt_w는 sqrt(W) 단위여야 하며 "
                "abs(field)**2가 power_coupled_into_fiber_w와 일치해야 합니다."
            )

    output_power = input_power * transmission
    loss_power = input_power - output_power
    output_field = (
        None if input_field is None else input_field * math.sqrt(transmission)
    )
    ledger_status = (
        "zero_input"
        if input_power == 0.0
        else "blocked"
        if transmission == 0.0
        else "applied"
    )
    ledger = (
        DetectorBoundaryPowerLedgerEntry(
            input_power_w=input_power,
            loss_w=loss_power,
            output_power_w=output_power,
            transmission_fraction=transmission,
            mechanism="duplexer_return_transmission",
            input_plane="coupled_fiber_mode",
            output_plane="detector_input_plane",
            model_source=resolved_model_source,
            status=ledger_status,
        ),
    )

    residuals = [abs(input_power - loss_power - output_power)]
    if output_field is not None:
        residuals.append(abs(abs(output_field) ** 2 - output_power))
    maximum_residual = max(residuals)
    energy_status = "pass" if maximum_residual <= tolerance else "fail"

    warnings: list[str] = []
    if input_power == 0.0:
        warnings.append(
            "Fiber-coupled input power가 0 W이므로 유한한 dB link loss를 정의하지 않습니다."
        )
    elif transmission == 0.0:
        warnings.append(
            "Duplexer return transmission이 0이므로 detector 입력은 0 W이며 "
            "유한한 dB link loss를 정의하지 않습니다."
        )
    if target_power is None:
        warnings.append(
            "power_on_target_w가 제공되지 않아 target-to-detector link loss는 보고하지 않습니다."
        )
    elif target_power == 0.0:
        warnings.append(
            "Target reference power가 0 W이므로 target-to-detector dB link loss를 정의하지 않습니다."
        )

    status = (
        "fail"
        if energy_status == "fail"
        else "zero_input"
        if input_power == 0.0
        else "blocked"
        if transmission == 0.0
        else "pass"
    )
    return DetectorInputBoundaryResult(
        model="passive_duplexer_detector_input_boundary",
        status=status,
        duplexer_type=resolved_duplexer_type,
        detector_model=resolved_detector_model,
        return_power_transmission=transmission,
        power_on_target_w=target_power,
        power_coupled_into_fiber_w=input_power,
        power_lost_in_duplexer_w=loss_power,
        power_at_detector_input_w=output_power,
        fiber_coupled_to_detector_input_link_loss_db=_link_loss_db(
            input_power,
            output_power,
        ),
        target_to_detector_input_link_loss_db=_link_loss_db(
            target_power,
            output_power,
        ),
        field_at_fiber_output_sqrt_w=input_field,
        field_at_detector_input_sqrt_w=output_field,
        power_ledger=ledger,
        maximum_energy_residual_w=maximum_residual,
        energy_tolerance_w=tolerance,
        energy_check_status=energy_status,
        assumptions=(
            "Duplexer/circulator는 설정된 scalar return power transmission을 갖는 수동 소자로 모델링합니다.",
            "Power transmission T는 optical power에 T, complex field amplitude에 sqrt(T)로 적용합니다.",
            "Optional complex field의 단위는 sqrt(W)이며 optical power와 별도 물리량으로 유지합니다.",
            "Detector input은 optical boundary일 뿐이며 detector responsivity, photocurrent, saturation과 noise는 계산하지 않습니다.",
            "Coherent mixing, LO path, FMCW beat signal과 FFT/CZT는 계산하지 않습니다.",
        ),
        warnings=tuple(warnings),
    )


__all__ = [
    "DetectorBoundaryPowerLedgerEntry",
    "DetectorInputBoundaryResult",
    "apply_duplexer_detector_boundary",
]
