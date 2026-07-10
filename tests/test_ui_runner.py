from __future__ import annotations

from pathlib import Path

from lidarsim.ui import run_ui_simulation


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
