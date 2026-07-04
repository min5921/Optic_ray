"""Absolute·port-to-port optical assembly placement 계산."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np

from lidarsim.catalog.loader import Catalog
from lidarsim.errors import ConfigValidationError, Diagnostic
from lidarsim.geometry.ports import OpticalPort
from lidarsim.geometry.transform import RigidTransform


@dataclass(frozen=True, slots=True)
class PlacedElement:
    """World frame에 배치된 component instance."""

    element_id: str
    component_ref: str
    T_world_from_component: RigidTransform
    ports: Mapping[str, OpticalPort]

    def world_from_port(self, port_id: str) -> RigidTransform:
        """해당 port frame에서 world frame으로 가는 transform을 반환한다."""

        try:
            port = self.ports[port_id]
        except KeyError as exc:
            raise KeyError(f"Element {self.element_id!r}에 port {port_id!r}가 없습니다.") from exc
        return self.T_world_from_component @ port.T_component_from_port


@dataclass(frozen=True, slots=True)
class AssemblyPlacement:
    """배치가 resolve된 immutable optical assembly."""

    elements: Mapping[str, PlacedElement]

    def __getitem__(self, element_id: str) -> PlacedElement:
        return self.elements[element_id]

    def to_dict(self) -> dict[str, Any]:
        """YAML·JSON report용 serializable mapping을 반환한다."""

        result: dict[str, Any] = {"elements": {}}
        for element_id, element in self.elements.items():
            ports: dict[str, Any] = {}
            for port_id in element.ports:
                world_from_port = element.world_from_port(port_id)
                ports[port_id] = {
                    "role": element.ports[port_id].role,
                    "interface_type": element.ports[port_id].interface_type,
                    "reference_plane": element.ports[port_id].reference_plane,
                    "origin_world_m": world_from_port.translation_m.tolist(),
                    "propagation_axis_world": world_from_port.rotation[:, 2].tolist(),
                    "transverse_x_world": world_from_port.rotation[:, 0].tolist(),
                }
            result["elements"][element_id] = {
                "component_ref": element.component_ref,
                "translation_world_m": element.T_world_from_component.translation_m.tolist(),
                "rotation_world_from_component": element.T_world_from_component.rotation.tolist(),
                "ports": ports,
            }
        return result


def _split_port_reference(reference: str) -> tuple[str, str]:
    element_id, separator, port_id = reference.rpartition(".")
    if not separator or not element_id or not port_id:
        raise ValueError(f"Port reference는 'element_id.port_id' 형식이어야 합니다: {reference!r}")
    return element_id, port_id


def _component_ports(component_ref: str, catalog: Catalog) -> Mapping[str, OpticalPort]:
    ports: dict[str, OpticalPort] = {}
    for raw_port in catalog[component_ref].ports:
        port = OpticalPort.from_mapping(raw_port)
        if port.identifier in ports:
            raise ValueError(f"Component {component_ref!r}에 중복 port {port.identifier!r}가 있습니다.")
        ports[port.identifier] = port
    return MappingProxyType(ports)


def _absolute_transform(placement: Mapping[str, Any]) -> RigidTransform:
    quaternion = placement.get("quaternion_wxyz", (1.0, 0.0, 0.0, 0.0))
    return RigidTransform.from_quaternion_wxyz(quaternion, placement["translation_m"])


def _port_offset_transform(placement: Mapping[str, Any]) -> RigidTransform:
    transverse = placement.get("transverse_offset_m", (0.0, 0.0))
    if len(transverse) != 2:
        raise ValueError("transverse_offset_m은 두 값으로 구성되어야 합니다.")
    angular = placement.get("angular_misalignment_rad", (0.0, 0.0))
    if len(angular) != 2:
        raise ValueError("angular_misalignment_rad는 두 값으로 구성되어야 합니다.")
    clocking = float(placement.get("clocking_rad", 0.0))
    rotation_x = RigidTransform.from_axis_angle((1.0, 0.0, 0.0), float(angular[0]))
    rotation_y = RigidTransform.from_axis_angle((0.0, 1.0, 0.0), float(angular[1]))
    rotation_z = RigidTransform.from_axis_angle((0.0, 0.0, 1.0), clocking)
    rotation = rotation_z @ rotation_y @ rotation_x
    translation = np.array(
        [float(transverse[0]), float(transverse[1]), float(placement.get("axial_gap_m", 0.0))],
        dtype=np.float64,
    )
    return RigidTransform(rotation.rotation, translation)


def _check_port_roles(
    source_port: OpticalPort,
    target_port: OpticalPort,
    *,
    source: str,
    path: str,
) -> None:
    diagnostics: list[Diagnostic] = []
    if source_port.role not in {"output", "bidirectional"}:
        diagnostics.append(
            Diagnostic(
                source=source,
                path=f"{path}.connect_from",
                message=f"Upstream port role은 output 또는 bidirectional이어야 합니다: {source_port.role!r}",
            )
        )
    if target_port.role not in {"input", "bidirectional"}:
        diagnostics.append(
            Diagnostic(
                source=source,
                path=f"{path}.connect_to",
                message=f"Target port role은 input 또는 bidirectional이어야 합니다: {target_port.role!r}",
            )
        )
    if (
        source_port.interface_type != "unspecified"
        and target_port.interface_type != "unspecified"
        and source_port.interface_type != target_port.interface_type
    ):
        diagnostics.append(
            Diagnostic(
                source=source,
                path=path,
                message=(
                    f"Port interface가 호환되지 않습니다: {source_port.interface_type!r} -> "
                    f"{target_port.interface_type!r}"
                ),
                hint="Free-space port와 fiber connector를 rigid optical placement로 직접 연결하지 마세요.",
            )
        )
    if diagnostics:
        raise ConfigValidationError(diagnostics)


def resolve_assembly(
    scenario: Mapping[str, Any],
    catalog: Catalog,
    *,
    source: str = "<resolved scenario>",
) -> AssemblyPlacement:
    """Scenario element의 absolute·port placement를 world transform으로 resolve한다."""

    raw_elements = list(scenario["optical_assembly"]["elements"])
    element_specs = {str(element["id"]): element for element in raw_elements}
    port_maps: dict[str, Mapping[str, OpticalPort]] = {}
    diagnostics: list[Diagnostic] = []

    for index, element in enumerate(raw_elements):
        element_id = str(element["id"])
        component_ref = str(element["component_ref"])
        try:
            port_maps[element_id] = _component_ports(component_ref, catalog)
        except (KeyError, ValueError) as exc:
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path=f"optical_assembly.elements[{index}].component_ref",
                    message=str(exc),
                )
            )
    if diagnostics:
        raise ConfigValidationError(diagnostics)

    placed: dict[str, PlacedElement] = {}
    pending: dict[str, Mapping[str, Any]] = {}
    for index, element in enumerate(raw_elements):
        element_id = str(element["id"])
        component_ref = str(element["component_ref"])
        placement = element["placement"]
        if placement["mode"] == "absolute":
            try:
                transform = _absolute_transform(placement)
            except ValueError as exc:
                diagnostics.append(
                    Diagnostic(
                        source=source,
                        path=f"optical_assembly.elements[{index}].placement",
                        message=str(exc),
                    )
                )
                continue
            placed[element_id] = PlacedElement(
                element_id=element_id,
                component_ref=component_ref,
                T_world_from_component=transform,
                ports=port_maps[element_id],
            )
        else:
            pending[element_id] = element
    if diagnostics:
        raise ConfigValidationError(diagnostics)

    while pending:
        progress = False
        for element_id in list(pending):
            element = pending[element_id]
            placement = element["placement"]
            index = raw_elements.index(element)
            path = f"optical_assembly.elements[{index}].placement"
            try:
                upstream_id, upstream_port_id = _split_port_reference(str(placement["connect_from"]))
                target_id, target_port_id = _split_port_reference(str(placement["connect_to"]))
            except ValueError as exc:
                diagnostics.append(Diagnostic(source=source, path=path, message=str(exc)))
                del pending[element_id]
                progress = True
                continue
            if upstream_id not in placed:
                continue
            if target_id != element_id:
                diagnostics.append(
                    Diagnostic(
                        source=source,
                        path=f"{path}.connect_to",
                        message="connect_to는 현재 배치하는 element의 port여야 합니다.",
                    )
                )
                del pending[element_id]
                progress = True
                continue

            upstream = placed[upstream_id]
            try:
                source_port = upstream.ports[upstream_port_id]
                target_port = port_maps[element_id][target_port_id]
                _check_port_roles(source_port, target_port, source=source, path=path)
                T_world_from_upstream_port = upstream.world_from_port(upstream_port_id)
                T_upstream_port_from_target_port = _port_offset_transform(placement)
                T_component_from_target_port = target_port.T_component_from_port
                T_world_from_component = (
                    T_world_from_upstream_port
                    @ T_upstream_port_from_target_port
                    @ T_component_from_target_port.inverse()
                )
            except (KeyError, ValueError) as exc:
                diagnostics.append(Diagnostic(source=source, path=path, message=str(exc)))
                del pending[element_id]
                progress = True
                continue

            placed[element_id] = PlacedElement(
                element_id=element_id,
                component_ref=str(element["component_ref"]),
                T_world_from_component=T_world_from_component,
                ports=port_maps[element_id],
            )
            del pending[element_id]
            progress = True

        if diagnostics:
            raise ConfigValidationError(diagnostics)
        if not progress:
            unresolved = ", ".join(sorted(pending))
            dependencies = ", ".join(
                f"{element_id}->{element['placement']['connect_from']}"
                for element_id, element in sorted(pending.items())
            )
            raise ConfigValidationError(
                [
                    Diagnostic(
                        source=source,
                        path="optical_assembly.elements",
                        message=f"Port placement dependency를 resolve할 수 없습니다: {unresolved}",
                        hint=f"Cycle 또는 배치되지 않은 upstream element를 확인하세요: {dependencies}",
                    )
                ]
            )

    ordered = {str(element["id"]): placed[str(element["id"])] for element in raw_elements}
    return AssemblyPlacement(elements=MappingProxyType(ordered))
