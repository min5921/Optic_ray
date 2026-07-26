"""Reproducible simulation/report runner used by the browser UI."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lidarsim.config import load_project, schema_directory_for_project
from lidarsim.config.schema import SchemaStore
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.scanner import run_ideal_scanner_line_path, write_scanner_path_csv
from lidarsim.ui.assembly import build_viewport_scene
from lidarsim.ui.dashboard import write_workspace_dashboard_html
from lidarsim.ui.simulation_variant import (
    AssemblyElementEdits,
    ProjectDraft,
    SimulationParameterEdits,
    SimulationVariantResult,
    create_simulation_variant,
)
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


@dataclass(frozen=True, slots=True)
class UiVariantSimulationRun:
    """하나의 rollback 가능한 variant 적용과 simulation 결과."""

    variant: SimulationVariantResult
    simulation: UiSimulationRun

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant.to_dict(),
            "simulation": self.simulation.to_dict(),
        }


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _configured_result_root(project: Any) -> Path:
    """Project ``result_root``를 project YAML directory 기준으로 해석한다."""

    configured = Path(str(project.project.get("result_root", "results")))
    if configured.is_absolute():
        return configured.resolve()
    return (project.project_path.parent / configured).resolve()


def _promote_result_bundle(staging: Path, destination: Path) -> None:
    """완성된 staging bundle을 rollback 가능한 directory swap으로 승격한다."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        os.replace(staging, destination)
        return

    backup = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.backup-",
            dir=destination.parent,
        )
    )
    backup.rmdir()
    os.replace(destination, backup)
    try:
        os.replace(staging, destination)
    except Exception:
        os.replace(backup, destination)
        raise
    shutil.rmtree(backup)


def _variant_provenance_path(project_path: Path) -> Path:
    stem = project_path.stem
    base = stem[:-8] if stem.endswith("_project") else stem
    return project_path.with_name(f"{base}_provenance.yaml")


def _restore_file_snapshot(path: Path, previous: bytes | None) -> None:
    """Rollback도 partial write가 보이지 않도록 같은 directory에서 교체한다."""

    if previous is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.rollback-",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(previous)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
        destination = (
            _configured_result_root(project)
            / "ui_runs"
            / f"{project.active_scenario['scenario_id']}_{project.config_hash[:8]}"
        )
    else:
        destination = Path(output_directory).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-",
            dir=destination.parent,
        )
    )
    scanner_result = None
    try:
        report_path_staged = _write_yaml(
            staging / "optical_train_report.yaml",
            report_data,
        )
        scene_path_staged = _write_yaml(staging / "viewport_scene.yaml", scene_data)
        workspace_path_staged = render_viewport_scene(
            scene,
            staging / "workspace.png",
            dpi=dpi,
        )
        train_path_staged = render_optical_train_view(
            report,
            staging / "optical_train.png",
            dpi=dpi,
        )

        scanner_report_path_staged = None
        scanner_csv_path_staged = None
        scanner_image_path_staged = None
        if include_scanner_path:
            scanner_result = run_ideal_scanner_line_path(project)
            scanner_data = scanner_result.to_dict()
            schemas.validate(
                scanner_data,
                "phase3_ideal_scanner_line_path.schema.json",
                source="generated UI scanner path report",
            )
            scanner_report_path_staged = _write_yaml(
                staging / "scanner_path.yaml",
                scanner_data,
            )
            scanner_csv_path_staged = write_scanner_path_csv(
                scanner_result,
                staging / "scanner_path.csv",
            )
            scanner_image_path_staged = render_scanner_path_view(
                scanner_result,
                staging / "scanner_path.png",
                dpi=dpi,
            )

        write_workspace_dashboard_html(
            project=project,
            report=report,
            scene=scene,
            workspace_image=workspace_path_staged,
            optical_train_image=train_path_staged,
            output_path=staging / "dashboard.html",
            report_path=report_path_staged,
            scene_path=scene_path_staged,
            scanner_path=scanner_result,
            scanner_path_image=scanner_image_path_staged,
            scanner_path_report_path=scanner_report_path_staged,
            scanner_path_csv_path=scanner_csv_path_staged,
        )
        _promote_result_bundle(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    report_path = destination / "optical_train_report.yaml"
    scene_path = destination / "viewport_scene.yaml"
    workspace_path = destination / "workspace.png"
    train_path = destination / "optical_train.png"
    dashboard_path = destination / "dashboard.html"
    scanner_report_path = (
        destination / "scanner_path.yaml" if include_scanner_path else None
    )
    scanner_csv_path = (
        destination / "scanner_path.csv" if include_scanner_path else None
    )
    scanner_image_path = (
        destination / "scanner_path.png" if include_scanner_path else None
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


def run_ui_variant_transaction(
    *,
    project_path: str | Path,
    scenario_id: str,
    scenario_output: str | Path,
    project_output: str | Path,
    output_directory: str | Path | None = None,
    parameter_edits: SimulationParameterEdits | None = None,
    element_edits: AssemblyElementEdits | None = None,
    draft: ProjectDraft | None = None,
    overwrite: bool = False,
    include_scanner_path: bool = True,
    dpi: int = 120,
) -> UiVariantSimulationRun:
    """Variant config와 완성된 result bundle을 하나의 rollback 단위로 적용한다.

    Variant writer가 schema validation을 마친 뒤 simulation/report/render를 staging
    result directory에서 끝낸다. 어느 단계든 실패하면 scenario, project와 provenance
    sidecar를 실행 전 byte snapshot으로 되돌린다. Result bundle은
    :func:`run_ui_simulation`의 directory swap이 기존 성공 결과를 보존한다.
    """

    scenario_path = Path(scenario_output).resolve()
    variant_project_path = Path(project_output).resolve()
    provenance_path = _variant_provenance_path(variant_project_path)
    snapshots = {
        path: path.read_bytes() if path.exists() else None
        for path in (scenario_path, variant_project_path, provenance_path)
    }
    try:
        variant = create_simulation_variant(
            project_path=project_path,
            scenario_id=scenario_id,
            scenario_output=scenario_path,
            project_output=variant_project_path,
            parameter_edits=parameter_edits,
            element_edits=element_edits,
            draft=draft,
            overwrite=overwrite,
        )
        simulation = run_ui_simulation(
            variant.project_path,
            output_directory=output_directory,
            include_scanner_path=include_scanner_path,
            dpi=dpi,
        )
    except Exception:
        rollback_errors: list[Exception] = []
        for path, previous in snapshots.items():
            try:
                _restore_file_snapshot(path, previous)
            except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_errors.append(exc)
        if rollback_errors:
            raise RuntimeError(
                "UI variant simulation 실패 후 config rollback에도 실패했습니다: "
                + "; ".join(str(error) for error in rollback_errors)
            ) from rollback_errors[0]
        raise
    return UiVariantSimulationRun(variant=variant, simulation=simulation)


__all__ = [
    "UiSimulationRun",
    "UiVariantSimulationRun",
    "run_ui_simulation",
    "run_ui_variant_transaction",
]
