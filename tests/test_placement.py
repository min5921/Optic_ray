from __future__ import annotations

import math
from pathlib import Path

import pytest

from lidarsim.config import load_project
from lidarsim.config.immutable import deep_thaw
from lidarsim.errors import ConfigValidationError
from lidarsim.geometry import OpticalPort, resolve_assembly


def test_optical_port_builds_right_handed_local_frame() -> None:
    port = OpticalPort.from_mapping(
        {
            "id": "output",
            "role": "output",
            "origin_local_m": (1.0, 2.0, 3.0),
            "propagation_axis_local": (0.0, 0.0, 2.0),
            "transverse_x_local": (3.0, 0.0, 1.0),
        }
    )

    assert port.T_component_from_port.translation_m == pytest.approx((1.0, 2.0, 3.0))
    assert port.T_component_from_port.rotation[:, 0] == pytest.approx((1.0, 0.0, 0.0))
    assert port.T_component_from_port.rotation[:, 1] == pytest.approx((0.0, 1.0, 0.0))
    assert port.T_component_from_port.rotation[:, 2] == pytest.approx((0.0, 0.0, 1.0))


def test_baseline_port_placement_resolves_world_position_and_axis(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    assembly = resolve_assembly(project.active_scenario, project.catalog)

    assert assembly["source"].T_world_from_component.translation_m == pytest.approx(
        (0.0, 0.0, -0.1)
    )
    assert assembly["collimator"].T_world_from_component.translation_m == pytest.approx(
        (0.0, 0.0, -0.08)
    )
    source_output = assembly["source"].world_from_port("output")
    collimator_input = assembly["collimator"].world_from_port("input")
    assert collimator_input.translation_m - source_output.translation_m == pytest.approx(
        (0.0, 0.0, 0.02)
    )
    assert source_output.rotation[:, 2] == pytest.approx((0.0, 0.0, 1.0))
    assert collimator_input.rotation[:, 2] == pytest.approx((0.0, 0.0, 1.0))


def test_port_offset_and_clocking_are_applied_in_upstream_port_frame(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scenario = deep_thaw(project.active_scenario)
    placement = scenario["optical_assembly"]["elements"][1]["placement"]
    placement["transverse_offset_m"] = [0.001, -0.002]
    placement["clocking_rad"] = math.pi / 2.0

    assembly = resolve_assembly(scenario, project.catalog)
    collimator = assembly["collimator"]

    assert collimator.T_world_from_component.translation_m == pytest.approx(
        (0.001, -0.002, -0.08)
    )
    assert collimator.world_from_port("input").rotation[:, 0] == pytest.approx(
        (0.0, 1.0, 0.0), abs=1e-12
    )


def test_port_dependency_cycle_is_rejected(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scenario = deep_thaw(project.active_scenario)
    scenario["optical_assembly"]["elements"][0]["placement"] = {
        "mode": "port",
        "connect_from": "collimator.output",
        "connect_to": "source.output",
    }

    with pytest.raises(ConfigValidationError, match="dependency"):
        resolve_assembly(scenario, project.catalog)
