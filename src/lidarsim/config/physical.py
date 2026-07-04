"""Schema만으로 표현하기 어려운 physical·cross-field validation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from lidarsim.errors import ConfigValidationError, Diagnostic


IMPLEMENTED_OUTPUTS = {
    "resolved_config",
    "run_manifest",
    "accuracy_report",
    "placement_report",
    "energy_ledger",
    "convergence_report",
    "layout_3d",
}


def _require_finite(
    value: Any,
    *,
    source: str,
    path: str,
    diagnostics: list[Diagnostic],
) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        diagnostics.append(
            Diagnostic(source=source, path=path, message="유한한 숫자여야 합니다.")
        )
        return None
    return number


def _require_positive(
    value: Any,
    *,
    source: str,
    path: str,
    diagnostics: list[Diagnostic],
    allow_zero: bool = False,
) -> float | None:
    number = _require_finite(value, source=source, path=path, diagnostics=diagnostics)
    if number is None:
        return None
    invalid = number < 0.0 if allow_zero else number <= 0.0
    if invalid:
        relation = "0 이상" if allow_zero else "0보다 큰 값"
        diagnostics.append(
            Diagnostic(
                source=source,
                path=path,
                message=f"Physical quantity는 {relation}이어야 합니다: {number}",
            )
        )
    return number


def _validate_range(
    values: Sequence[Any],
    *,
    source: str,
    path: str,
    diagnostics: list[Diagnostic],
) -> tuple[float, float] | None:
    if len(values) != 2:
        return None
    minimum = _require_positive(
        values[0], source=source, path=f"{path}[0]", diagnostics=diagnostics
    )
    maximum = _require_positive(
        values[1], source=source, path=f"{path}[1]", diagnostics=diagnostics
    )
    if minimum is None or maximum is None:
        return None
    if minimum > maximum:
        diagnostics.append(
            Diagnostic(
                source=source,
                path=path,
                message="Validity range의 minimum이 maximum보다 큽니다.",
            )
        )
    return minimum, maximum


def _require_direction(
    values: Sequence[Any],
    *,
    source: str,
    path: str,
    diagnostics: list[Diagnostic],
) -> tuple[float, float, float] | None:
    if len(values) != 3:
        return None
    resolved = tuple(
        _require_finite(value, source=source, path=f"{path}[{index}]", diagnostics=diagnostics)
        for index, value in enumerate(values)
    )
    if any(value is None for value in resolved):
        return None
    vector = tuple(float(value) for value in resolved)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 1e-15:
        diagnostics.append(
            Diagnostic(source=source, path=path, message="Direction vector는 zero일 수 없습니다.")
        )
        return None
    return tuple(value / norm for value in vector)


def validate_catalog_record_physics(
    record: Mapping[str, Any],
    *,
    source: str,
    kind: str,
) -> None:
    """Resolved component·material record의 physical bounds를 검사한다."""

    diagnostics: list[Diagnostic] = []
    optical = record["optical"]
    if kind == "component":
        component_type = str(record["component_type"])
        if component_type == "fiber_source":
            for field in ("wavelength_m", "optical_power_w", "mode_field_diameter_m"):
                if field in optical:
                    _require_positive(
                        optical[field],
                        source=source,
                        path=f"optical.{field}",
                        diagnostics=diagnostics,
                    )
        elif component_type == "collimator":
            for field in (
                "design_wavelength_m",
                "effective_focal_length_m",
                "clear_aperture_diameter_m",
            ):
                _require_positive(
                    optical[field],
                    source=source,
                    path=f"optical.{field}",
                    diagnostics=diagnostics,
                )
        elif component_type == "scanner_mirror":
            for field in ("clear_width_m", "clear_height_m"):
                _require_positive(
                    optical[field],
                    source=source,
                    path=f"optical.{field}",
                    diagnostics=diagnostics,
                )
            mechanical = record["mechanical"]
            axis = _require_direction(
                mechanical["default_rotation_axis_local"],
                source=source,
                path="mechanical.default_rotation_axis_local",
                diagnostics=diagnostics,
            )
            normal = _require_direction(
                mechanical["surface_normal_local"],
                source=source,
                path="mechanical.surface_normal_local",
                diagnostics=diagnostics,
            )
            if axis is not None and normal is not None:
                cosine = abs(sum(a * b for a, b in zip(axis, normal, strict=True)))
                if cosine > 1e-9:
                    diagnostics.append(
                        Diagnostic(
                            source=source,
                            path="mechanical",
                            message="Scanner rotation axis는 mirror surface normal과 수직이어야 합니다.",
                        )
                    )
        for index, port in enumerate(record.get("ports", ())):
            if port.get("clear_aperture_diameter_m") is not None:
                _require_positive(
                    port["clear_aperture_diameter_m"],
                    source=source,
                    path=f"ports[{index}].clear_aperture_diameter_m",
                    diagnostics=diagnostics,
                )
        validity = record.get("validity")
        if isinstance(validity, Mapping) and validity.get("wavelength_range_m") is not None:
            _validate_range(
                validity["wavelength_range_m"],
                source=source,
                path="validity.wavelength_range_m",
                diagnostics=diagnostics,
            )
    else:
        _require_positive(
            optical["wavelength_m"],
            source=source,
            path="optical.wavelength_m",
            diagnostics=diagnostics,
        )
        reflectivity = float(optical.get("hemispherical_reflectivity", 0.0))
        transmission = float(optical.get("transmission", 0.0))
        if reflectivity + transmission > 1.0 + 1e-12:
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path="optical",
                    message="Reflectivity와 transmission의 합은 1을 넘을 수 없습니다.",
                )
            )
    if diagnostics:
        raise ConfigValidationError(diagnostics)


def _source_element(
    scenario: Mapping[str, Any],
    catalog: Any,
    elements: Mapping[str, Mapping[str, Any]],
) -> tuple[str, Mapping[str, Any]] | None:
    source_element_id = str(scenario["source"].get("element_id", ""))
    if source_element_id:
        element = elements.get(source_element_id)
        return (source_element_id, element) if element is not None else None
    candidates: list[tuple[str, Mapping[str, Any]]] = []
    for element_id, element in elements.items():
        component_ref = str(element["component_ref"])
        if component_ref in catalog and catalog[component_ref].data.get("component_type") == "fiber_source":
            candidates.append((element_id, element))
    return candidates[0] if len(candidates) == 1 else None


def validate_scenario_physics(
    scenario: Mapping[str, Any],
    *,
    source: Path,
    catalog: Any,
) -> tuple[Diagnostic, ...]:
    """Scenario physical bounds·ownership·capability를 검사한다."""

    source_text = str(source)
    diagnostics: list[Diagnostic] = []
    warnings: list[Diagnostic] = []
    source_config = scenario["source"]
    wavelength = _require_positive(
        source_config["wavelength_m"],
        source=source_text,
        path="source.wavelength_m",
        diagnostics=diagnostics,
    )
    _require_positive(
        source_config["optical_power_w"],
        source=source_text,
        path="source.optical_power_w",
        diagnostics=diagnostics,
    )
    source_type = str(source_config["type"])
    if source_type == "fiber_gaussian":
        if "mode_field_diameter_m" not in source_config:
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path="source.mode_field_diameter_m",
                    message="fiber_gaussian source에는 mode_field_diameter_m이 필요합니다.",
                )
            )
        else:
            _require_positive(
                source_config["mode_field_diameter_m"],
                source=source_text,
                path="source.mode_field_diameter_m",
                diagnostics=diagnostics,
            )
    elif source_type == "free_space_gaussian":
        for field in ("waist_radius_x_m", "waist_radius_y_m"):
            if field not in source_config:
                diagnostics.append(
                    Diagnostic(
                        source=source_text,
                        path=f"source.{field}",
                        message=f"free_space_gaussian source에는 {field}이 필요합니다.",
                    )
                )
            else:
                _require_positive(
                    source_config[field],
                    source=source_text,
                    path=f"source.{field}",
                    diagnostics=diagnostics,
                )
    elif source_type == "measured_profile" and not source_config.get("profile_file"):
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="source.profile_file",
                message="measured_profile source에는 profile_file이 필요합니다.",
            )
        )

    element_list = scenario["optical_assembly"]["elements"]
    elements = {str(element["id"]): element for element in element_list}
    source_element = _source_element(scenario, catalog, elements)
    if source_element is None:
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="source.element_id",
                message="Operational source와 연결할 fiber_source element를 하나로 결정할 수 없습니다.",
            )
        )
    else:
        source_element_id, source_element_spec = source_element
        component_ref = str(source_element_spec["component_ref"])
        component = catalog[component_ref].data
        catalog_model = str(component["optical"].get("source_model", ""))
        if catalog_model and catalog_model != source_type:
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path="source.type",
                    message=(
                        f"Scenario source type {source_type!r}이 element {source_element_id!r}의 "
                        f"catalog source_model {catalog_model!r}과 다릅니다."
                    ),
                )
            )
        validity = component.get("validity", {})
        wavelength_range = validity.get("wavelength_range_m")
        if wavelength is not None and wavelength_range is not None:
            lower, upper = (float(value) for value in wavelength_range)
            if not lower <= wavelength <= upper:
                diagnostics.append(
                    Diagnostic(
                        source=source_text,
                        path="source.wavelength_m",
                        message=(
                            f"Wavelength {wavelength} m가 source component {component_ref!r}의 "
                            f"validity range [{lower}, {upper}] m 밖에 있습니다."
                        ),
                    )
                )

    if wavelength is not None:
        source_element_id = str(source_config["element_id"])
        for element_id, element in elements.items():
            if element_id == source_element_id:
                continue
            component_ref = str(element["component_ref"])
            component = catalog[component_ref].data
            wavelength_range = component.get("validity", {}).get("wavelength_range_m")
            if wavelength_range is None:
                continue
            lower, upper = (float(value) for value in wavelength_range)
            if not lower <= wavelength <= upper:
                diagnostics.append(
                    Diagnostic(
                        source=source_text,
                        path="source.wavelength_m",
                        message=(
                            f"Wavelength {wavelength} m가 element {element_id!r} "
                            f"({component_ref})의 validity range [{lower}, {upper}] m 밖에 있습니다."
                        ),
                    )
                )

    scanner = scenario["scanner"]
    amplitude = _require_positive(
        scanner["mechanical_amplitude_rad"],
        source=source_text,
        path="scanner.mechanical_amplitude_rad",
        diagnostics=diagnostics,
        allow_zero=True,
    )
    frequency = _require_positive(
        scanner["frequency_hz"],
        source=source_text,
        path="scanner.frequency_hz",
        diagnostics=diagnostics,
        allow_zero=True,
    )
    is_static = scanner["type"] == "static_mirror" or scanner["waveform"] == "static"
    if is_static and ((amplitude or 0.0) != 0.0 or (frequency or 0.0) != 0.0):
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="scanner",
                message="Static scanner는 amplitude와 frequency가 0이어야 합니다.",
            )
        )
    if not is_static and ((amplitude or 0.0) <= 0.0 or (frequency or 0.0) <= 0.0):
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="scanner",
                message="Moving scanner는 양수 amplitude와 frequency가 필요합니다.",
            )
        )
    if amplitude is not None and amplitude >= math.pi / 2.0:
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="scanner.mechanical_amplitude_rad",
                message="Mechanical scan amplitude는 90 deg보다 작아야 합니다.",
            )
        )

    for index, target in enumerate(scenario["scene"]["targets"]):
        geometry = target["geometry"]
        base_path = f"scene.targets[{index}].geometry"
        if geometry["type"] == "rectangle_plane":
            for field in ("center_m", "normal", "width_m", "height_m"):
                if field not in geometry:
                    diagnostics.append(
                        Diagnostic(
                            source=source_text,
                            path=f"{base_path}.{field}",
                            message=f"rectangle_plane에는 {field}이 필요합니다.",
                        )
                    )
            for field in ("width_m", "height_m"):
                if field in geometry:
                    _require_positive(
                        geometry[field],
                        source=source_text,
                        path=f"{base_path}.{field}",
                        diagnostics=diagnostics,
                    )
        elif not geometry.get("metadata_file"):
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path=f"{base_path}.metadata_file",
                    message="stl_asset geometry에는 metadata_file이 필요합니다.",
                )
            )
        if wavelength is not None:
            material_ref = str(target["material_ref"])
            material_wavelength = float(catalog[material_ref].data["optical"]["wavelength_m"])
            if not math.isclose(wavelength, material_wavelength, rel_tol=1e-12, abs_tol=0.0):
                warnings.append(
                    Diagnostic(
                        source=source_text,
                        path=f"scene.targets[{index}].material_ref",
                        message=(
                            f"Material {material_ref!r}은 {material_wavelength} m에서 정의됐지만 "
                            f"scenario wavelength는 {wavelength} m입니다."
                        ),
                        hint="해당 파장의 measured/catalog material data로 교체하세요.",
                        severity="warning",
                    )
                )

    receiver = scenario["receiver"]
    _require_positive(
        receiver["aperture_diameter_m"],
        source=source_text,
        path="receiver.aperture_diameter_m",
        diagnostics=diagnostics,
    )
    fov = _require_positive(
        receiver["full_fov_rad"],
        source=source_text,
        path="receiver.full_fov_rad",
        diagnostics=diagnostics,
    )
    if fov is not None and fov > math.pi:
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="receiver.full_fov_rad",
                message="Receiver full FOV는 180 deg 이하여야 합니다.",
            )
        )
    if receiver["architecture"] == "virtual_monostatic":
        warnings.append(
            Diagnostic(
                source=source_text,
                path="receiver.architecture",
                message=(
                    "virtual_monostatic receiver는 실제 beamsplitter·reverse scanner·detector "
                    "path를 생략한 analytical aperture입니다."
                ),
                severity="warning",
            )
        )

    simulation = scenario["simulation"]
    if simulation["backend"] != "numpy":
        warnings.append(
            Diagnostic(
                source=source_text,
                path="simulation.backend",
                message="Phase 0 reference path는 numpy만 검증되었습니다.",
                severity="warning",
            )
        )
    if simulation["real_dtype"] != "float64":
        warnings.append(
            Diagnostic(
                source=source_text,
                path="simulation.real_dtype",
                message="CPU reference validation은 float64를 사용해야 합니다.",
                severity="warning",
            )
        )
    unavailable = sorted(set(scenario["outputs"]) - IMPLEMENTED_OUTPUTS)
    if unavailable:
        warnings.append(
            Diagnostic(
                source=source_text,
                path="outputs",
                message=f"현재 Phase에서 생성되지 않는 output입니다: {', '.join(unavailable)}",
                hint="Phase 1 이후 구현 전까지 report에서 not_evaluated로 취급하세요.",
                severity="warning",
            )
        )
    if scenario.get("model_purpose") == "analytical_regression":
        warnings.append(
            Diagnostic(
                source=source_text,
                path="model_purpose",
                message="이 scenario는 실제 product prediction이 아닌 analytical regression 기준입니다.",
                severity="warning",
            )
        )
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return tuple(warnings)
