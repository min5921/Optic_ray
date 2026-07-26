from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import lidarsim.ui.runner as ui_runner
from lidarsim.config import load_project
from lidarsim.ui import (
    SimulationParameterEdits,
    create_simulation_variant,
    run_ui_simulation,
    run_ui_variant_transaction,
)


def test_ui_runner_writes_reproducible_result_bundle(
    project_root: Path,
    tmp_path: Path,
) -> None:
    result = run_ui_simulation(
        project_root / "configs" / "project.yaml",
        output_directory=tmp_path / "ui_result",
        include_scanner_path=False,
        dpi=72,
    )

    assert result.config_hash == load_project(project_root / "configs" / "project.yaml").config_hash
    assert result.summary["target_hit_count"] == 1
    assert result.summary["estimated_received_power_w"] > 0.0
    assert result.report_path.is_file()
    assert result.scene_path.is_file()
    assert result.workspace_image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.optical_train_image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.dashboard_path.is_file()
    assert result.scanner_path_report_path is None
    assert result.scanner_path_csv_path is None
    assert result.scanner_path_image_path is None


def test_ui_runner_can_include_scanner_path(project_root: Path, tmp_path: Path) -> None:
    result = run_ui_simulation(
        project_root / "configs" / "project.yaml",
        output_directory=tmp_path / "ui_result_with_path",
        include_scanner_path=True,
        dpi=72,
    )

    assert result.scanner_path_report_path is not None
    assert result.scanner_path_report_path.is_file()
    assert result.scanner_path_csv_path is not None
    assert result.scanner_path_csv_path.is_file()
    assert result.scanner_path_image_path is not None
    assert result.scanner_path_image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_ui_runner_preserves_existing_bundle_when_render_fails(
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "existing_bundle"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("previous-good-result", encoding="utf-8")

    def _fail_render(*args, **kwargs):
        raise RuntimeError("injected optical render failure")

    monkeypatch.setattr(ui_runner, "render_optical_train_view", _fail_render)

    with pytest.raises(RuntimeError, match="injected optical render failure"):
        run_ui_simulation(
            project_root / "configs" / "project.yaml",
            output_directory=destination,
            include_scanner_path=False,
            dpi=72,
        )

    assert marker.read_text(encoding="utf-8") == "previous-good-result"
    assert not list(tmp_path.glob(".existing_bundle.staging-*"))
    assert not list(tmp_path.glob(".existing_bundle.backup-*"))


def test_ui_runner_uses_project_result_root_when_output_is_omitted(
    copied_project: Path,
) -> None:
    raw_project = yaml.safe_load(copied_project.read_text(encoding="utf-8"))
    raw_project["result_root"] = "custom_ui_results"
    copied_project.write_text(
        yaml.safe_dump(raw_project, sort_keys=False),
        encoding="utf-8",
    )

    result = run_ui_simulation(
        copied_project,
        include_scanner_path=False,
        dpi=72,
    )

    expected_root = copied_project.parent / "custom_ui_results" / "ui_runs"
    assert result.output_directory.parent == expected_root.resolve()
    assert result.dashboard_path.is_file()


def test_ui_variant_transaction_writes_valid_config_and_result_together(
    copied_project: Path,
    tmp_path: Path,
) -> None:
    config_dir = copied_project.parent / "ui_runs"

    transaction = run_ui_variant_transaction(
        project_path=copied_project,
        scenario_id="atomic_success",
        scenario_output=config_dir / "atomic_success.yaml",
        project_output=config_dir / "atomic_success_project.yaml",
        output_directory=tmp_path / "atomic_success_result",
        parameter_edits=SimulationParameterEdits(
            scanner_static_command_angle_rad="0.25 deg",
        ),
        include_scanner_path=False,
        dpi=72,
    )

    loaded = load_project(transaction.variant.project_path)
    assert loaded.config_hash == transaction.variant.config_hash
    assert transaction.simulation.config_hash == transaction.variant.config_hash
    assert transaction.variant.provenance_path.is_file()
    assert transaction.simulation.dashboard_path.is_file()


def test_ui_variant_transaction_rolls_back_config_provenance_and_result_on_failure(
    copied_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = copied_project.parent / "ui_runs"
    scenario_path = config_dir / "atomic_existing.yaml"
    project_path = config_dir / "atomic_existing_project.yaml"
    existing = create_simulation_variant(
        project_path=copied_project,
        scenario_id="atomic_existing",
        scenario_output=scenario_path,
        project_output=project_path,
        parameter_edits=SimulationParameterEdits(
            scanner_static_command_angle_rad="0.1 deg",
        ),
    )
    before = {
        path: path.read_bytes()
        for path in (scenario_path, project_path, existing.provenance_path)
    }
    destination = tmp_path / "atomic_existing_result"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("previous-good-result", encoding="utf-8")

    def _fail_render(*args, **kwargs):
        raise RuntimeError("injected transaction render failure")

    monkeypatch.setattr(ui_runner, "render_optical_train_view", _fail_render)

    with pytest.raises(RuntimeError, match="injected transaction render failure"):
        run_ui_variant_transaction(
            project_path=copied_project,
            scenario_id="atomic_existing",
            scenario_output=scenario_path,
            project_output=project_path,
            output_directory=destination,
            parameter_edits=SimulationParameterEdits(
                scanner_static_command_angle_rad="0.2 deg",
            ),
            overwrite=True,
            include_scanner_path=False,
            dpi=72,
        )

    for path, payload in before.items():
        assert path.read_bytes() == payload
    assert marker.read_text(encoding="utf-8") == "previous-good-result"
    assert not list(config_dir.glob(".*.rollback-*"))
    assert not list(tmp_path.glob(".atomic_existing_result.staging-*"))
    assert not list(tmp_path.glob(".atomic_existing_result.backup-*"))
