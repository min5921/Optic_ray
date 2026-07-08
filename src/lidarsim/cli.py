"""Command-line entry point for configuration validation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml

from lidarsim.assets import load_measurement, load_stl_asset
from lidarsim.beam import build_source_beam, default_propagation_distance_m
from lidarsim.config import load_project
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
from lidarsim.visualization import (
    render_beam_view,
    render_optical_train_view,
    render_placement_view,
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
        help="run Phase 2 source-to-collimator optical train propagation",
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
        schemas = SchemaStore.load(project.project_path.parent.parent / "schemas")
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
        schemas = SchemaStore.load(project.project_path.parent.parent / "schemas")
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
        schemas = SchemaStore.load(project.project_path.parent.parent / "schemas")
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
        schemas = SchemaStore.load(project.project_path.parent.parent / "schemas")
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
        schemas = SchemaStore.load(project.project_path.parent.parent / "schemas")
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
        schemas = SchemaStore.load(project.project_path.parent.parent / "schemas")
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
        f"Checks: q={summary['q_parameter_status']}, "
        f"energy={summary['energy_ledger_status']}, aperture={summary['aperture_status']}"
    )
    print(
        f"Overall: {summary['overall_status']} | "
        f"readiness={report.accuracy['hardware_readiness']} | "
        f"unsupported={summary['unsupported_element_count']}"
    )
    for warning in report.accuracy["warnings"]:
        print(warning, file=sys.stderr)
    return 0


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
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
