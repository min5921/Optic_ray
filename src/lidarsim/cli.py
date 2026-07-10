"""Command-line entry point for configuration validation."""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from lidarsim.assets import load_measurement, load_stl_asset
from lidarsim.beam import build_source_beam, default_propagation_distance_m
from lidarsim.config import load_project, schema_directory_for_project
from lidarsim.config.units import resolve_quantities
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigError
from lidarsim.geometry import resolve_assembly
from lidarsim.results import (
    build_phase0_report,
    build_phase1_beam_report,
    build_phase2_optical_train_report,
    write_review_html,
)
from lidarsim.scanner import (
    default_static_sweep_angles,
    run_ideal_scanner_line_path,
    run_static_scanner_angle_sweep,
    write_scanner_path_csv,
    write_scanner_sweep_csv,
)
from lidarsim.ui import build_viewport_scene, create_placement_variant, write_workspace_dashboard_html
from lidarsim.visualization import (
    render_beam_view,
    render_optical_train_view,
    render_placement_view,
    render_scanner_path_view,
    render_scanner_sweep_view,
    render_viewport_scene,
)


def _length_argument(value: str) -> float:
    """CLI length를 meter float 또는 unit-bearing string으로 해석한다."""

    try:
        return float(value)
    except ValueError:
        pass
    try:
        return float(resolve_quantities({"value_m": value}, source="lidarsim CLI")["value_m"])
    except ConfigError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lidarsim", description="Optic Ray simulation tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate and resolve a project configuration")
    validate.add_argument("project", nargs="?", default="configs/project.yaml")
    validate.add_argument(
        "--write-resolved",
        type=Path,
        metavar="PATH",
        help="write the immutable resolved snapshot to YAML",
    )
    placement = subparsers.add_parser(
        "placement",
        help="resolve and inspect active-scenario component placements",
    )
    placement.add_argument("project", nargs="?", default="configs/project.yaml")
    placement.add_argument(
        "--write-report",
        type=Path,
        metavar="PATH",
        help="write the resolved placement report to YAML",
    )
    inspect_mesh = subparsers.add_parser(
        "inspect-mesh",
        help="validate an STL sidecar and inspect referenced geometry",
    )
    inspect_mesh.add_argument("metadata", type=Path)
    inspect_mesh.add_argument("--project", default="configs/project.yaml")
    inspect_mesh.add_argument("--write-report", type=Path, metavar="PATH")
    inspect_measurement = subparsers.add_parser(
        "inspect-measurement",
        help="validate measurement metadata and referenced data",
    )
    inspect_measurement.add_argument("metadata", type=Path)
    inspect_measurement.add_argument("--project", default="configs/project.yaml")
    inspect_measurement.add_argument("--write-report", type=Path, metavar="PATH")
    report = subparsers.add_parser(
        "report",
        help="write a schema-validated Phase 0 validation report",
    )
    report.add_argument("project", nargs="?", default="configs/project.yaml")
    report.add_argument(
        "--output",
        type=Path,
        default=Path("results/phase0_report.yaml"),
    )
    view = subparsers.add_parser(
        "view",
        help="render a headless 2D/3D placement PNG",
    )
    view.add_argument("project", nargs="?", default="configs/project.yaml")
    view.add_argument(
        "--output",
        type=Path,
        default=Path("results/placement.png"),
    )
    view.add_argument("--dpi", type=int, default=150)
    review = subparsers.add_parser(
        "review",
        help="write a self-contained Phase 0.1 HTML review and placement PNG",
    )
    review.add_argument("project", nargs="?", default="configs/project.yaml")
    review.add_argument(
        "--output",
        type=Path,
        default=Path("results/phase0_1_review.html"),
    )
    review.add_argument("--dpi", type=int, default=150)
    beam = subparsers.add_parser(
        "beam",
        help="run Phase 1 Gaussian free-space propagation and power audit",
    )
    beam.add_argument("project", nargs="?", default="configs/project.yaml")
    beam.add_argument(
        "--output",
        type=Path,
        help="full YAML report path; default creates a timestamped run directory",
    )
    beam.add_argument(
        "--plot",
        type=Path,
        help="PNG path; default uses the run directory",
    )
    beam.add_argument(
        "--summary",
        type=Path,
        help="compact YAML summary path; default uses the run directory",
    )
    beam.add_argument("--z-max-m", type=_length_argument, metavar="LENGTH")
    beam.add_argument("--profile-distance-m", type=_length_argument, metavar="LENGTH")
    beam.add_argument("--samples", type=int, default=201)
    beam.add_argument("--grid-size", type=int, default=301)
    beam.add_argument("--extent-radii", type=float, default=4.0)
    beam.add_argument("--dpi", type=int, default=150)
    optical_train = subparsers.add_parser(
        "optical-train",
        aliases=["train"],
        help="run the Phase 2 source-to-static-mirror target/receiver reference path",
    )
    optical_train.add_argument("project", nargs="?", default="configs/project.yaml")
    optical_train.add_argument(
        "--output",
        type=Path,
        help="YAML report path; default creates a timestamped run directory",
    )
    optical_train.add_argument(
        "--plot",
        type=Path,
        help="PNG path; default uses the run directory",
    )
    optical_train.add_argument("--dpi", type=int, default=150)
    workspace = subparsers.add_parser(
        "workspace",
        help="render the UI MVP 0 optical assembly workspace PNG",
    )
    workspace.add_argument("project", nargs="?", default="configs/project.yaml")
    workspace.add_argument(
        "--output",
        type=Path,
        default=Path("results/ui_workspace.png"),
        help="PNG workspace image path",
    )
    workspace.add_argument(
        "--write-scene",
        type=Path,
        help="optional serialized ViewportScene YAML path",
    )
    workspace.add_argument("--dpi", type=int, default=150)
    dashboard = subparsers.add_parser(
        "dashboard",
        help="write a self-contained read-only optical workspace dashboard HTML",
    )
    dashboard.add_argument("project", nargs="?", default="configs/project.yaml")
    dashboard.add_argument(
        "--output",
        type=Path,
        default=Path("results/ui_dashboard.html"),
        help="self-contained dashboard HTML path",
    )
    dashboard.add_argument(
        "--report",
        type=Path,
        help="optional Phase 2 report YAML path; default is next to dashboard",
    )
    dashboard.add_argument(
        "--write-scene",
        type=Path,
        help="optional ViewportScene YAML path; default is next to dashboard",
    )
    dashboard.add_argument(
        "--workspace-plot",
        type=Path,
        help="optional workspace PNG path; default is next to dashboard",
    )
    dashboard.add_argument(
        "--train-plot",
        type=Path,
        help="optional optical train PNG path; default is next to dashboard",
    )
    dashboard.add_argument(
        "--include-scanner-path",
        action="store_true",
        help="also run and embed an ideal forward-line scanner path report/plot",
    )
    dashboard.add_argument(
        "--scanner-path-samples",
        type=int,
        help="sample count for --include-scanner-path; default uses scanner.samples_per_line",
    )
    dashboard.add_argument(
        "--scanner-path-report",
        type=Path,
        help="optional scanner path YAML path; default is next to dashboard",
    )
    dashboard.add_argument(
        "--scanner-path-csv",
        type=Path,
        help="optional scanner path CSV path; default is next to dashboard",
    )
    dashboard.add_argument(
        "--scanner-path-plot",
        type=Path,
        help="optional scanner path PNG path; default is next to dashboard",
    )
    dashboard.add_argument("--dpi", type=int, default=150)
    scanner_sweep = subparsers.add_parser(
        "scanner-sweep",
        help="run a static scanner command-angle sweep against the Phase 2 reference model",
    )
    scanner_sweep.add_argument("project", nargs="?", default="configs/project.yaml")
    scanner_sweep.add_argument(
        "--angles-deg",
        type=float,
        nargs="+",
        help="explicit static scanner command angles in degrees",
    )
    scanner_sweep.add_argument(
        "--start-deg",
        type=float,
        help="range start angle in degrees; default uses -mechanical_amplitude",
    )
    scanner_sweep.add_argument(
        "--stop-deg",
        type=float,
        help="range stop angle in degrees; default uses +mechanical_amplitude",
    )
    scanner_sweep.add_argument(
        "--count",
        type=int,
        default=11,
        help="number of range samples when --angles-deg is not used",
    )
    scanner_sweep.add_argument(
        "--output",
        type=Path,
        default=Path("results/scanner_sweep.yaml"),
        help="YAML sweep report path",
    )
    scanner_sweep.add_argument(
        "--csv",
        type=Path,
        help="CSV table path; default is next to --output",
    )
    scanner_sweep.add_argument(
        "--plot",
        type=Path,
        help="PNG trend plot path; default is next to --output",
    )
    scanner_sweep.add_argument("--dpi", type=int, default=150)
    scanner_path = subparsers.add_parser(
        "scanner-path",
        help="run one ideal forward-line scanner path from active scanner waveform settings",
    )
    scanner_path.add_argument("project", nargs="?", default="configs/project.yaml")
    scanner_path.add_argument(
        "--samples",
        type=int,
        help="override scanner.samples_per_line for this reference run",
    )
    scanner_path.add_argument(
        "--output",
        type=Path,
        default=Path("results/scanner_path.yaml"),
        help="YAML scanner path report path",
    )
    scanner_path.add_argument(
        "--csv",
        type=Path,
        help="CSV table path; default is next to --output",
    )
    scanner_path.add_argument(
        "--plot",
        type=Path,
        help="PNG path plot; default is next to --output",
    )
    scanner_path.add_argument("--dpi", type=int, default=150)
    placement_variant = subparsers.add_parser(
        "placement-variant",
        help="write a variant scenario/project with numeric placement edits",
    )
    placement_variant.add_argument("project", nargs="?", default="configs/project.yaml")
    placement_variant.add_argument("--element", required=True, help="element id to edit")
    placement_variant.add_argument("--scenario-id", help="new variant scenario id")
    placement_variant.add_argument(
        "--scenario-output",
        type=Path,
        help="variant scenario YAML path; default is next to source project",
    )
    placement_variant.add_argument(
        "--project-output",
        type=Path,
        help="variant project YAML path; default is next to source project",
    )
    placement_variant.add_argument(
        "--translation-m",
        type=float,
        nargs=3,
        metavar=("X", "Y", "Z"),
        help="absolute placement translation in meters",
    )
    placement_variant.add_argument(
        "--quaternion-wxyz",
        type=float,
        nargs=4,
        metavar=("W", "X", "Y", "Z"),
        help="absolute placement quaternion",
    )
    placement_variant.add_argument(
        "--axial-gap-m",
        help='port placement axial gap; unit string such as "25 mm" is allowed',
    )
    placement_variant.add_argument(
        "--transverse-offset-m",
        nargs=2,
        metavar=("U", "V"),
        help='port placement transverse offset; unit strings such as "1 mm" are allowed',
    )
    placement_variant.add_argument(
        "--clocking-rad",
        help='port placement clocking angle; unit string such as "2 deg" is allowed',
    )
    placement_variant.add_argument(
        "--angular-misalignment-rad",
        nargs=2,
        metavar=("RX", "RY"),
        help='port placement angular misalignment; unit strings such as "1 deg" are allowed',
    )
    placement_variant.add_argument(
        "--overwrite",
        action="store_true",
        help="allow overwriting existing variant files",
    )
    ui = subparsers.add_parser(
        "ui",
        help="launch the Streamlit parameter and numeric-placement workspace",
    )
    ui.add_argument("project", nargs="?", default="configs/project.yaml")
    ui.add_argument("--port", type=int, default=8501, help="Streamlit server port")
    ui.add_argument(
        "--headless",
        action="store_true",
        help="do not open a browser automatically",
    )
    return parser


def _validate(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.write_resolved is not None:
        output_path = args.write_resolved.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(project.to_dict(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"Resolved snapshot: {output_path}")

    print(f"Project valid: {project.project['project_id']}")
    print(f"Scenarios: {len(project.scenarios)} (active: {project.project['active_baseline']})")
    print(
        "Catalog: "
        f"{project.catalog.count('component')} components, "
        f"{project.catalog.count('material')} materials"
    )
    print(f"Experiments: {len(project.experiments)}")
    print(f"Resolved config SHA-256: {project.config_hash}")
    for warning in project.warnings:
        print(warning.format(), file=sys.stderr)
    return 0


def _placement(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        assembly = resolve_assembly(
            project.active_scenario,
            project.catalog,
            source=str(project.project_path),
        )
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.write_report is not None:
        output_path = args.write_report.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(assembly.to_dict(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"Placement report: {output_path}")

    print(f"Active scenario placement: {project.project['active_baseline']}")
    for element_id, element in assembly.elements.items():
        x, y, z = element.T_world_from_component.translation_m
        print(
            f"{element_id}: component={element.component_ref}, "
            f"origin_m=({x:.9g}, {y:.9g}, {z:.9g})"
        )
        for port_id in element.ports:
            port_transform = element.world_from_port(port_id)
            px, py, pz = port_transform.translation_m
            ax, ay, az = port_transform.rotation[:, 2]
            print(
                f"  port {port_id}: origin_m=({px:.9g}, {py:.9g}, {pz:.9g}), "
                f"axis=({ax:.9g}, {ay:.9g}, {az:.9g})"
            )
    return 0


def _write_yaml_report(path: Path, report: dict) -> Path:
    output_path = path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return output_path


def _inspect_mesh(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        asset = load_stl_asset(args.metadata, schemas, catalog=project.catalog)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.write_report is not None:
        print(f"Mesh report: {_write_yaml_report(args.write_report, asset.to_dict())}")
    audit = asset.audit
    print(f"STL asset valid: {asset.identifier}")
    print(f"Mesh: {asset.mesh_path}")
    print(
        f"Encoding: {audit.encoding}, triangles: {audit.triangle_count}, "
        f"unique vertices: {audit.unique_vertex_count}"
    )
    print(f"Bounds raw: {audit.bounds_raw.tolist()}")
    print(f"Bounds SI (m): {audit.bounds_m.tolist()}")
    print(
        f"Closed: {audit.is_closed}, boundary edges: {audit.boundary_edge_count}, "
        f"non-manifold edges: {audit.nonmanifold_edge_count}"
    )
    print(f"Mesh SHA-256: {audit.content_sha256}")
    for warning in asset.warnings:
        print(warning.format(), file=sys.stderr)
    return 0


def _inspect_measurement(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        measurement = load_measurement(args.metadata, schemas)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.write_report is not None:
        print(
            f"Measurement report: "
            f"{_write_yaml_report(args.write_report, measurement.to_dict())}"
        )
    print(f"Measurement valid: {measurement.identifier}")
    print(f"Data: {measurement.data_path}")
    print(f"Data SHA-256: {measurement.data_sha256}")
    for warning in measurement.warnings:
        print(warning.format(), file=sys.stderr)
    return 0


def _report(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        assembly = resolve_assembly(
            project.active_scenario,
            project.catalog,
            source=str(project.project_path),
        )
        report = build_phase0_report(project, assembly)
        report_data = report.to_dict()
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            report_data,
            "phase0_report.schema.json",
            source="generated phase0 report",
        )
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    output_path = _write_yaml_report(args.output, report_data)
    print(f"Phase 0 report: {output_path}")
    print(
        f"Confidence: {report.accuracy.confidence_level} "
        f"({report.accuracy.calibration_status})"
    )
    print(f"Energy ledger: {report.energy_ledger.status}")
    print(f"Convergence: {report.convergence.overall_status}")
    return 0


def _view(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        output_path = render_placement_view(project, args.output, dpi=args.dpi)
    except (ConfigError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"Placement view: {output_path}")
    return 0


def _review(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        assembly = resolve_assembly(
            project.active_scenario,
            project.catalog,
            source=str(project.project_path),
        )
        report = build_phase0_report(project, assembly)
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            report.to_dict(),
            "phase0_report.schema.json",
            source="generated Phase 0.1 review report",
        )
        html_path = args.output.resolve()
        image_path = html_path.with_name(f"{html_path.stem}_placement.png")
        render_placement_view(project, image_path, assembly, dpi=args.dpi)
        write_review_html(project, report, image_path, html_path)
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    print(f"Phase 0.1 review: {html_path}")
    print(f"Placement view: {image_path}")
    print(f"Hardware readiness: {report.accuracy.hardware_readiness}")
    return 0


def _beam(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        assembly = resolve_assembly(
            project.active_scenario,
            project.catalog,
            source=str(project.project_path),
        )
        beam = build_source_beam(project, assembly)
        maximum = (
            default_propagation_distance_m(project, assembly)
            if args.z_max_m is None
            else float(args.z_max_m)
        )
        profile_distance = (
            maximum
            if args.profile_distance_m is None
            else float(args.profile_distance_m)
        )
        report = build_phase1_beam_report(
            project,
            beam,
            z_max_m=maximum,
            sample_count=args.samples,
            profile_distance_m=profile_distance,
            grid_size=args.grid_size,
            extent_radii=args.extent_radii,
        )
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            report.to_dict(),
            "phase1_beam_report.schema.json",
            source="generated Phase 1 beam report",
        )
        summary_data = report.to_summary_dict()
        schemas.validate(
            summary_data,
            "phase1_beam_summary.schema.json",
            source="generated Phase 1 beam summary",
        )
        result_root = (
            project.project_path.parent / str(project.project.get("result_root", "../results"))
        ).resolve()
        timestamp = str(report.manifest["created_at_utc"])
        run_stamp = timestamp.replace("-", "").replace(":", "").replace(".", "")
        run_id = (
            f"{run_stamp}_{project.active_scenario['scenario_id']}_"
            f"{project.config_hash[:8]}"
        )
        run_directory = result_root / "phase1" / run_id
        if args.output is not None:
            report_target = args.output
            summary_target = args.summary or args.output.with_name(
                f"{args.output.stem}_summary.yaml"
            )
            plot_target = args.plot or args.output.with_name(f"{args.output.stem}_plot.png")
        elif args.plot is not None:
            plot_target = args.plot
            report_target = args.plot.with_name(f"{args.plot.stem}_report.yaml")
            summary_target = args.summary or args.plot.with_name(
                f"{args.plot.stem}_summary.yaml"
            )
        elif args.summary is not None:
            summary_target = args.summary
            report_target = args.summary.with_name(f"{args.summary.stem}_report.yaml")
            plot_target = args.summary.with_name(f"{args.summary.stem}_plot.png")
        else:
            report_target = run_directory / "beam_report.yaml"
            summary_target = run_directory / "beam_summary.yaml"
            plot_target = run_directory / "beam.png"
        report_path = _write_yaml_report(report_target, report.to_dict())
        summary_path = _write_yaml_report(summary_target, summary_data)
        plot_path = render_beam_view(
            beam,
            plot_target,
            z_max_m=maximum,
            sample_count=args.samples,
            profile_distance_m=profile_distance,
            grid_size=args.grid_size,
            extent_radii=args.extent_radii,
            dpi=args.dpi,
            hardware_readiness=report.accuracy["hardware_readiness"],
            paraxial_status=report.accuracy["paraxial_validity"]["status"],
        )
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    audit = report.profile_audit
    print(f"Phase 1 beam report: {report_path}")
    print(f"Beam summary: {summary_path}")
    print(f"Beam plot: {plot_path}")
    print(
        f"Profile: {beam.profile_kind}, propagation={beam.propagation_model}, "
        f"z_max_m={maximum:.9g}"
    )
    print(
        f"Radius at profile plane: x={audit['radius_x_m']:.9g} m, "
        f"y={audit['radius_y_m']:.9g} m"
    )
    print(
        f"Power integral: {audit['status']} "
        f"(relative error={audit['relative_power_error']:.3e})"
    )
    print(
        f"Overall: {report.summary['overall_status']} | "
        f"readiness={report.accuracy['hardware_readiness']} | "
        f"calibration={report.accuracy['calibration_status']}"
    )
    print(
        f"Internal consistency: {report.analytical_checks['status']} "
        f"(external validation={report.analytical_checks['external_validation_status']})"
    )
    for warning in project.warnings:
        print(warning.format(), file=sys.stderr)
    return 0


def _optical_train(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        report = build_phase2_optical_train_report(project)
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            report.to_dict(),
            "phase2_optical_train_report.schema.json",
            source="generated Phase 2 optical train report",
        )
        result_root = (
            project.project_path.parent / str(project.project.get("result_root", "../results"))
        ).resolve()
        timestamp = str(report.manifest["created_at_utc"])
        run_stamp = timestamp.replace("-", "").replace(":", "").replace(".", "")
        run_id = (
            f"{run_stamp}_{project.active_scenario['scenario_id']}_"
            f"{project.config_hash[:8]}"
        )
        run_directory = result_root / "phase2" / run_id
        if args.output is not None:
            report_target = args.output
            plot_target = args.plot or args.output.with_name(f"{args.output.stem}_plot.png")
        elif args.plot is not None:
            plot_target = args.plot
            report_target = args.plot.with_name(f"{args.plot.stem}_report.yaml")
        else:
            report_target = run_directory / "optical_train_report.yaml"
            plot_target = run_directory / "optical_train.png"
        report_path = _write_yaml_report(report_target, report.to_dict())
        plot_path = render_optical_train_view(report, plot_target, dpi=args.dpi)
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    summary = report.summary
    print(f"Phase 2 optical train report: {report_path}")
    print(f"Optical train plot: {plot_path}")
    print(
        f"Path: {summary['optical_path_id']} -> final={summary['final_plane']}, "
        f"radius=({summary['final_radius_x_m']:.9g}, {summary['final_radius_y_m']:.9g}) m"
    )
    print(
        f"Power: {summary['final_power_w']:.9g} W, "
        f"transmission={summary['total_transmission']:.9g}, "
        f"loss={summary['total_loss_w']:.3e} W"
    )
    print(
        f"Target/receiver: hits={summary['target_hit_count']}, "
        f"P_target={summary['estimated_power_on_target_w']:.9g} W, "
        f"P_rx={summary['estimated_received_power_w']:.9g} W, "
        f"link_loss_db={summary['link_loss_db']}"
    )
    print(
        f"Checks: q={summary['q_parameter_status']}, "
        f"energy={summary['energy_ledger_status']}, aperture={summary['aperture_status']}, "
        f"target={summary['target_footprint_status']}, "
        f"receiver={summary['receiver_return_status']}"
    )
    print(
        f"Overall: {summary['overall_status']} | "
        f"readiness={report.accuracy['hardware_readiness']} | "
        f"unsupported={summary['unsupported_element_count']}"
    )
    for warning in report.accuracy["warnings"]:
        print(warning, file=sys.stderr)
    return 0


def _scanner_sweep_angles(args: argparse.Namespace, project: Any) -> tuple[float, ...]:
    if args.angles_deg is not None:
        return tuple(math.radians(float(value)) for value in args.angles_deg)
    count = int(args.count)
    if count < 1:
        raise ValueError("--count는 1 이상이어야 합니다.")
    amplitude = float(project.active_scenario["scanner"].get("mechanical_amplitude_rad", 0.0))
    if args.start_deg is None and args.stop_deg is None:
        return default_static_sweep_angles(project, count=count)
    start_rad = -amplitude if args.start_deg is None else math.radians(float(args.start_deg))
    stop_rad = amplitude if args.stop_deg is None else math.radians(float(args.stop_deg))
    return tuple(float(value) for value in np.linspace(start_rad, stop_rad, count))


def _scanner_sweep(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        angles = _scanner_sweep_angles(args, project)
        result = run_static_scanner_angle_sweep(project, angles)
        result_data = result.to_dict()
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            result_data,
            "phase3_static_scanner_angle_sweep.schema.json",
            source="generated Phase 3 scanner sweep report",
        )
        report_path = _write_yaml_report(args.output, result_data)
        csv_target = args.csv or report_path.with_name(f"{report_path.stem}_table.csv")
        plot_target = args.plot or report_path.with_name(f"{report_path.stem}_plot.png")
        csv_path = write_scanner_sweep_csv(result, csv_target)
        plot_path = render_scanner_sweep_view(result, plot_target, dpi=args.dpi)
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    data = result.to_dict()
    summary = data["summary"]
    print(f"Scanner sweep report: {report_path}")
    print(f"Scanner sweep table: {csv_path}")
    print(f"Scanner sweep plot: {plot_path}")
    print(
        f"Samples: {summary['sample_count']}, hits={summary['target_hit_count']}, "
        f"positive_returns={summary['positive_return_count']}, "
        f"max_P_rx={summary['max_estimated_received_power_w']:.9g} W"
    )
    print(
        "Scope: static command-angle comparison only; scanner waveform/time dynamics "
        "are not simulated."
    )
    for warning in result.warnings:
        print(warning, file=sys.stderr)
    return 0


def _scanner_path(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        result = run_ideal_scanner_line_path(project, sample_count=args.samples)
        result_data = result.to_dict()
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            result_data,
            "phase3_ideal_scanner_line_path.schema.json",
            source="generated Phase 3 scanner path report",
        )
        report_path = _write_yaml_report(args.output, result_data)
        csv_target = args.csv or report_path.with_name(f"{report_path.stem}_table.csv")
        plot_target = args.plot or report_path.with_name(f"{report_path.stem}_plot.png")
        csv_path = write_scanner_path_csv(result, csv_target)
        plot_path = render_scanner_path_view(result, plot_target, dpi=args.dpi)
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    data = result.to_dict()
    summary = data["summary"]
    print(f"Scanner path report: {report_path}")
    print(f"Scanner path table: {csv_path}")
    print(f"Scanner path plot: {plot_path}")
    print(
        f"Waveform: {result.waveform}, samples={summary['target_hit_count']}/"
        f"{result.sample_count} hits, positive_returns={summary['positive_return_count']}, "
        f"line_duration={result.line_duration_s:.9g} s"
    )
    print(
        "Scope: ideal forward-line command path only; scanner dynamics/calibration "
        "are not simulated."
    )
    for warning in result.warnings:
        print(warning, file=sys.stderr)
    return 0


def _workspace(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        report = build_phase2_optical_train_report(project)
        scene = build_viewport_scene(project, report=report)
        scene_data = scene.to_dict()
        if args.write_scene is not None:
            scene_path = _write_yaml_report(args.write_scene, scene_data)
        else:
            scene_path = None
        plot_path = render_viewport_scene(scene, args.output, dpi=args.dpi)
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    print(f"Optical assembly workspace: {plot_path}")
    if scene_path is not None:
        print(f"Viewport scene: {scene_path}")
    print(
        f"Scene: components={len(scene.components)}, ports={len(scene.ports)}, "
        f"guides={len(scene.guides)}, rays={len(scene.rays)}, "
        f"footprints={len(scene.footprints)}"
    )
    print(
        "Source of truth: config/report driven; UI placement edits must be saved "
        "back to config variants."
    )
    for warning in scene.warnings:
        print(warning, file=sys.stderr)
    return 0


def _dashboard(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
        report = build_phase2_optical_train_report(project)
        schemas = SchemaStore.load(schema_directory_for_project(project.project_path))
        schemas.validate(
            report.to_dict(),
            "phase2_optical_train_report.schema.json",
            source="generated Phase 2 dashboard report",
        )
        scene = build_viewport_scene(project, report=report)
        html_path = args.output.resolve()
        report_target = args.report or html_path.with_name(f"{html_path.stem}_phase2_report.yaml")
        scene_target = args.write_scene or html_path.with_name(f"{html_path.stem}_viewport_scene.yaml")
        workspace_target = args.workspace_plot or html_path.with_name(
            f"{html_path.stem}_workspace.png"
        )
        train_target = args.train_plot or html_path.with_name(f"{html_path.stem}_optical_train.png")
        report_path = _write_yaml_report(report_target, report.to_dict())
        scene_path = _write_yaml_report(scene_target, scene.to_dict())
        workspace_path = render_viewport_scene(scene, workspace_target, dpi=args.dpi)
        train_path = render_optical_train_view(report, train_target, dpi=args.dpi)
        scanner_path_result = None
        scanner_path_report_path = None
        scanner_path_csv_path = None
        scanner_path_plot_path = None
        if args.include_scanner_path:
            scanner_path_result = run_ideal_scanner_line_path(
                project,
                sample_count=args.scanner_path_samples,
            )
            scanner_path_data = scanner_path_result.to_dict()
            schemas.validate(
                scanner_path_data,
                "phase3_ideal_scanner_line_path.schema.json",
                source="generated dashboard scanner path report",
            )
            scanner_path_report_target = args.scanner_path_report or html_path.with_name(
                f"{html_path.stem}_scanner_path.yaml"
            )
            scanner_path_csv_target = args.scanner_path_csv or html_path.with_name(
                f"{html_path.stem}_scanner_path.csv"
            )
            scanner_path_plot_target = args.scanner_path_plot or html_path.with_name(
                f"{html_path.stem}_scanner_path.png"
            )
            scanner_path_report_path = _write_yaml_report(
                scanner_path_report_target,
                scanner_path_data,
            )
            scanner_path_csv_path = write_scanner_path_csv(
                scanner_path_result,
                scanner_path_csv_target,
            )
            scanner_path_plot_path = render_scanner_path_view(
                scanner_path_result,
                scanner_path_plot_target,
                dpi=args.dpi,
            )
        dashboard_path = write_workspace_dashboard_html(
            project=project,
            report=report,
            scene=scene,
            workspace_image=workspace_path,
            optical_train_image=train_path,
            output_path=html_path,
            report_path=report_path,
            scene_path=scene_path,
            scanner_path=scanner_path_result,
            scanner_path_image=scanner_path_plot_path,
            scanner_path_report_path=scanner_path_report_path,
            scanner_path_csv_path=scanner_path_csv_path,
        )
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    print(f"Workspace dashboard: {dashboard_path}")
    print(f"Phase 2 report: {report_path}")
    print(f"Viewport scene: {scene_path}")
    print(f"Workspace plot: {workspace_path}")
    print(f"Optical train plot: {train_path}")
    if args.include_scanner_path:
        print(f"Scanner path report: {scanner_path_report_path}")
        print(f"Scanner path table: {scanner_path_csv_path}")
        print(f"Scanner path plot: {scanner_path_plot_path}")
    print(
        f"Summary: status={report.summary['overall_status']}, "
        f"P_rx={report.summary['estimated_received_power_w']:.9g} W, "
        f"link_loss_db={report.summary['link_loss_db']}"
    )
    for warning in report.accuracy["warnings"]:
        print(warning, file=sys.stderr)
    return 0


def _placement_variant(args: argparse.Namespace) -> int:
    try:
        result = create_placement_variant(
            project_path=args.project,
            element_id=args.element,
            scenario_id=args.scenario_id,
            scenario_output=args.scenario_output,
            project_output=args.project_output,
            translation_m=None if args.translation_m is None else tuple(args.translation_m),
            quaternion_wxyz=(
                None if args.quaternion_wxyz is None else tuple(args.quaternion_wxyz)
            ),
            axial_gap_m=args.axial_gap_m,
            transverse_offset_m=(
                None
                if args.transverse_offset_m is None
                else tuple(args.transverse_offset_m)
            ),
            clocking_rad=args.clocking_rad,
            angular_misalignment_rad=(
                None
                if args.angular_misalignment_rad is None
                else tuple(args.angular_misalignment_rad)
            ),
            overwrite=bool(args.overwrite),
        )
        project = load_project(result.project_path)
    except (ConfigError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    print(f"Placement variant scenario: {result.scenario_path}")
    print(f"Placement variant project: {result.project_path}")
    print(f"Scenario ID: {result.scenario_id}")
    print(f"Edited element: {result.element_id}")
    print(f"Changed fields: {', '.join(result.changed_fields)}")
    print(f"Variant config valid: {project.project['project_id']}")
    print(
        "Next: "
        f"lidarsim dashboard {result.project_path} "
        f"--output {result.project_path.with_suffix('').with_name(result.project_path.stem + '_dashboard.html')}"
    )
    for warning in project.warnings:
        print(warning.format(), file=sys.stderr)
    return 0


def _ui(args: argparse.Namespace) -> int:
    if importlib.util.find_spec("streamlit") is None:
        print(
            'Streamlit UI dependency가 없습니다. python -m pip install -e ".[ui]"를 실행하세요.',
            file=sys.stderr,
        )
        return 2
    project_path = Path(args.project).resolve()
    app_path = Path(__file__).resolve().parent / "ui" / "app.py"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        f"--server.port={int(args.port)}",
        f"--server.headless={'true' if args.headless else 'false'}",
        "--",
        str(project_path),
    ]
    environment = dict(os.environ)
    environment["LIDARSIM_UI_PROJECT"] = str(project_path)
    try:
        completed = subprocess.run(command, env=environment, check=False)
    except OSError as exc:
        print(f"Streamlit UI를 시작할 수 없습니다: {exc}", file=sys.stderr)
        return 2
    return int(completed.returncode)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested CLI command."""

    args = _parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args)
    if args.command == "placement":
        return _placement(args)
    if args.command == "inspect-mesh":
        return _inspect_mesh(args)
    if args.command == "inspect-measurement":
        return _inspect_measurement(args)
    if args.command == "report":
        return _report(args)
    if args.command == "view":
        return _view(args)
    if args.command == "review":
        return _review(args)
    if args.command == "beam":
        return _beam(args)
    if args.command in {"optical-train", "train"}:
        return _optical_train(args)
    if args.command == "workspace":
        return _workspace(args)
    if args.command == "dashboard":
        return _dashboard(args)
    if args.command == "scanner-sweep":
        return _scanner_sweep(args)
    if args.command == "scanner-path":
        return _scanner_path(args)
    if args.command == "placement-variant":
        return _placement_variant(args)
    if args.command == "ui":
        return _ui(args)
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
