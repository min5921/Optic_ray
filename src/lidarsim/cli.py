"""Command-line entry point for configuration validation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml

from lidarsim.config import load_project
from lidarsim.errors import ConfigError


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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested CLI command."""

    args = _parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args)
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
