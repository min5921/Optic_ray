"""Resolved scenario와 placement에서 source BeamState를 생성한다."""

from __future__ import annotations

from typing import Any

from lidarsim.beam.gaussian import BeamState
from lidarsim.geometry import AssemblyPlacement, resolve_assembly


def _source_output_port(element: Any) -> str:
    candidates = [
        port_id
        for port_id, port in element.ports.items()
        if port.role in {"output", "bidirectional"}
    ]
    waist_ports = [
        port_id
        for port_id in candidates
        if element.ports[port_id].reference_plane == "source_waist"
    ]
    selected = waist_ports or candidates
    if len(selected) != 1:
        raise ValueError(
            f"Source element {element.element_id!r}의 output reference port를 하나로 결정할 수 없습니다."
        )
    return selected[0]


def build_source_beam(
    project: Any,
    assembly: AssemblyPlacement | None = None,
) -> BeamState:
    """Active scenario의 authoritative source operating point를 BeamState로 만든다."""

    scenario = project.active_scenario
    source = scenario["source"]
    if source["type"] == "measured_profile":
        raise ValueError(
            "measured_profile propagation은 아직 구현되지 않았습니다. "
            "Phase 1 Gaussian source 또는 향후 measured-transfer loader를 사용하세요."
        )
    resolved_assembly = assembly or resolve_assembly(
        scenario,
        project.catalog,
        source=str(project.project_path),
    )
    source_element_id = str(source["element_id"])
    element = resolved_assembly[source_element_id]
    port_id = _source_output_port(element)
    world_from_port = element.world_from_port(port_id)

    if source["type"] == "fiber_gaussian":
        waist_x = waist_y = float(source["mode_field_diameter_m"]) / 2.0
    else:
        waist_x = float(source["waist_radius_x_m"])
        waist_y = float(source["waist_radius_y_m"])

    optical_path_id = None
    for path in scenario["optical_assembly"]["optical_paths"]:
        if source_element_id in path["elements"]:
            optical_path_id = str(path["id"])
            break

    return BeamState(
        time_s=0.0,
        origin_m=world_from_port.translation_m,
        direction=world_from_port.rotation[:, 2],
        transverse_x_axis=world_from_port.rotation[:, 0],
        wavelength_m=float(source["wavelength_m"]),
        power_w=float(source["optical_power_w"]),
        waist_radius_x_m=waist_x,
        waist_radius_y_m=waist_y,
        m2_x=float(source.get("m2_x", 1.0)),
        m2_y=float(source.get("m2_y", 1.0)),
        profile_kind=str(source["profile_kind"]),
        propagation_model=str(source["propagation_model"]),
        polarization=str(source.get("polarization", "scalar_unspecified")),
        distance_from_waist_m=-float(source.get("waist_offset_m", 0.0)),
        source_component_id=source_element_id,
        source_component_ref=element.component_ref,
        optical_path_id=optical_path_id,
    )


def default_propagation_distance_m(
    project: Any,
    assembly: AssemblyPlacement | None = None,
) -> float:
    """Source에서 첫 downstream element까지의 geometric distance를 반환한다."""

    scenario = project.active_scenario
    resolved_assembly = assembly or resolve_assembly(
        scenario,
        project.catalog,
        source=str(project.project_path),
    )
    source_id = str(scenario["source"]["element_id"])
    source_position = build_source_beam(project, resolved_assembly).origin_m
    for path in scenario["optical_assembly"]["optical_paths"]:
        elements = [str(value) for value in path["elements"]]
        if source_id not in elements:
            continue
        index = elements.index(source_id)
        if index + 1 < len(elements):
            next_position = resolved_assembly[elements[index + 1]].T_world_from_component.translation_m
            distance = float(((next_position - source_position) ** 2).sum() ** 0.5)
            if distance > 0.0:
                return distance
    return 1.0
