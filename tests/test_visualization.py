from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lidarsim.config import load_project
from lidarsim.geometry import resolve_assembly
from lidarsim.visualization import render_placement_view
from lidarsim.visualization.placement import _receiver_fov_directions, _scanner_geometry


def test_headless_placement_view_writes_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    output_path = tmp_path / "placement.png"

    result = render_placement_view(project, output_path, dpi=72)

    assert result == output_path.resolve()
    payload = output_path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 10_000


def test_scanner_guides_apply_twice_the_mechanical_angle(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    assembly = resolve_assembly(project.active_scenario, project.catalog)

    _, polygon, normal, directions = _scanner_geometry(
        project,
        project.active_scenario,
        assembly,
    )

    assert polygon.shape == (4, 3)
    assert np.linalg.norm(normal) == pytest.approx(1.0)
    assert directions[1] == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)
    assert abs(directions[0][2]) == pytest.approx(np.sin(np.deg2rad(10.0)), abs=1e-12)
    assert directions[0][2] == pytest.approx(-directions[2][2], abs=1e-12)


def test_receiver_fov_guides_use_half_of_full_fov(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    directions = _receiver_fov_directions(project.active_scenario["receiver"])

    look = np.asarray(project.active_scenario["receiver"]["direction"])
    expected_cosine = np.cos(project.active_scenario["receiver"]["full_fov_rad"] / 2.0)
    assert len(directions) == 12
    assert all(np.dot(direction, look) == pytest.approx(expected_cosine) for direction in directions)
