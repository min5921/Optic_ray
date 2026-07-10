"""Ideal scanner line-path sampling built on static scanner angle sweeps."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from lidarsim.config.loader import ResolvedProject
from lidarsim.scanner.sweep import ScannerSweepSample, run_static_scanner_angle_sweep


@dataclass(frozen=True, slots=True)
class ScannerPathSample:
    """One ideal scanner line-path sample."""

    sample_index: int
    time_s: float
    line_position: float
    sweep_sample: ScannerSweepSample

    @property
    def command_angle_rad(self) -> float:
        return self.sweep_sample.command_angle_rad

    @property
    def command_angle_deg(self) -> float:
        return self.sweep_sample.command_angle_deg

    def to_dict(self) -> dict[str, Any]:
        data = self.sweep_sample.to_dict()
        data.update(
            {
                "time_s": self.time_s,
                "line_position": self.line_position,
            }
        )
        return data


@dataclass(frozen=True, slots=True)
class ScannerPathResult:
    """One ideal forward-line scanner path report."""

    project_id: str
    scenario_id: str
    base_config_hash: str
    scanner_element_id: str
    waveform: str
    sample_count: int
    line_duration_s: float
    frequency_hz: float
    mechanical_amplitude_rad: float
    samples: tuple[ScannerPathSample, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        hit_count = sum(1 for sample in self.samples if sample.sweep_sample.target_hit)
        positive_return_count = sum(
            1 for sample in self.samples if sample.sweep_sample.estimated_received_power_w > 0.0
        )
        received = [sample.sweep_sample.estimated_received_power_w for sample in self.samples]
        return {
            "schema_version": 1,
            "report_type": "phase3_ideal_scanner_line_path",
            "project_id": self.project_id,
            "scenario_id": self.scenario_id,
            "base_config_hash": self.base_config_hash,
            "scanner_element_id": self.scanner_element_id,
            "waveform": self.waveform,
            "sample_count": self.sample_count,
            "line_duration_s": self.line_duration_s,
            "frequency_hz": self.frequency_hz,
            "mechanical_amplitude_rad": self.mechanical_amplitude_rad,
            "mechanical_amplitude_deg": math.degrees(self.mechanical_amplitude_rad),
            "summary": {
                "target_hit_count": hit_count,
                "positive_return_count": positive_return_count,
                "max_estimated_received_power_w": max(received, default=0.0),
                "min_estimated_received_power_w": min(received, default=0.0),
                "model_scope": "ideal_forward_line_command_path",
            },
            "samples": [sample.to_dict() for sample in self.samples],
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def _line_positions(sample_count: int) -> tuple[float, ...]:
    if sample_count < 1:
        raise ValueError("scanner path sample_count는 1 이상이어야 합니다.")
    if sample_count == 1:
        return (0.0,)
    return tuple(float(value) for value in np.linspace(0.0, 1.0, sample_count))


def _scanner_config(project: ResolvedProject) -> dict[str, Any]:
    scanner = dict(project.active_scenario["scanner"])
    amplitude = float(scanner.get("mechanical_amplitude_rad", 0.0))
    frequency = float(scanner.get("frequency_hz", 0.0))
    waveform = str(scanner.get("waveform", ""))
    if not math.isfinite(amplitude) or amplitude < 0.0:
        raise ValueError("scanner.mechanical_amplitude_rad는 0 이상 유한한 값이어야 합니다.")
    if not math.isfinite(frequency) or frequency < 0.0:
        raise ValueError("scanner.frequency_hz는 0 이상 유한한 값이어야 합니다.")
    if waveform != "static" and frequency <= 0.0:
        raise ValueError("Moving scanner의 scanner.frequency_hz는 0보다 커야 합니다.")
    scanner["mechanical_amplitude_rad"] = amplitude
    scanner["frequency_hz"] = frequency
    return scanner


def ideal_forward_line_command_angles(
    project: ResolvedProject,
    *,
    sample_count: int | None = None,
) -> tuple[tuple[float, ...], float, str]:
    """Return command angles for one ideal forward scanner line."""

    scanner = _scanner_config(project)
    count = int(sample_count if sample_count is not None else scanner["samples_per_line"])
    positions = _line_positions(count)
    amplitude = float(scanner["mechanical_amplitude_rad"])
    waveform = str(scanner["waveform"])
    frequency = float(scanner["frequency_hz"])

    if waveform == "static":
        command = float(scanner.get("static_command_angle_rad", 0.0))
        # A static scanner has no line duration or distinct time samples. Emit
        # one pose even when samples_per_line was configured for moving modes.
        return (command,), 0.0, waveform
    if waveform == "triangle":
        return tuple(-amplitude + 2.0 * amplitude * position for position in positions), 0.5 / frequency, waveform
    if waveform == "sinusoidal":
        return (
            tuple(
                amplitude * math.sin(-0.5 * math.pi + math.pi * position)
                for position in positions
            ),
            0.5 / frequency,
            waveform,
        )
    raise ValueError(
        f"지원하지 않는 ideal scanner path waveform입니다: {waveform!r}. "
        "현재 scanner-path는 static, triangle, sinusoidal만 지원합니다."
    )


def run_ideal_scanner_line_path(
    project: ResolvedProject,
    *,
    sample_count: int | None = None,
) -> ScannerPathResult:
    """Run one ideal forward-line scanner path using Phase 2 static samples."""

    scanner = _scanner_config(project)
    command_angles, duration_s, waveform = ideal_forward_line_command_angles(
        project,
        sample_count=sample_count,
    )
    positions = _line_positions(len(command_angles))
    times = (
        (0.0,)
        if len(command_angles) == 1
        else tuple(float(value) for value in np.linspace(0.0, duration_s, len(command_angles)))
    )
    sweep = run_static_scanner_angle_sweep(project, command_angles)
    samples = tuple(
        ScannerPathSample(
            sample_index=index,
            time_s=times[index],
            line_position=positions[index],
            sweep_sample=sweep_sample,
        )
        for index, sweep_sample in enumerate(sweep.samples)
    )
    waveform_assumption = {
        "static": "static waveform은 0 Hz의 단일 command pose로 저장합니다.",
        "triangle": "triangle waveform은 -amplitude에서 +amplitude로 이동하는 half-period line으로 근사합니다.",
        "sinusoidal": "sinusoidal waveform은 sin phase -π/2에서 +π/2까지의 forward half-cycle로 근사합니다.",
    }[waveform]
    return ScannerPathResult(
        project_id=str(project.project["project_id"]),
        scenario_id=str(project.active_scenario["scenario_id"]),
        base_config_hash=project.config_hash,
        scanner_element_id=str(scanner["element_id"]),
        waveform=waveform,
        sample_count=len(samples),
        line_duration_s=duration_s,
        frequency_hz=float(scanner["frequency_hz"]),
        mechanical_amplitude_rad=float(scanner["mechanical_amplitude_rad"]),
        samples=samples,
        assumptions=(
            "Moving waveform은 한 줄의 ideal forward scanner command path만 샘플링합니다.",
            waveform_assumption,
            "각 time sample의 optical/target/receiver 값은 Phase 2 static scanner angle reference run을 재사용합니다.",
        ),
        warnings=(
            "Motor/galvo dynamics, lag, jitter, acceleration limit, bidirectional return stroke와 calibration table은 아직 계산하지 않습니다.",
            "이 결과는 ideal command path reference이며 calibrated hardware scan path가 아닙니다.",
        ),
    )


def write_scanner_path_csv(result: ScannerPathResult, output_path: Path) -> Path:
    """Write a compact ideal scanner path table."""

    path = output_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_index",
                "time_s",
                "line_position",
                "command_angle_deg",
                "command_angle_rad",
                "sample_status",
                "target_hit",
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
            sweep = sample.sweep_sample
            hit = sweep.hit_center_m
            local = sweep.target_local_coordinates_m
            writer.writerow(
                {
                    "sample_index": sample.sample_index,
                    "time_s": sample.time_s,
                    "line_position": sample.line_position,
                    "command_angle_deg": sweep.command_angle_deg,
                    "command_angle_rad": sweep.command_angle_rad,
                    "sample_status": sweep.sample_status,
                    "target_hit": sweep.target_hit,
                    "hit_x_m": None if hit is None else hit[0],
                    "hit_y_m": None if hit is None else hit[1],
                    "hit_z_m": None if hit is None else hit[2],
                    "target_local_u_m": None if local is None else local[0],
                    "target_local_v_m": None if local is None else local[1],
                    "estimated_power_on_target_w": sweep.estimated_power_on_target_w,
                    "estimated_received_power_w": sweep.estimated_received_power_w,
                    "link_loss_db": sweep.link_loss_db,
                    "receiver_fov_status": sweep.receiver_fov_status,
                }
            )
    return path
