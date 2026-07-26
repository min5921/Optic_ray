"""Phase 2.4-R4 project adapter for the detector-input optical boundary.

The adapter consumes only the scalar power produced by the R3 fiber-coupling
proxy.  It applies the configured passive duplexer return transmission and
stops at the detector input plane.  Detector response and coherent field
generation are deliberately outside this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .detector_boundary import (
    DetectorBoundaryPowerLedgerEntry,
    DetectorInputBoundaryResult,
    apply_duplexer_detector_boundary,
)
from .fiber_coupling_project import ProjectFiberCoupling
from .reciprocal_project import RECIPROCAL_ARCHITECTURE


MODEL = "passive_duplexer_detector_input_boundary"
MODEL_SCOPE = "analytical_optical_boundary_only"
HARDWARE_READINESS = "uncalibrated"


def _loss_db(reference_power_w: float | None, output_power_w: float) -> float | None:
    if reference_power_w is None or reference_power_w <= 0.0 or output_power_w <= 0.0:
        return None
    loss = -10.0 * math.log10(output_power_w / reference_power_w)
    return 0.0 if abs(loss) <= 1.0e-15 else loss


@dataclass(frozen=True, slots=True)
class ProjectDetectorBoundary:
    """Resolved R4 result and explicit upstream/readiness metadata."""

    status: str
    status_reason: str | None
    detector_model: str | None
    duplexer_type: str | None
    return_power_transmission: float | None
    source_power_w: float
    power_on_target_w: float | None
    result: DetectorInputBoundaryResult | None
    source_to_detector_input_round_trip_link_loss_db: float | None
    coherent_field_status: str
    field_usable_for_coherent_propagation: bool
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def power_at_detector_input_w(self) -> float | None:
        return None if self.result is None else self.result.power_at_detector_input_w

    @property
    def fiber_coupled_to_detector_input_link_loss_db(self) -> float | None:
        if self.result is None:
            return None
        return self.result.fiber_coupled_to_detector_input_link_loss_db

    @property
    def target_to_detector_input_link_loss_db(self) -> float | None:
        if self.result is None:
            return None
        return self.result.target_to_detector_input_link_loss_db

    @property
    def energy_check_status(self) -> str:
        return "not_evaluated" if self.result is None else self.result.energy_check_status

    @property
    def maximum_energy_residual_w(self) -> float | None:
        return None if self.result is None else self.result.maximum_energy_residual_w

    @property
    def energy_tolerance_w(self) -> float | None:
        return None if self.result is None else self.result.energy_tolerance_w

    @property
    def power_ledger(self) -> tuple[DetectorBoundaryPowerLedgerEntry, ...]:
        return () if self.result is None else self.result.power_ledger

    def to_dict(self) -> dict[str, Any]:
        result = self.result
        return {
            "model": MODEL,
            "model_scope": MODEL_SCOPE,
            "hardware_readiness": HARDWARE_READINESS,
            "status": self.status,
            "status_reason": self.status_reason,
            "detector_response_status": "not_evaluated",
            "detector_model": self.detector_model,
            "duplexer_type": self.duplexer_type,
            "return_power_transmission": self.return_power_transmission,
            "source_power_w": self.source_power_w,
            "power_on_target_w": self.power_on_target_w,
            "power_coupled_into_fiber_w": (
                None if result is None else result.power_coupled_into_fiber_w
            ),
            "power_lost_in_duplexer_w": (
                None if result is None else result.power_lost_in_duplexer_w
            ),
            "power_at_detector_input_w": self.power_at_detector_input_w,
            "fiber_coupled_to_detector_input_link_loss_db": (
                self.fiber_coupled_to_detector_input_link_loss_db
            ),
            "target_to_detector_input_link_loss_db": (
                self.target_to_detector_input_link_loss_db
            ),
            "source_to_detector_input_round_trip_link_loss_db": (
                self.source_to_detector_input_round_trip_link_loss_db
            ),
            "field_at_fiber_output_sqrt_w": None,
            "field_at_detector_input_sqrt_w": None,
            "coherent_field_status": self.coherent_field_status,
            "field_usable_for_coherent_propagation": (
                self.field_usable_for_coherent_propagation
            ),
            "power_ledger": [entry.to_dict() for entry in self.power_ledger],
            "maximum_energy_residual_w": self.maximum_energy_residual_w,
            "energy_tolerance_w": self.energy_tolerance_w,
            "energy_check_status": self.energy_check_status,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _not_evaluated(
    *,
    status: str,
    reason: str,
    detector_model: str | None,
    duplexer_type: str | None,
    return_power_transmission: float | None,
    source_power_w: float,
    power_on_target_w: float | None,
    assumptions: tuple[str, ...],
) -> ProjectDetectorBoundary:
    return ProjectDetectorBoundary(
        status=status,
        status_reason=reason,
        detector_model=detector_model,
        duplexer_type=duplexer_type,
        return_power_transmission=return_power_transmission,
        source_power_w=source_power_w,
        power_on_target_w=power_on_target_w,
        result=None,
        source_to_detector_input_round_trip_link_loss_db=None,
        coherent_field_status="not_provided",
        field_usable_for_coherent_propagation=False,
        assumptions=assumptions,
        warnings=(reason,),
    )


def evaluate_project_detector_boundary(
    project: Any,
    fiber_coupling: ProjectFiberCoupling,
    *,
    power_on_target_w: float | None = None,
    energy_tolerance_w: float = 1.0e-15,
) -> ProjectDetectorBoundary:
    """Apply the configured duplexer to the valid R3 scalar coupled power."""

    scenario = project.active_scenario
    receiver = scenario["receiver"]
    detector_model_value = receiver.get("detector_model")
    detector_model = (
        "none" if detector_model_value is None else str(detector_model_value)
    )
    source_power = float(scenario["source"]["optical_power_w"])
    target_power = None if power_on_target_w is None else float(power_on_target_w)
    tolerance = float(energy_tolerance_w)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("energy_tolerance_w는 0보다 큰 유한한 값이어야 합니다.")
    if str(receiver["architecture"]) != RECIPROCAL_ARCHITECTURE:
        return _not_evaluated(
            status="not_evaluated",
            reason="reciprocal_single_mode_fiber architecture가 아니므로 R4 detector-input boundary를 계산하지 않았습니다.",
            detector_model=detector_model,
            duplexer_type=None,
            return_power_transmission=None,
            source_power_w=source_power,
            power_on_target_w=target_power,
            assumptions=(
                "R4는 reciprocal_single_mode_fiber architecture의 passive duplexer detector-input boundary만 지원합니다.",
            ),
        )

    duplexer = receiver["duplexer"]
    duplexer_type = str(duplexer["type"])
    transmission = float(duplexer["return_power_transmission"])

    assumptions = (
        "R4 optical input은 R3 power_coupled_into_fiber_w만 사용합니다.",
        "Duplexer/circulator는 configured scalar return power transmission을 갖는 수동 경계로 모델링합니다.",
        "Source round-trip link loss의 reference power는 resolved scenario source.optical_power_w입니다.",
        "R3 diffuse Lambertian Gaussian alignment proxy의 analytical upper-bound 성격을 그대로 유지합니다.",
        "Radiometric R3가 coherent field를 제공하지 않으므로 R4 input/output field는 null입니다.",
        "Detector input plane까지만 계산하며 responsivity, photocurrent, saturation, noise, coherent mixing과 FFT/CZT는 계산하지 않습니다.",
    )

    if fiber_coupling.status == "fail" or fiber_coupling.energy_check_status == "fail":
        return _not_evaluated(
            status="fail",
            reason="R3 fiber coupling 또는 energy ledger가 fail이므로 R4로 power를 전파하지 않았습니다.",
            detector_model=detector_model,
            duplexer_type=duplexer_type,
            return_power_transmission=transmission,
            source_power_w=source_power,
            power_on_target_w=target_power,
            assumptions=assumptions,
        )
    if fiber_coupling.result is None:
        return _not_evaluated(
            status="not_evaluated",
            reason=(
                "R3 power_coupled_into_fiber_w가 없어 R4 detector-input boundary를 "
                f"계산하지 않았습니다 (R3 status={fiber_coupling.status!r})."
            ),
            detector_model=detector_model,
            duplexer_type=duplexer_type,
            return_power_transmission=transmission,
            source_power_w=source_power,
            power_on_target_w=target_power,
            assumptions=assumptions,
        )
    if fiber_coupling.energy_check_status != "pass":
        return _not_evaluated(
            status="fail",
            reason="R3 fiber coupling energy check가 pass가 아니므로 R4로 power를 전파하지 않았습니다.",
            detector_model=detector_model,
            duplexer_type=duplexer_type,
            return_power_transmission=transmission,
            source_power_w=source_power,
            power_on_target_w=target_power,
            assumptions=assumptions,
        )

    coupled_power = fiber_coupling.result.power_coupled_into_fiber_w
    if coupled_power > source_power:
        return _not_evaluated(
            status="fail",
            reason=(
                "R3 power_coupled_into_fiber_w가 현재 project source.optical_power_w의 "
                "수동 power bound를 초과하므로 서로 다른 project 결과를 R4로 전파하지 않았습니다."
            ),
            detector_model=detector_model,
            duplexer_type=duplexer_type,
            return_power_transmission=transmission,
            source_power_w=source_power,
            power_on_target_w=target_power,
            assumptions=assumptions,
        )

    result = apply_duplexer_detector_boundary(
        power_coupled_into_fiber_w=coupled_power,
        return_power_transmission=transmission,
        duplexer_type=duplexer_type,
        power_on_target_w=target_power,
        field_at_fiber_output_sqrt_w=None,
        detector_model=detector_model,
        model_source="receiver.duplexer.return_power_transmission",
        energy_tolerance_w=tolerance,
    )
    output_power = result.power_at_detector_input_w
    warnings = list(result.warnings)
    warnings.append(
        "R4 detector-input power는 R3 diffuse-return Gaussian alignment proxy에 의존하는 analytical/uncalibrated reference입니다."
    )
    warnings.append(
        "Detector response는 미구현이며 detector_model은 경계 metadata로만 보고합니다."
    )
    return ProjectDetectorBoundary(
        status=result.status,
        status_reason=None,
        detector_model=detector_model,
        duplexer_type=duplexer_type,
        return_power_transmission=transmission,
        source_power_w=source_power,
        power_on_target_w=target_power,
        result=result,
        source_to_detector_input_round_trip_link_loss_db=_loss_db(
            source_power,
            output_power,
        ),
        coherent_field_status="not_provided",
        field_usable_for_coherent_propagation=False,
        assumptions=assumptions,
        warnings=tuple(warnings),
    )


__all__ = [
    "HARDWARE_READINESS",
    "MODEL",
    "MODEL_SCOPE",
    "ProjectDetectorBoundary",
    "evaluate_project_detector_boundary",
]
