"""Static scanner command-angle sweep reference runner."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Sequence

import numpy as np

from lidarsim.config.immutable import canonical_hash, deep_freeze, deep_thaw
from lidarsim.config.loader import ResolvedProject
from lidarsim.results import Phase2OpticalTrainReport, build_phase2_optical_train_report


def _finite_angle(value: float, *, index: int) -> float:
    angle = float(value)
    if not math.isfinite(angle):
        raise ValueError(f"scanner sweep angle[{index}]는 유한한 radian 값이어야 합니다.")
    return angle


def _tuple3(value: Any | None) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if len(value) != 3:
        return None
    return tuple(float(item) for item in value)


def _tuple2(value: Any | None) -> tuple[float, float] | None:
    if value is None:
        return None
    if len(value) != 2:
        return None
    return tuple(float(item) for item in value)


@dataclass(frozen=True, slots=True)
class ScannerSweepSample:
    """One static scanner command-angle sample."""

    sample_index: int
    command_angle_rad: float
    command_angle_deg: float
    scenario_config_hash: str
    final_direction: tuple[float, float, float]
    mirror_normal_world: tuple[float, float, float] | None
    reflected_direction: tuple[float, float, float] | None
    target_id: str | None
    target_hit: bool
    target_miss_reason: str | None
    hit_center_m: tuple[float, float, float] | None
    target_local_coordinates_m: tuple[float, float] | None
    target_incidence_angle_rad: float | None
    estimated_power_on_target_w: float
    estimated_received_power_w: float
    link_loss_db: float | None
    receiver_fov_status: str | None
    receiver_distance_m: float | None
    overall_status: str
    target_footprint_status: str
    receiver_return_status: str
    sample_status: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_index": self.sample_index,
            "command_angle_rad": self.command_angle_rad,
            "command_angle_deg": self.command_angle_deg,
            "scenario_config_hash": self.scenario_config_hash,
            "final_direction": list(self.final_direction),
            "mirror_normal_world": (
                None if self.mirror_normal_world is None else list(self.mirror_normal_world)
            ),
            "reflected_direction": (
                None if self.reflected_direction is None else list(self.reflected_direction)
            ),
            "target_id": self.target_id,
            "target_hit": self.target_hit,
            "target_miss_reason": self.target_miss_reason,
            "hit_center_m": None if self.hit_center_m is None else list(self.hit_center_m),
            "target_local_coordinates_m": (
                None
                if self.target_local_coordinates_m is None
                else list(self.target_local_coordinates_m)
            ),
            "target_incidence_angle_rad": self.target_incidence_angle_rad,
            "estimated_power_on_target_w": self.estimated_power_on_target_w,
            "estimated_received_power_w": self.estimated_received_power_w,
            "link_loss_db": self.link_loss_db,
            "receiver_fov_status": self.receiver_fov_status,
            "receiver_distance_m": self.receiver_distance_m,
            "overall_status": self.overall_status,
            "target_footprint_status": self.target_footprint_status,
            "receiver_return_status": self.receiver_return_status,
            "sample_status": self.sample_status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ScannerSweepResult:
    """Static command-angle sweep report."""

    project_id: str
    scenario_id: str
    base_config_hash: str
    scanner_element_id: str
    angle_count: int
    samples: tuple[ScannerSweepSample, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        hit_count = sum(1 for sample in self.samples if sample.target_hit)
        positive_return_count = sum(
            1 for sample in self.samples if sample.estimated_received_power_w > 0.0
        )
        powers = [sample.estimated_received_power_w for sample in self.samples]
        best_sample = (
            max(self.samples, key=lambda sample: sample.estimated_received_power_w)
            if self.samples
            else None
        )
        return {
            "schema_version": 1,
            "report_type": "phase3_static_scanner_angle_sweep",
            "project_id": self.project_id,
            "scenario_id": self.scenario_id,
            "base_config_hash": self.base_config_hash,
            "scanner_element_id": self.scanner_element_id,
            "angle_unit": "rad",
            "angle_count": self.angle_count,
            "summary": {
                "sample_count": len(self.samples),
                "target_hit_count": hit_count,
                "positive_return_count": positive_return_count,
                "max_estimated_received_power_w": max(powers, default=0.0),
                "best_command_angle_rad": (
                    None if best_sample is None else best_sample.command_angle_rad
                ),
                "best_command_angle_deg": (
                    None if best_sample is None else best_sample.command_angle_deg
                ),
            },
            "samples": [sample.to_dict() for sample in self.samples],
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def default_static_sweep_angles(project: ResolvedProject, *, count: int = 11) -> tuple[float, ...]:
    """Return evenly spaced static scanner angles across the configured mechanical amplitude."""

    sample_count = int(count)
    if sample_count < 1:
        raise ValueError("scanner sweep count는 1 이상이어야 합니다.")
    amplitude = float(project.active_scenario["scanner"].get("mechanical_amplitude_rad", 0.0))
    if not math.isfinite(amplitude) or amplitude < 0.0:
        raise ValueError("scanner.mechanical_amplitude_rad는 0 이상 유한한 값이어야 합니다.")
    if sample_count == 1 or amplitude <= 0.0:
        return (0.0,)
    return tuple(float(value) for value in np.linspace(-amplitude, amplitude, sample_count))


def _project_with_static_angle(project: ResolvedProject, command_angle_rad: float) -> ResolvedProject:
    scenario_id = str(project.project["active_baseline"])
    scenario = deep_thaw(project.active_scenario)
    scenario["scanner"]["static_command_angle_rad"] = float(command_angle_rad)
    scenario_hash = canonical_hash(
        {
            "base_config_hash": project.config_hash,
            "scenario_id": scenario_id,
            "scanner_static_command_angle_rad": float(command_angle_rad),
        }
    )
    scenarios = dict(project.scenarios)
    scenarios[scenario_id] = deep_freeze(scenario)
    return replace(
        project,
        scenarios=MappingProxyType(scenarios),
        config_hash=scenario_hash,
    )


def _sample_status(
    *,
    target_hit: bool,
    receiver_fov_status: str | None,
    estimated_received_power_w: float,
) -> str:
    if not target_hit:
        return "target_miss"
    if receiver_fov_status == "outside_fov":
        return "outside_receiver_fov"
    if estimated_received_power_w > 0.0:
        return "positive_return"
    return "zero_return"


def _sample_from_report(
    *,
    sample_index: int,
    command_angle_rad: float,
    variant_project: ResolvedProject,
    report: Phase2OpticalTrainReport,
) -> ScannerSweepSample:
    summary = report.summary
    train = report.optical_train
    final_state = train["states"][-1]["beam_state"]
    mirror_report = next(
        (
            item
            for item in train["component_reports"]
            if item.get("component_type") == "scanner_mirror"
        ),
        {},
    )
    footprint = report.target_footprints[0] if report.target_footprints else {}
    returns = report.receiver_return.get("returns", ())
    receiver_return = returns[0] if returns else {}
    target_hit = bool(footprint.get("hit", False))
    received_power = float(summary["estimated_received_power_w"])
    receiver_fov_status = receiver_return.get("receiver_fov_status")
    warnings = list(report.accuracy["warnings"])
    for item in footprint.get("warnings", ()):
        if item not in warnings:
            warnings.append(str(item))
    for item in receiver_return.get("warnings", ()):
        if item not in warnings:
            warnings.append(str(item))

    return ScannerSweepSample(
        sample_index=sample_index,
        command_angle_rad=float(command_angle_rad),
        command_angle_deg=math.degrees(float(command_angle_rad)),
        scenario_config_hash=variant_project.config_hash,
        final_direction=_tuple3(final_state["direction"]) or (0.0, 0.0, 0.0),
        mirror_normal_world=_tuple3(mirror_report.get("surface_normal_world")),
        reflected_direction=_tuple3(mirror_report.get("reflected_direction")),
        target_id=footprint.get("target_id"),
        target_hit=target_hit,
        target_miss_reason=footprint.get("miss_reason"),
        hit_center_m=_tuple3(footprint.get("hit_center_m")),
        target_local_coordinates_m=_tuple2(footprint.get("local_coordinates_m")),
        target_incidence_angle_rad=(
            None
            if footprint.get("incidence_angle_rad") is None
            else float(footprint["incidence_angle_rad"])
        ),
        estimated_power_on_target_w=float(summary["estimated_power_on_target_w"]),
        estimated_received_power_w=received_power,
        link_loss_db=(
            None if summary["link_loss_db"] is None else float(summary["link_loss_db"])
        ),
        receiver_fov_status=None if receiver_fov_status is None else str(receiver_fov_status),
        receiver_distance_m=(
            None
            if receiver_return.get("receiver_distance_m") is None
            else float(receiver_return["receiver_distance_m"])
        ),
        overall_status=str(summary["overall_status"]),
        target_footprint_status=str(summary["target_footprint_status"]),
        receiver_return_status=str(summary["receiver_return_status"]),
        sample_status=_sample_status(
            target_hit=target_hit,
            receiver_fov_status=None if receiver_fov_status is None else str(receiver_fov_status),
            estimated_received_power_w=received_power,
        ),
        warnings=tuple(warnings),
    )


def run_static_scanner_angle_sweep(
    project: ResolvedProject,
    command_angles_rad: Sequence[float],
) -> ScannerSweepResult:
    """Run independent Phase 2 reports for multiple static scanner command angles."""

    angles = tuple(_finite_angle(value, index=index) for index, value in enumerate(command_angles_rad))
    if not angles:
        raise ValueError("scanner sweep에는 최소 1개의 command angle이 필요합니다.")
    samples: list[ScannerSweepSample] = []
    for index, angle in enumerate(angles):
        variant_project = _project_with_static_angle(project, angle)
        report = build_phase2_optical_train_report(variant_project)
        samples.append(
            _sample_from_report(
                sample_index=index,
                command_angle_rad=angle,
                variant_project=variant_project,
                report=report,
            )
        )

    return ScannerSweepResult(
        project_id=str(project.project["project_id"]),
        scenario_id=str(project.active_scenario["scenario_id"]),
        base_config_hash=project.config_hash,
        scanner_element_id=str(project.active_scenario["scanner"]["element_id"]),
        angle_count=len(angles),
        samples=tuple(samples),
        assumptions=(
            "각 command angle은 독립 static scanner pose로 계산합니다.",
            "Mirror mechanical command angle의 optical deflection은 flat mirror reflection 법칙에 의해 약 2배로 나타납니다.",
            "Scanner waveform, time sampling, motor lag, jitter, acceleration과 calibration table은 아직 계산하지 않습니다.",
            "각 sample의 target footprint와 receiver return은 기존 Phase 2 analytical reference model을 재사용합니다.",
        ),
        warnings=(
            "이 sweep은 scanner time dynamics가 아니라 static command angle 비교 helper입니다.",
            "결과는 analytical/reference이며 calibrated hardware prediction으로 표시하지 않습니다.",
        ),
    )


def write_scanner_sweep_csv(result: ScannerSweepResult, output_path: Path) -> Path:
    """Write a compact scanner sweep table for spreadsheet inspection."""

    path = output_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_index",
                "command_angle_deg",
                "command_angle_rad",
                "sample_status",
                "target_hit",
                "target_miss_reason",
                "hit_x_m",
                "hit_y_m",
                "hit_z_m",
                "target_local_u_m",
                "target_local_v_m",
                "estimated_power_on_target_w",
                "estimated_received_power_w",
                "link_loss_db",
                "receiver_fov_status",
            ],
        )
        writer.writeheader()
        for sample in result.samples:
            hit = sample.hit_center_m
            local = sample.target_local_coordinates_m
            writer.writerow(
                {
                    "sample_index": sample.sample_index,
                    "command_angle_deg": sample.command_angle_deg,
                    "command_angle_rad": sample.command_angle_rad,
                    "sample_status": sample.sample_status,
                    "target_hit": sample.target_hit,
                    "target_miss_reason": sample.target_miss_reason,
                    "hit_x_m": None if hit is None else hit[0],
                    "hit_y_m": None if hit is None else hit[1],
                    "hit_z_m": None if hit is None else hit[2],
                    "target_local_u_m": None if local is None else local[0],
                    "target_local_v_m": None if local is None else local[1],
                    "estimated_power_on_target_w": sample.estimated_power_on_target_w,
                    "estimated_received_power_w": sample.estimated_received_power_w,
                    "link_loss_db": sample.link_loss_db,
                    "receiver_fov_status": sample.receiver_fov_status,
                }
            )
    return path
