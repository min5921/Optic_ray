from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.scanner import (
    ideal_forward_line_command_angles,
    run_ideal_scanner_line_path,
    write_scanner_path_csv,
)
from lidarsim.visualization import render_scanner_path_view


def test_triangle_forward_line_uses_configured_amplitude_and_half_period(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    angles, duration_s, waveform = ideal_forward_line_command_angles(project, sample_count=5)

    assert waveform == "triangle"
    assert duration_s == pytest.approx(0.05)
    assert angles == pytest.approx(
        [
            -math.radians(5.0),
            -math.radians(2.5),
            0.0,
            math.radians(2.5),
            math.radians(5.0),
        ],
        abs=1e-15,
    )


def test_ideal_scanner_line_path_contains_time_hit_and_return(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    result = run_ideal_scanner_line_path(project, sample_count=5)

    assert result.waveform == "triangle"
    assert result.sample_count == 5
    assert result.line_duration_s == pytest.approx(0.05)
    assert [sample.time_s for sample in result.samples] == pytest.approx(
        [0.0, 0.0125, 0.025, 0.0375, 0.05]
    )
    assert all(sample.sweep_sample.target_hit for sample in result.samples)
    assert all(sample.sweep_sample.estimated_received_power_w > 0.0 for sample in result.samples)
    assert result.samples[0].command_angle_deg == pytest.approx(-5.0)
    assert result.samples[-1].command_angle_deg == pytest.approx(5.0)
    assert result.samples[0].sweep_sample.target_local_coordinates_m[1] > 0.0
    assert result.samples[-1].sweep_sample.target_local_coordinates_m[1] < 0.0


def test_sinusoidal_forward_line_samples_half_cycle(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scanner"]["waveform"] = "sinusoidal"
    scenario_path.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    project = load_project(copied_project)

    angles, duration_s, waveform = ideal_forward_line_command_angles(project, sample_count=3)

    assert waveform == "sinusoidal"
    assert duration_s == pytest.approx(0.05)
    assert angles == pytest.approx([-math.radians(5.0), 0.0, math.radians(5.0)], abs=1e-15)


def test_static_scanner_path_accepts_zero_frequency_and_validates_schema(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scanner"].update(
        {
            "type": "static_mirror",
            "waveform": "static",
            "static_command_angle_rad": "2 deg",
            "mechanical_amplitude_rad": "0 deg",
            "frequency_hz": "0 Hz",
        }
    )
    scenario_path.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    project = load_project(copied_project)

    result = run_ideal_scanner_line_path(project, sample_count=3)

    assert result.waveform == "static"
    assert result.sample_count == 1
    assert result.frequency_hz == 0.0
    assert result.line_duration_s == 0.0
    assert [sample.time_s for sample in result.samples] == [0.0]
    assert [sample.command_angle_deg for sample in result.samples] == pytest.approx([2.0])
    assert any("단일 command pose" in item for item in result.assumptions)
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        result.to_dict(),
        "phase3_ideal_scanner_line_path.schema.json",
        source="test static scanner path report",
    )


def test_ideal_scanner_path_serializes_csv_and_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    result = run_ideal_scanner_line_path(project, sample_count=5)
    yaml_path = tmp_path / "scanner_path.yaml"
    csv_path = tmp_path / "scanner_path.csv"
    png_path = tmp_path / "scanner_path.png"

    yaml_path.write_text(
        yaml.safe_dump(result.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    written_csv = write_scanner_path_csv(result, csv_path)
    written_png = render_scanner_path_view(result, png_path, dpi=72)

    loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert loaded["report_type"] == "phase3_ideal_scanner_line_path"
    assert loaded["sample_count"] == 5
    assert loaded["summary"]["target_hit_count"] == 5
    assert "time_s" in written_csv.read_text(encoding="utf-8").splitlines()[0]
    assert written_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert written_png.stat().st_size > 10_000


def test_ideal_scanner_line_path_report_is_schema_valid(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    result = run_ideal_scanner_line_path(project, sample_count=5)

    SchemaStore.load(project_root / "schemas").validate(
        result.to_dict(),
        "phase3_ideal_scanner_line_path.schema.json",
        source="test scanner path report",
    )
