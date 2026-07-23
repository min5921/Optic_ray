"""Resolved assembly 기반 transmitter optical train propagation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from lidarsim.beam import BeamState, build_source_beam
from lidarsim.geometry import AssemblyPlacement, resolve_assembly
from lidarsim.geometry.transform import normalize_vector
from lidarsim.optics.abcd import ABCDMatrix, apply_abcd_to_beam
from lidarsim.optics.aperture import ApertureClipResult, circular_aperture_clip
from lidarsim.optics.mirror import interact_flat_mirror


def _loss_db(input_power_w: float, output_power_w: float) -> float | None:
    if input_power_w <= 0.0 or output_power_w <= 0.0:
        return None
    value = -10.0 * math.log10(output_power_w / input_power_w)
    return 0.0 if abs(value) <= 1e-15 else value


@dataclass(frozen=True, slots=True)
class PowerLedgerEntry:
    optical_path_id: str
    element_id: str
    component_ref: str
    mechanism: str
    input_power_w: float
    output_power_w: float
    loss_w: float
    loss_db: float | None
    transmission_fraction: float
    model_source: str
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "optical_path_id": self.optical_path_id,
            "element_id": self.element_id,
            "component_ref": self.component_ref,
            "mechanism": self.mechanism,
            "input_power_w": self.input_power_w,
            "output_power_w": self.output_power_w,
            "loss_w": self.loss_w,
            "loss_db": self.loss_db,
            "transmission_fraction": self.transmission_fraction,
            "model_source": self.model_source,
            "warning": self.warning,
        }


@dataclass(frozen=True, slots=True)
class BeamPlane:
    label: str
    element_id: str
    component_ref: str
    port_id: str | None
    plane_role: str
    distance_along_path_m: float
    state: BeamState

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "element_id": self.element_id,
            "component_ref": self.component_ref,
            "port_id": self.port_id,
            "plane_role": self.plane_role,
            "distance_along_path_m": self.distance_along_path_m,
            "beam_state": self.state.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class OpticalTrainResult:
    optical_path_id: str
    element_sequence: tuple[str, ...]
    states: tuple[BeamPlane, ...]
    power_ledger: tuple[PowerLedgerEntry, ...]
    component_reports: tuple[dict[str, Any], ...]
    unsupported_elements: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]

    @property
    def final_state(self) -> BeamPlane:
        return self.states[-1]

    @property
    def total_transmission(self) -> float:
        if not self.power_ledger:
            return 1.0
        input_power = self.power_ledger[0].input_power_w
        output_power = self.power_ledger[-1].output_power_w
        if input_power <= 0.0:
            return 0.0
        return output_power / input_power

    @property
    def total_loss_w(self) -> float:
        if not self.power_ledger:
            return 0.0
        return self.power_ledger[0].input_power_w - self.power_ledger[-1].output_power_w

    def to_dict(self) -> dict[str, Any]:
        return {
            "optical_path_id": self.optical_path_id,
            "element_sequence": list(self.element_sequence),
            "states": [state.to_dict() for state in self.states],
            "power_ledger": [entry.to_dict() for entry in self.power_ledger],
            "component_reports": list(self.component_reports),
            "unsupported_elements": list(self.unsupported_elements),
            "warnings": list(self.warnings),
        }


def _path_containing_source(scenario: Any) -> tuple[str, tuple[str, ...]]:
    source_id = str(scenario["source"]["element_id"])
    for path in scenario["optical_assembly"]["optical_paths"]:
        elements = tuple(str(value) for value in path["elements"])
        if source_id in elements:
            return str(path["id"]), elements[elements.index(source_id) :]
    raise ValueError(f"source element {source_id!r}를 포함한 optical path가 없습니다.")


def _preferred_port(element: Any, role: str) -> str:
    candidates = [
        port_id
        for port_id, port in element.ports.items()
        if port.role in {role, "bidirectional"}
    ]
    if role in candidates:
        return role
    if len(candidates) != 1:
        raise ValueError(
            f"Element {element.element_id!r}의 {role} port를 하나로 결정할 수 없습니다."
        )
    return candidates[0]


def _input_reference_plane(element: Any) -> tuple[str | None, Any, str]:
    """입력 port가 있으면 port plane, 없으면 component origin을 반환한다."""

    if element.ports:
        port_id = _preferred_port(element, "input")
        return port_id, element.world_from_port(port_id), "element_input"
    return None, element.T_world_from_component, "component_origin"


def _axial_distance_to_port(beam: BeamState, port_transform: Any) -> tuple[float, float]:
    delta = port_transform.translation_m - beam.origin_m
    axial = float(np.dot(delta, beam.direction))
    transverse = float(np.linalg.norm(delta - axial * beam.direction))
    if axial < -1e-12:
        raise ValueError("다음 optical element가 현재 beam 진행 방향의 뒤쪽에 있습니다.")
    return max(axial, 0.0), transverse


def _append_free_space(
    *,
    current: BeamState,
    distance_m: float,
    optical_path_id: str,
    element_id: str,
    component_ref: str,
    ledger: list[PowerLedgerEntry],
) -> BeamState:
    propagated = current.propagate_free_space(distance_m)
    ledger.append(
        PowerLedgerEntry(
            optical_path_id=optical_path_id,
            element_id=element_id,
            component_ref=component_ref,
            mechanism="free_space_propagation",
            input_power_w=current.power_w,
            output_power_w=propagated.power_w,
            loss_w=0.0,
            loss_db=0.0,
            transmission_fraction=1.0,
            model_source="ABCD free-space q-parameter",
        )
    )
    return propagated


def _collimator_report(
    *,
    optical_path_id: str,
    element_id: str,
    component_ref: str,
    component: Any,
    before_lens: BeamState,
    output_origin_m: Any,
    output_direction: Any,
    output_x_axis: Any,
    ledger: list[PowerLedgerEntry],
) -> tuple[BeamState, dict[str, Any]]:
    optical = component["optical"]
    model = str(optical["model"])
    if model != "ideal_thin_lens":
        raise ValueError(f"지원하지 않는 collimator model입니다: {model!r}")

    aperture = circular_aperture_clip(
        before_lens,
        aperture_diameter_m=float(optical["clear_aperture_diameter_m"]),
    )
    after_aperture_power = aperture.output_power_w
    ledger.append(
        PowerLedgerEntry(
            optical_path_id=optical_path_id,
            element_id=element_id,
            component_ref=component_ref,
            mechanism="circular_aperture_clipping",
            input_power_w=aperture.input_power_w,
            output_power_w=after_aperture_power,
            loss_w=aperture.loss_w,
            loss_db=aperture.loss_db,
            transmission_fraction=aperture.transmission_fraction,
            model_source=aperture.method,
            warning=(
                "Clipping 뒤 diffraction/truncated profile shape는 아직 계산하지 않고 "
                "Gaussian power loss로만 반영합니다."
            ),
        )
    )

    surface_transmission = float(optical["power_transmission"])
    after_transmission_power = after_aperture_power * surface_transmission
    ledger.append(
        PowerLedgerEntry(
            optical_path_id=optical_path_id,
            element_id=element_id,
            component_ref=component_ref,
            mechanism="component_power_transmission",
            input_power_w=after_aperture_power,
            output_power_w=after_transmission_power,
            loss_w=after_aperture_power - after_transmission_power,
            loss_db=_loss_db(after_aperture_power, after_transmission_power),
            transmission_fraction=surface_transmission,
            model_source="catalog optical.power_transmission",
        )
    )

    total_transmission = aperture.transmission_fraction * surface_transmission
    lens = ABCDMatrix.thin_lens(float(optical["effective_focal_length_m"]))
    after_lens = apply_abcd_to_beam(
        before_lens,
        lens,
        origin_m=output_origin_m,
        direction=output_direction,
        transverse_x_axis=output_x_axis,
        power_transmission=total_transmission,
    )
    report = {
        "element_id": element_id,
        "component_ref": component_ref,
        "component_type": str(component["component_type"]),
        "model": model,
        "model_level": str(component["model_level"]),
        "abcd_matrix": lens.as_nested_list(),
        "effective_focal_length_m": float(optical["effective_focal_length_m"]),
        "clear_aperture_diameter_m": float(optical["clear_aperture_diameter_m"]),
        "aperture_clip": aperture.to_dict(),
        "power_transmission": surface_transmission,
        "input_beam_state": before_lens.to_dict(),
        "output_beam_state": after_lens.to_dict(),
        "assumptions": [
            "Ideal zero-thickness thin lens입니다.",
            "Beam center가 aperture 중심과 일치한다고 가정합니다.",
            "Aberration, diffraction, coating spectral curve와 decenter/tilt sensitivity는 계산하지 않습니다.",
        ],
    }
    return after_lens, report


def _mirror_aperture_axes(element: Any, component: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scanner mirror catalog의 local normal/axis를 world aperture axes로 변환한다."""

    mechanical = component["mechanical"]
    rotation = element.T_world_from_component.rotation
    normal = normalize_vector(
        rotation @ np.asarray(mechanical["surface_normal_local"], dtype=np.float64),
        name="mirror surface normal",
    )
    rotation_axis = normalize_vector(
        rotation @ np.asarray(mechanical["default_rotation_axis_local"], dtype=np.float64),
        name="mirror rotation axis",
    )
    aperture_y = normalize_vector(
        rotation_axis - float(np.dot(rotation_axis, normal)) * normal,
        name="mirror aperture y axis",
    )
    aperture_x = normalize_vector(np.cross(aperture_y, normal), name="mirror aperture x axis")
    return normal, aperture_x, aperture_y


def _rotate_vector_about_axis(vector: Any, axis: Any, angle_rad: float) -> np.ndarray:
    unit_axis = normalize_vector(axis, name="scanner rotation axis")
    value = np.asarray(vector, dtype=np.float64)
    angle = float(angle_rad)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return normalize_vector(
        value * cosine
        + np.cross(unit_axis, value) * sine
        + unit_axis * float(np.dot(unit_axis, value)) * (1.0 - cosine),
        name="rotated scanner vector",
    )


def _scanner_static_pose(
    scenario: Any,
    *,
    element_id: str,
    normal: np.ndarray,
    aperture_x: np.ndarray,
    aperture_y: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    scanner = scenario.get("scanner", {})
    if str(scanner.get("element_id", "")) != element_id:
        return 0.0, np.zeros(3, dtype=np.float64), normal, aperture_x, aperture_y
    command_angle = float(scanner.get("static_command_angle_rad", 0.0))
    rotation_axis = normalize_vector(scanner["rotation_axis_world"], name="scanner rotation axis")
    if abs(command_angle) <= 1e-15:
        return command_angle, rotation_axis, normal, aperture_x, aperture_y
    return (
        command_angle,
        rotation_axis,
        _rotate_vector_about_axis(normal, rotation_axis, command_angle),
        _rotate_vector_about_axis(aperture_x, rotation_axis, command_angle),
        _rotate_vector_about_axis(aperture_y, rotation_axis, command_angle),
    )


def _scanner_mirror_report(
    *,
    scenario: Any,
    optical_path_id: str,
    element_id: str,
    component_ref: str,
    component: Any,
    element: Any,
    before_mirror: BeamState,
    ledger: list[PowerLedgerEntry],
) -> tuple[BeamState, dict[str, Any]]:
    optical = component["optical"]
    surface_model = str(optical["surface_model"])
    if surface_model != "flat_mirror":
        raise ValueError(f"지원하지 않는 scanner_mirror surface_model입니다: {surface_model!r}")

    normal, aperture_x, aperture_y = _mirror_aperture_axes(element, component)
    command_angle, rotation_axis, normal, aperture_x, aperture_y = _scanner_static_pose(
        scenario,
        element_id=element_id,
        normal=normal,
        aperture_x=aperture_x,
        aperture_y=aperture_y,
    )
    interaction = interact_flat_mirror(
        before_mirror,
        surface_origin_m=element.T_world_from_component.translation_m,
        surface_normal=normal,
        aperture_x_axis=aperture_x,
        aperture_y_axis=aperture_y,
        clear_width_m=float(optical["clear_width_m"]),
        clear_height_m=float(optical["clear_height_m"]),
        power_reflectivity=float(optical["power_reflectivity"]),
    )
    clip = interaction.aperture_clip
    after_clip_power = clip.output_power_w
    ledger.append(
        PowerLedgerEntry(
            optical_path_id=optical_path_id,
            element_id=element_id,
            component_ref=component_ref,
            mechanism="mirror_rectangular_aperture",
            input_power_w=clip.input_power_w,
            output_power_w=after_clip_power,
            loss_w=clip.loss_w,
            loss_db=clip.loss_db,
            transmission_fraction=clip.transmission_fraction,
            model_source=clip.method,
            warning=(
                "Mirror aperture는 surface-projected Gaussian power만 적분합니다. "
                "Diffraction과 edge scattering은 아직 계산하지 않습니다."
            ),
        )
    )
    reflectivity = float(optical["power_reflectivity"])
    after_reflection_power = after_clip_power * reflectivity
    ledger.append(
        PowerLedgerEntry(
            optical_path_id=optical_path_id,
            element_id=element_id,
            component_ref=component_ref,
            mechanism="mirror_reflectivity",
            input_power_w=after_clip_power,
            output_power_w=after_reflection_power,
            loss_w=after_clip_power - after_reflection_power,
            loss_db=_loss_db(after_clip_power, after_reflection_power),
            transmission_fraction=reflectivity,
            model_source="catalog optical.power_reflectivity",
        )
    )
    report = {
        "element_id": element_id,
        "component_ref": component_ref,
        "component_type": str(component["component_type"]),
        "model": surface_model,
        "surface_model": surface_model,
        "model_level": str(component["model_level"]),
        "incident_direction": before_mirror.direction.tolist(),
        "scanner_pose_model": "static_command_angle",
        "scanner_command_angle_rad": command_angle,
        "scanner_rotation_axis_input_world": [
            float(value) for value in scenario["scanner"]["rotation_axis_world"]
        ],
        "scanner_rotation_axis_world": rotation_axis.tolist(),
        "surface_normal_world": interaction.surface_normal.tolist(),
        "aperture_x_axis_world": interaction.aperture_x_axis.tolist(),
        "aperture_y_axis_world": interaction.aperture_y_axis.tolist(),
        "reflected_direction": interaction.reflected_direction.tolist(),
        "reflected_direction_world": interaction.reflected_direction.tolist(),
        "incidence_angle_rad": clip.incidence_angle_rad,
        "incidence_angle_convention": "angle_from_surface_normal_radians",
        "clear_width_m": float(optical["clear_width_m"]),
        "clear_height_m": float(optical["clear_height_m"]),
        "aperture_status": clip.status,
        "aperture_transmission_fraction": clip.transmission_fraction,
        "aperture_clip": clip.to_dict(),
        "power_reflectivity": reflectivity,
        "input_beam_state": before_mirror.to_dict(),
        "output_beam_state": interaction.output_beam.to_dict(),
        "assumptions": [
            "Ideal flat mirror에 static scanner command angle만 적용합니다.",
            "Dynamic lag, jitter, waveform sampling과 scanner time path는 아직 적용하지 않습니다.",
            "Beam center가 mirror component origin과 aperture 중심을 지난다고 가정합니다.",
            "Diffraction, edge scattering, coating spectral curve와 polarization은 계산하지 않습니다.",
        ],
        "warnings": [
            "Static command-angle reference입니다. Time-dependent scanner motion은 아직 계산하지 않습니다.",
            "Rectangular aperture는 projected Gaussian power clipping만 계산합니다.",
        ],
    }
    return interaction.output_beam, report


def propagate_transmitter_train(
    project: Any,
    assembly: AssemblyPlacement | None = None,
) -> OpticalTrainResult:
    """Active scenario의 source부터 첫 unsupported element까지 Gaussian train을 전파한다."""

    scenario = project.active_scenario
    if scenario["simulation"]["backend"] != "numpy" or scenario["simulation"]["real_dtype"] != "float64":
        raise ValueError("Phase 2 optical train reference는 backend=numpy, real_dtype=float64만 지원합니다.")
    propagation_model = str(scenario["source"]["propagation_model"])
    if propagation_model != "gaussian_m2":
        raise ValueError(
            "Phase 2 optical train은 propagation_model=gaussian_m2만 지원합니다. "
            f"{propagation_model!r}을 q-ABCD 경로로 암묵적으로 처리하지 않습니다."
        )

    resolved_assembly = assembly or resolve_assembly(
        scenario,
        project.catalog,
        source=str(project.project_path),
    )
    optical_path_id, sequence = _path_containing_source(scenario)
    source_id = str(scenario["source"]["element_id"])
    source_element = resolved_assembly[source_id]
    source_output_port = _preferred_port(source_element, "output")
    current = build_source_beam(project, resolved_assembly)

    states: list[BeamPlane] = [
        BeamPlane(
            label="source.output",
            element_id=source_id,
            component_ref=source_element.component_ref,
            port_id=source_output_port,
            plane_role="source_output",
            distance_along_path_m=current.optical_path_length_m,
            state=current,
        )
    ]
    ledger: list[PowerLedgerEntry] = []
    component_reports: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    warnings: list[str] = []

    for element_id in sequence[1:]:
        element = resolved_assembly[element_id]
        component = project.catalog[element.component_ref].data
        input_port, input_transform, plane_role = _input_reference_plane(element)
        distance, transverse_error = _axial_distance_to_port(current, input_transform)
        if transverse_error > 1e-9:
            reference = f"{element_id}.{input_port}" if input_port is not None else f"{element_id}.origin"
            warnings.append(
                f"{reference} plane이 beam axis에서 {transverse_error:.3e} m 벗어나 있습니다."
            )
        if distance > 0.0:
            current = _append_free_space(
                current=current,
                distance_m=distance,
                optical_path_id=optical_path_id,
                element_id=element_id,
                component_ref=element.component_ref,
                ledger=ledger,
            )
        states.append(
            BeamPlane(
                label=f"{element_id}.{input_port}" if input_port is not None else f"{element_id}.origin",
                element_id=element_id,
                component_ref=element.component_ref,
                port_id=input_port,
                plane_role=plane_role,
                distance_along_path_m=current.optical_path_length_m,
                state=current,
            )
        )

        component_type = str(component["component_type"])
        if component_type == "collimator":
            output_port = _preferred_port(element, "output")
            output_transform = element.world_from_port(output_port)
            current, report = _collimator_report(
                optical_path_id=optical_path_id,
                element_id=element_id,
                component_ref=element.component_ref,
                component=component,
                before_lens=current,
                output_origin_m=output_transform.translation_m,
                output_direction=output_transform.rotation[:, 2],
                output_x_axis=output_transform.rotation[:, 0],
                ledger=ledger,
            )
            component_reports.append(report)
            states.append(
                BeamPlane(
                    label=f"{element_id}.{output_port}",
                    element_id=element_id,
                    component_ref=element.component_ref,
                    port_id=output_port,
                    plane_role="element_output",
                    distance_along_path_m=current.optical_path_length_m,
                    state=current,
                )
            )
            continue

        if component_type == "scanner_mirror":
            current, report = _scanner_mirror_report(
                scenario=scenario,
                optical_path_id=optical_path_id,
                element_id=element_id,
                component_ref=element.component_ref,
                component=component,
                element=element,
                before_mirror=current,
                ledger=ledger,
            )
            component_reports.append(report)
            warnings.append(
                f"{element_id}는 static scanner command angle "
                f"{report['scanner_command_angle_rad']:.6g} rad만 적용했습니다. "
                "시간 구동 scanner motion은 아직 적용하지 않습니다."
            )
            states.append(
                BeamPlane(
                    label=f"{element_id}.reflected",
                    element_id=element_id,
                    component_ref=element.component_ref,
                    port_id=None,
                    plane_role="element_output",
                    distance_along_path_m=current.optical_path_length_m,
                    state=current,
                )
            )
            continue

        unsupported.append(
            {
                "element_id": element_id,
                "component_ref": element.component_ref,
                "component_type": component_type,
                "reason": (
                    "Phase 2 first vertical slice는 source→ideal thin-lens collimator와 "
                    "다음 component origin까지의 free-space propagation만 계산합니다."
                ),
            }
        )
        break

    return OpticalTrainResult(
        optical_path_id=optical_path_id,
        element_sequence=sequence,
        states=tuple(states),
        power_ledger=tuple(ledger),
        component_reports=tuple(component_reports),
        unsupported_elements=tuple(unsupported),
        warnings=tuple(warnings),
    )
