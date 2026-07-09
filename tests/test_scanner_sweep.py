from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.scanner import (
    default_static_sweep_angles,
    run_static_scanner_angle_sweep,
    write_scanner_sweep_csv,
)
from lidarsim.visualization import render_scanner_sweep_view


def test_default_static_sweep_uses_configured_mechanical_amplitude(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    angles = default_static_sweep_angles(project, count=3)

    assert angles == pytest.approx(
        [-math.radians(5.0), 0.0, math.radians(5.0)],
        abs=1e-15,
    )


def test_static_scanner_angle_sweep_tracks_hit_and_return(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    angles = [math.radians(-5.0), 0.0, math.radians(5.0)]

    result = run_static_scanner_angle_sweep(project, angles)

    assert result.angle_count == 3
    assert [sample.command_angle_deg for sample in result.samples] == pytest.approx(
        [-5.0, 0.0, 5.0]
    )
    assert result.samples[0].final_direction[2] > 0.0
    assert result.samples[1].final_direction[2] == pytest.approx(0.0, abs=1e-15)
    assert result.samples[2].final_direction[2] < 0.0
    assert all(sample.target_hit for sample in result.samples)
    assert all(sample.sample_status == "positive_return" for sample in result.samples)
    assert all(sample.estimated_received_power_w > 0.0 for sample in result.samples)
    assert result.samples[0].target_local_coordinates_m is not None
    assert result.samples[2].target_local_coordinates_m is not None
    assert result.samples[0].target_local_coordinates_m[1] > result.samples[1].target_local_coordinates_m[1]
    assert result.samples[2].target_local_coordinates_m[1] < result.samples[1].target_local_coordinates_m[1]


def test_static_scanner_sweep_serializes_yaml_csv_and_png(
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    result = run_static_scanner_angle_sweep(project, [math.radians(-2.0), 0.0, math.radians(2.0)])
    yaml_path = tmp_path / "scanner_sweep.yaml"
    csv_path = tmp_path / "scanner_sweep.csv"
    png_path = tmp_path / "scanner_sweep.png"

    yaml_path.write_text(
        yaml.safe_dump(result.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    written_csv = write_scanner_sweep_csv(result, csv_path)
    written_png = render_scanner_sweep_view(result, png_path, dpi=72)

    loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert loaded["report_type"] == "phase3_static_scanner_angle_sweep"
    assert loaded["summary"]["sample_count"] == 3
    assert "command_angle_deg" in written_csv.read_text(encoding="utf-8").splitlines()[0]
    assert written_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert written_png.stat().st_size > 10_000
