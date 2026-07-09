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
    assert "virtual_monostatic receiver" in output.err
    assert "현재 Phase에서 생성되지 않는 output" in output.err
    assert "analytical regression 기준" in output.err


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


def test_review_command_writes_html_and_png(project_root: Path, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "phase0_1_review.html"

    result = main(
        [
            "review",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(output_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    assert "Phase 0.1 review:" in output.out
    assert "Hardware readiness: analytical_only" in output.out
    assert output_path.is_file()
    assert output_path.with_name("phase0_1_review_placement.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert output.err == ""


def test_beam_command_writes_schema_validated_report_and_plot(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    report_path = tmp_path / "beam.yaml"
    plot_path = tmp_path / "beam.png"

    result = main(
        [
            "beam",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(report_path),
            "--plot",
            str(plot_path),
            "--z-max-m",
            "0.02",
            "--samples",
            "21",
            "--grid-size",
            "101",
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["report_type"] == "phase1_beam"
    assert report["profile_audit"]["status"] == "pass"
    assert report["analytical_checks"]["status"] == "pass"
    assert report["accuracy"]["hardware_readiness"] == "analytical_only"
    assert report["summary"]["paraxial_validity_status"] == "warning"
    assert plot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert report_path.with_name("beam_summary.yaml").is_file()
    assert "Power integral: pass" in output.out
    assert "small-angle geometric proxy error" in output.err


def test_beam_command_accepts_unit_bearing_cli_lengths(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    report_path = tmp_path / "unit_beam.yaml"

    result = main(
        [
            "beam",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(report_path),
            "--plot",
            str(tmp_path / "unit_beam.png"),
            "--z-max-m",
            "20 mm",
            "--profile-distance-m",
            "10 mm",
            "--samples",
            "11",
            "--grid-size",
            "51",
            "--dpi",
            "72",
        ]
    )
    capsys.readouterr()

    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert result == 0
    assert report["propagation"]["z_max_m"] == pytest.approx(0.02)
    assert report["profile_audit"]["distance_m"] == pytest.approx(0.01)


def test_beam_command_default_creates_timestamped_run_directory(
    copied_project: Path,
    capsys,
) -> None:
    result = main(
        [
            "beam",
            str(copied_project),
            "--samples",
            "11",
            "--grid-size",
            "51",
            "--dpi",
            "72",
        ]
    )
    capsys.readouterr()

    run_directories = list((copied_project.parent.parent / "results" / "phase1").iterdir())
    assert result == 0
    assert len(run_directories) == 1
    assert (run_directories[0] / "beam_report.yaml").is_file()
    assert (run_directories[0] / "beam_summary.yaml").is_file()
    assert (run_directories[0] / "beam.png").is_file()


def test_optical_train_command_writes_schema_validated_report_and_plot(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    report_path = tmp_path / "phase2_train.yaml"
    plot_path = tmp_path / "phase2_train.png"

    result = main(
        [
            "optical-train",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(report_path),
            "--plot",
            str(plot_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["report_type"] == "phase2_optical_train"
    assert report["summary"]["q_parameter_status"] == "pass"
    assert report["summary"]["energy_ledger_status"] == "pass"
    assert report["summary"]["aperture_status"] == "pass"
    assert plot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "Phase 2 optical train report:" in output.out
    assert "unsupported=0" in output.out


def test_workspace_command_writes_scene_and_plot(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    plot_path = tmp_path / "workspace.png"
    scene_path = tmp_path / "viewport_scene.yaml"

    result = main(
        [
            "workspace",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(plot_path),
            "--write-scene",
            str(scene_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    assert plot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    scene = yaml.safe_load(scene_path.read_text(encoding="utf-8"))
    assert scene["project_id"] == "optic_ray_default"
    assert any(ray["status"] == "target_hit" for ray in scene["rays"])
    assert len(scene["footprints"]) == 1
    assert "Optical assembly workspace:" in output.out
    assert "Viewport scene:" in output.out
    assert "Source of truth: config/report driven" in output.out
