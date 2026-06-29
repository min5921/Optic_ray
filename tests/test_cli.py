from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lidarsim.cli import main


def test_validate_command_reports_resolved_project(project_root: Path, capsys) -> None:
    result = main(["validate", str(project_root / "configs" / "project.yaml")])
    output = capsys.readouterr()

    assert result == 0
    assert "Project valid: optic_ray_default" in output.out
    assert "4 components, 1 materials" in output.out
    assert "Resolved config SHA-256:" in output.out
    assert output.err == ""


def test_validate_command_returns_nonzero_for_missing_project(tmp_path: Path, capsys) -> None:
    result = main(["validate", str(tmp_path / "missing.yaml")])
    output = capsys.readouterr()

    assert result == 2
    assert "Cannot read YAML" in output.err


def test_validate_command_writes_resolved_si_snapshot(
    project_root: Path, tmp_path: Path, capsys
) -> None:
    output_path = tmp_path / "resolved.yaml"

    result = main(
        [
            "validate",
            str(project_root / "configs" / "project.yaml"),
            "--write-resolved",
            str(output_path),
        ]
    )
    capsys.readouterr()

    assert result == 0
    resolved = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert resolved["scenarios"]["baseline_1550nm"]["source"]["wavelength_m"] == pytest.approx(
        1.55e-6
    )
    assert len(resolved["config_hash"]) == 64
