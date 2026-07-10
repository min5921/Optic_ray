from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
    assert "Reference fidelity로만 생성되는 output" in output.err
    assert "scan_path=ideal_forward_line_command_path" in output.err
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


def test_dashboard_command_writes_self_contained_workspace_html(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    html_path = tmp_path / "dashboard.html"

    result = main(
        [
            "dashboard",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(html_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    document = html_path.read_text(encoding="utf-8")
    assert "Optic Ray Workspace Dashboard" in document
    assert "data:image/png;base64," in document
    assert "Power ledger" in document
    assert "Target footprint" in document
    assert "Receiver return" in document
    assert "Virtual aperture estimate" in document
    assert "single-mode fiber" in document
    assert html_path.with_name("dashboard_phase2_report.yaml").is_file()
    assert html_path.with_name("dashboard_viewport_scene.yaml").is_file()
    assert html_path.with_name("dashboard_workspace.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert html_path.with_name("dashboard_optical_train.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert "Workspace dashboard:" in output.out
    assert "P_virtual_ap=" in output.out


def test_dashboard_command_can_embed_scanner_path(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    html_path = tmp_path / "dashboard_with_path.html"

    result = main(
        [
            "dashboard",
            str(project_root / "configs" / "project.yaml"),
            "--output",
            str(html_path),
            "--include-scanner-path",
            "--scanner-path-samples",
            "5",
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    document = html_path.read_text(encoding="utf-8")
    assert "Scanner path — ideal forward line" in document
    assert "ideal command-path reference" in document
    assert html_path.with_name("dashboard_with_path_scanner_path.yaml").is_file()
    assert html_path.with_name("dashboard_with_path_scanner_path.csv").is_file()
    assert html_path.with_name("dashboard_with_path_scanner_path.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert "Scanner path report:" in output.out
    assert "Scanner path plot:" in output.out


def test_scanner_sweep_command_writes_yaml_csv_and_plot(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    report_path = tmp_path / "scanner_sweep.yaml"
    csv_path = tmp_path / "scanner_sweep.csv"
    plot_path = tmp_path / "scanner_sweep.png"

    result = main(
        [
            "scanner-sweep",
            str(project_root / "configs" / "project.yaml"),
            "--angles-deg",
            "-2",
            "0",
            "2",
            "--output",
            str(report_path),
            "--csv",
            str(csv_path),
            "--plot",
            str(plot_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["report_type"] == "phase3_static_scanner_angle_sweep"
    assert report["summary"]["sample_count"] == 3
    assert report["summary"]["target_hit_count"] == 3
    assert csv_path.read_text(encoding="utf-8").splitlines()[0].startswith("sample_index")
    assert plot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "Scanner sweep report:" in output.out
    assert "static command-angle comparison only" in output.out


def test_scanner_path_command_writes_yaml_csv_and_plot(
    project_root: Path,
    tmp_path: Path,
    capsys,
) -> None:
    report_path = tmp_path / "scanner_path.yaml"
    csv_path = tmp_path / "scanner_path.csv"
    plot_path = tmp_path / "scanner_path.png"

    result = main(
        [
            "scanner-path",
            str(project_root / "configs" / "project.yaml"),
            "--samples",
            "5",
            "--output",
            str(report_path),
            "--csv",
            str(csv_path),
            "--plot",
            str(plot_path),
            "--dpi",
            "72",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["report_type"] == "phase3_ideal_scanner_line_path"
    assert report["sample_count"] == 5
    assert report["summary"]["target_hit_count"] == 5
    assert csv_path.read_text(encoding="utf-8").splitlines()[0].startswith("sample_index")
    assert plot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "Scanner path report:" in output.out
    assert "ideal forward-line command path only" in output.out


def test_placement_variant_command_writes_valid_variant_project(
    copied_project: Path,
    capsys,
) -> None:
    scenario_path = copied_project.parent / "mirror_shift.yaml"
    project_path = copied_project.parent / "mirror_shift_project.yaml"

    result = main(
        [
            "placement-variant",
            str(copied_project),
            "--element",
            "scan_mirror",
            "--scenario-id",
            "mirror_shift",
            "--scenario-output",
            str(scenario_path),
            "--project-output",
            str(project_path),
            "--translation-m",
            "0.1",
            "0.0",
            "0.0",
        ]
    )
    output = capsys.readouterr()

    assert result == 0
    assert scenario_path.is_file()
    assert project_path.is_file()
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    assert scenario["scenario_id"] == "mirror_shift"
    assert scenario["optical_assembly"]["elements"][2]["placement"]["translation_m"] == pytest.approx(
        [0.1, 0.0, 0.0]
    )
    assert "Placement variant project:" in output.out
    assert "Variant config valid:" in output.out


def test_ui_command_reports_optional_dependency_when_missing(
    project_root: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr("lidarsim.cli.importlib.util.find_spec", lambda name: None)

    result = main(["ui", str(project_root / "configs" / "project.yaml"), "--headless"])
    output = capsys.readouterr()

    assert result == 2
    assert "[ui]" in output.err


def test_ui_command_launches_streamlit_with_project_argument(
    project_root: Path,
    monkeypatch,
) -> None:
    captured: dict = {}

    monkeypatch.setattr("lidarsim.cli.importlib.util.find_spec", lambda name: object())

    def fake_run(command, *, env, check):
        captured["command"] = command
        captured["env"] = env
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("lidarsim.cli.subprocess.run", fake_run)
    project_path = project_root / "configs" / "project.yaml"

    result = main(["ui", str(project_path), "--port", "8765", "--headless"])

    assert result == 0
    assert captured["command"][1:4] == ["-m", "streamlit", "run"]
    assert "--server.port=8765" in captured["command"]
    assert "--server.headless=true" in captured["command"]
    assert "--browser.gatherUsageStats=false" in captured["command"]
    assert captured["command"][-1] == str(project_path.resolve())
    assert captured["env"]["LIDARSIM_UI_PROJECT"] == str(project_path.resolve())
    assert captured["check"] is False
