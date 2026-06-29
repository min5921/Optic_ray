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


def test_placement_command_reports_baseline_geometry(project_root: Path, capsys) -> None:
    result = main(["placement", str(project_root / "configs" / "project.yaml")])
    output = capsys.readouterr()

    assert result == 0
    assert "Active scenario placement: baseline_1550nm" in output.out
    assert "source: component=custom:baseline_fiber_source" in output.out
    assert "collimator: component=custom:ideal_collimator_f20, origin_m=(0, 0, -0.08)" in output.out
    assert "port input: origin_m=(0, 0, -0.08), axis=(0, 0, 1)" in output.out
    assert output.err == ""


def test_placement_command_writes_report(project_root: Path, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "placement.yaml"

    result = main(
        [
            "placement",
            str(project_root / "configs" / "project.yaml"),
            "--write-report",
            str(output_path),
        ]
    )
    capsys.readouterr()

    assert result == 0
    report = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert report["elements"]["collimator"]["translation_world_m"] == pytest.approx(
        [0.0, 0.0, -0.08]
    )
    assert report["elements"]["source"]["ports"]["output"][
        "propagation_axis_world"
    ] == pytest.approx([0.0, 0.0, 1.0])


def test_inspect_mesh_command_reports_geometry(
    project_root: Path, tmp_path: Path, write_binary_stl, capsys
) -> None:
    triangles = [
        [(0, 0, 0), (0, 1, 0), (1, 0, 0)],
        [(0, 0, 0), (1, 0, 0), (0, 0, 1)],
        [(0, 0, 0), (0, 0, 1), (0, 1, 0)],
        [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
    ]
    mesh_path = write_binary_stl(tmp_path / "tetra.stl", triangles)
    metadata_path = tmp_path / "tetra.stl.yaml"
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "asset_id": "test:cli_tetra",
                "mesh": {
                    "file": mesh_path.name,
                    "format": "stl",
                    "binary_preferred": True,
                    "unit_scale_m": 0.001,
                },
                "role": "mount",
                "placement": {
                    "parent_frame": "world",
                    "translation_m": [0.0, 0.0, 0.0],
                    "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                },
                "validation": {
                    "require_closed_mesh": True,
                    "normal_policy": "validate",
                    "expected_bounds_m": None,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "inspect-mesh",
            str(metadata_path),
            "--project",
            str(project_root / "configs" / "project.yaml"),
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    assert "STL asset valid: test:cli_tetra" in output.out
    assert "Encoding: binary, triangles: 4, unique vertices: 4" in output.out
    assert "Closed: True" in output.out
    assert output.err == ""


def test_inspect_measurement_command_reports_data_hash(
    project_root: Path, tmp_path: Path, capsys
) -> None:
    data_path = tmp_path / "profile.csv"
    data_path.write_text("x,irradiance\n0,1\n", encoding="utf-8")
    metadata_path = tmp_path / "profile.measurement.yaml"
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "measurement_id": "lab:cli_profile",
                "measurement_type": "source_beam_profile",
                "dataset_role": "validation",
                "data_file": data_path.name,
                "conditions": {"wavelength": "1550 nm"},
                "instrument": {},
                "uncertainty": {},
                "coordinate_frame": "measurement_frame",
                "units": {"x": "mm", "irradiance": "W/m^2"},
                "processing": [],
                "source_hash": None,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "inspect-measurement",
            str(metadata_path),
            "--project",
            str(project_root / "configs" / "project.yaml"),
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    assert "Measurement valid: lab:cli_profile" in output.out
    assert "Data SHA-256:" in output.out
    assert output.err == ""


def test_report_command_writes_schema_validated_phase0_report(
    project_root: Path, tmp_path: Path, capsys
) -> None:
    output_path = tmp_path / "phase0_report.yaml"

    result = main(
        [
            "report",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(output_path),
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    report = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert report["report_type"] == "phase0_validation"
    assert report["accuracy"]["confidence_level"] == "comparative"
    assert report["energy_ledger"]["status"] == "not_evaluated"
    assert report["convergence"]["overall_status"] == "warning"
    assert "Phase 0 report:" in output.out
    assert output.err == ""


def test_view_command_writes_headless_png(project_root: Path, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "placement.png"

    result = main(
        [
            "view",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(output_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "Placement view:" in output.out
    assert output.err == ""
