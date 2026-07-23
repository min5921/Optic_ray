"""측정 근거에 기반한 공통 accuracy/readiness 판정."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lidarsim.config.immutable import deep_thaw


@dataclass(frozen=True, slots=True)
class ReadinessAssessment:
    """Report 전 단계가 공유하는 hardware readiness 판정."""

    model_purpose: str
    accuracy_mode: str
    confidence_level: str
    hardware_readiness: str
    calibration_status: str
    calibration_evidence: dict[str, Any] | None
    warnings: tuple[str, ...]


def _measurement_role(project: Any, identifier: str) -> str | None:
    assets = getattr(project, "assets", None)
    measurements = getattr(assets, "measurements", {})
    record = measurements.get(identifier) if hasattr(measurements, "get") else None
    if record is None:
        return None
    return str(record.data.get("dataset_role", ""))


def _calibration_problems(project: Any) -> list[str]:
    scenario = project.active_scenario
    evidence = scenario.get("calibration_evidence")
    problems: list[str] = []
    if not isinstance(evidence, Mapping):
        return ["calibrated_hardware에는 calibration_evidence가 필요합니다."]

    fitted = evidence.get("fitted_parameter_set")
    if not isinstance(fitted, Mapping) or not all(
        fitted.get(field) for field in ("id", "file", "sha256")
    ):
        problems.append(
            "검증된 fitted_parameter_set(id, file, sha256)가 필요합니다."
        )

    calibration_ids = tuple(str(value) for value in evidence.get("calibration_measurement_ids", ()))
    validation_ids = tuple(str(value) for value in evidence.get("validation_measurement_ids", ()))
    if not calibration_ids:
        problems.append("calibration measurement dataset이 최소 하나 필요합니다.")
    if not validation_ids:
        problems.append("독립 validation measurement dataset이 최소 하나 필요합니다.")
    overlap = sorted(set(calibration_ids) & set(validation_ids))
    if overlap:
        problems.append(
            "Calibration과 validation dataset은 독립적이어야 합니다: "
            + ", ".join(overlap)
        )
    for identifier in calibration_ids:
        role = _measurement_role(project, identifier)
        if role != "calibration":
            problems.append(
                f"{identifier!r}의 dataset_role은 calibration이어야 합니다(현재 {role!r})."
            )
    for identifier in validation_ids:
        role = _measurement_role(project, identifier)
        if role != "validation":
            problems.append(
                f"{identifier!r}의 dataset_role은 validation이어야 합니다(현재 {role!r})."
            )

    validity = evidence.get("validity")
    wavelength_range = (
        validity.get("wavelength_range_m")
        if isinstance(validity, Mapping)
        else None
    )
    if not isinstance(wavelength_range, (list, tuple)) or len(wavelength_range) != 2:
        problems.append("calibration validity.wavelength_range_m 두 값이 필요합니다.")
    else:
        lower, upper = (float(value) for value in wavelength_range)
        wavelength = float(scenario["source"]["wavelength_m"])
        if not all(math.isfinite(value) for value in (lower, upper)) or lower <= 0.0:
            problems.append("Calibration wavelength validity는 양의 유한한 범위여야 합니다.")
        elif lower > upper:
            problems.append("Calibration wavelength validity의 최솟값이 최댓값보다 큽니다.")
        elif not lower <= wavelength <= upper:
            problems.append(
                f"Scenario wavelength {wavelength:.9g} m가 calibration validity "
                f"[{lower:.9g}, {upper:.9g}] m 밖에 있습니다."
            )

    if str(scenario["simulation"]["accuracy_mode"]) != "absolute_radiometric":
        problems.append(
            "calibrated_hardware에는 simulation.accuracy_mode=absolute_radiometric가 필요합니다."
        )
    if str(scenario["receiver"]["model_level"]) != "calibrated":
        problems.append(
            "calibrated_hardware에는 receiver.model_level=calibrated가 필요합니다."
        )
    return problems


def assess_readiness(project: Any) -> ReadinessAssessment:
    """사용자 label이 아니라 검증된 evidence로 readiness를 결정한다."""

    scenario = project.active_scenario
    purpose = str(scenario["model_purpose"])
    mode = str(scenario["simulation"]["accuracy_mode"])
    evidence = scenario.get("calibration_evidence")

    if purpose == "analytical_regression":
        return ReadinessAssessment(
            model_purpose=purpose,
            accuracy_mode=mode,
            confidence_level="comparative",
            hardware_readiness="analytical_only",
            calibration_status="uncalibrated",
            calibration_evidence=None,
            warnings=(),
        )
    if purpose == "bench_template":
        return ReadinessAssessment(
            model_purpose=purpose,
            accuracy_mode=mode,
            confidence_level="engineering_estimate",
            hardware_readiness="bench_template",
            calibration_status="uncalibrated",
            calibration_evidence=None,
            warnings=(),
        )

    problems = _calibration_problems(project)
    if problems:
        return ReadinessAssessment(
            model_purpose=purpose,
            accuracy_mode=mode,
            confidence_level="engineering_estimate",
            hardware_readiness="bench_template",
            calibration_status="uncalibrated",
            calibration_evidence=(
                deep_thaw(evidence) if isinstance(evidence, Mapping) else None
            ),
            warnings=tuple(
                f"Calibrated readiness를 선언할 수 없습니다: {problem}"
                for problem in problems
            ),
        )
    return ReadinessAssessment(
        model_purpose=purpose,
        accuracy_mode=mode,
        confidence_level="calibrated",
        hardware_readiness="calibrated",
        calibration_status="calibrated",
        calibration_evidence=deep_thaw(evidence),
        warnings=(),
    )
