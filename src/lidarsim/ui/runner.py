"""Reproducible simulation/report runner used by the browser UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lidarsim.config import find_project_root, load_project, schema_directory_for_project
from lidarsim.config.schema import SchemaStore
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.scanner import run_ideal_scanner_line_path, write_scanner_path_csv
from lidarsim.ui.assembly import build_viewport_scene
from lidarsim.ui.dashboard import write_workspace_dashboard_html
from lidarsim.visualization import (
    render_optical_train_view,
    render_scanner_path_view,
    render_viewport_scene,
)


@dataclass(frozen=True, slots=True)
class UiSimulationRun:
    """Paths and summary produced by one UI-triggered simulation."""

    project_path: Path
    config_hash: str
    output_directory: Path
    report_path: Path
    scene_path: Path
    workspace_image_path: Path
    optical_train_image_path: Path
    dashboard_path: Path
    scanner_path_report_path: Path | None
    scanner_path_csv_path: Path | None
    scanner_path_image_path: Path | None
    summary: dict[str, Any]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": str(self.project_path),
            "config_hash": self.config_hash,
            "output_directory": str(self.output_directory),
            "report_path": str(self.report_path),
            "scene_path": str(self.scene_path),
            "workspace_image_path": str(self.workspace_image_path),
            "optical_train_image_path": str(self.optical_train_image_path),
            "dashboard_path": str(self.dashboard_path),
            "scanner_path_report_path": (
                None
                if self.scanner_path_report_path is None
                else str(self.scanner_path_report_path)
            ),
            "scanner_path_csv_path": (
                None if self.scanner_path_csv_path is None else str(self.scanner_path_csv_path)
            ),
            "scanner_path_image_path": (
                None if self.scanner_path_image_path is None else str(self.scanner_path_image_path)
            ),
            "summary": dict(self.summary),
            "warnings": list(self.warnings),
        }


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def run_ui_simulation(
    project_path: str | Path,
    *,
    output_directory: str | Path | None = None,
    include_scanner_path: bool = True,
    dpi: int = 120,
) -> UiSimulationRun:
    """Validate a project and write the complete UI result bundle."""

    project = load_project(project_path)
    report = build_phase2_optical_train_report(project)
    report_data = report.to_dict()
    schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
    schemas.validate(
        report_data,
        "phase2_optical_train_report.schema.json",
        source="generated UI Phase 2 report",
    )
    scene = build_viewport_scene(project, report=report)
    scene_data = scene.to_dict()
    schemas.validate(
        scene_data,
        "viewport_scene.schema.json",
        source="generated UI viewport scene",
    )

    if output_directory is None:
        root = find_project_root(project.project_path)
        destination = (
            root
            / "results"
            / "ui_runs"
            / f"{project.active_scenario['scenario_id']}_{project.config_hash[:8]}"
        )
    else:
        destination = Path(output_directory).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    report_path = _write_yaml(destination / "optical_train_report.yaml", report_data)
    scene_path = _write_yaml(destination / "viewport_scene.yaml", scene_data)
    workspace_path = render_viewport_scene(
        scene,
        destination / "workspace.png",
        dpi=dpi,
    )
    train_path = render_optical_train_view(
        report,
        destination / "optical_train.png",
        dpi=dpi,
    )

    scanner_result = None
    scanner_report_path = None
    scanner_csv_path = None
    scanner_image_path = None
    if include_scanner_path:
        scanner_result = run_ideal_scanner_line_path(project)
        scanner_data = scanner_result.to_dict()
        schemas.validate(
            scanner_data,
            "phase3_ideal_scanner_line_path.schema.json",
            source="generated UI scanner path report",
        )
        scanner_report_path = _write_yaml(destination / "scanner_path.yaml", scanner_data)
        scanner_csv_path = write_scanner_path_csv(
            scanner_result,
            destination / "scanner_path.csv",
        )
        scanner_image_path = render_scanner_path_view(
            scanner_result,
            destination / "scanner_path.png",
            dpi=dpi,
        )

    dashboard_path = write_workspace_dashboard_html(
        project=project,
        report=report,
        scene=scene,
        workspace_image=workspace_path,
        optical_train_image=train_path,
        output_path=destination / "dashboard.html",
        report_path=report_path,
        scene_path=scene_path,
        scanner_path=scanner_result,
        scanner_path_image=scanner_image_path,
        scanner_path_report_path=scanner_report_path,
        scanner_path_csv_path=scanner_csv_path,
    )
    return UiSimulationRun(
        project_path=project.project_path,
        config_hash=project.config_hash,
        output_directory=destination,
        report_path=report_path,
        scene_path=scene_path,
        workspace_image_path=workspace_path,
        optical_train_image_path=train_path,
        dashboard_path=dashboard_path,
        scanner_path_report_path=scanner_report_path,
        scanner_path_csv_path=scanner_csv_path,
        scanner_path_image_path=scanner_image_path,
        summary=dict(report.summary),
        warnings=tuple(str(value) for value in report.accuracy["warnings"]),
    )


__all__ = ["UiSimulationRun", "run_ui_simulation"]
