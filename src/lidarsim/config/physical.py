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
    "beam_envelope",
    "target_footprint",
    "received_aperture_power",
    "link_budget",
}

PARAXIAL_PROXY_TOLERANCE = 1e-3


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
        if component_type in {"fiber_source", "beam_source"}:
            for field in ("wavelength_m", "optical_power_w", "mode_field_diameter_m"):
                if field in optical:
                    _require_positive(
                        optical[field],
                        source=source,
                        path=f"optical.{field}",
                        diagnostics=diagnostics,
                    )
            source_model = str(optical.get("source_model", ""))
            if source_model == "fiber_gaussian" and "mode_field_diameter_m" in optical:
                if "mode_field_diameter_definition" not in optical:
                    diagnostics.append(
                        Diagnostic(
                            source=source,
                            path="optical.mode_field_diameter_definition",
                            message="Fiber MFD의 정의를 명시해야 합니다.",
                        )
                    )
                if optical.get("mode_field_diameter_uncertainty_m") is not None:
                    _require_positive(
                        optical["mode_field_diameter_uncertainty_m"],
                        source=source,
                        path="optical.mode_field_diameter_uncertainty_m",
                        diagnostics=diagnostics,
                        allow_zero=True,
                    )
            if source_model == "free_space_gaussian":
                for field in ("waist_radius_x_m", "waist_radius_y_m"):
                    if field not in optical:
                        diagnostics.append(
                            Diagnostic(
                                source=source,
                                path=f"optical.{field}",
                                message=f"free_space_gaussian component에는 {field}이 필요합니다.",
                            )
                        )
                    else:
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
        if component_ref in catalog and catalog[component_ref].data.get("component_type") in {
            "fiber_source",
            "beam_source",
        }:
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
    profile_kind = str(source_config["profile_kind"])
    propagation_model = str(source_config["propagation_model"])
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
        for field in ("mode_field_diameter_definition", "mfd_gaussian_approximation"):
            if field not in source_config:
                diagnostics.append(
                    Diagnostic(
                        source=source_text,
                        path=f"source.{field}",
                        message=f"fiber_gaussian source에는 {field}이 필요합니다.",
                    )
                )
        if source_config.get("mfd_gaussian_approximation") is False:
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path="source.mfd_gaussian_approximation",
                    message=(
                        "Gaussian beam engine은 MFD를 Gaussian-equivalent waist로 해석해야 합니다. "
                        "이 근사를 사용하지 않으려면 measured_profile을 선택하세요."
                    ),
                )
            )
        definition = source_config.get("mode_field_diameter_definition")
        if definition not in {None, "gaussian_1e2_intensity"}:
            warnings.append(
                Diagnostic(
                    source=source_text,
                    path="source.mode_field_diameter_definition",
                    message=(
                        f"{definition} MFD를 Gaussian 1/e^2 intensity diameter로 근사합니다."
                    ),
                    hint="실제 장비 예측에는 measured beam profile 또는 M² 측정값을 사용하세요.",
                    severity="warning",
                )
            )
        if source_config.get("mode_field_diameter_uncertainty_m") is not None:
            _require_positive(
                source_config["mode_field_diameter_uncertainty_m"],
                source=source_text,
                path="source.mode_field_diameter_uncertainty_m",
                diagnostics=diagnostics,
                allow_zero=True,
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
    if source_type == "measured_profile":
        if profile_kind != "measured" or propagation_model != "measured_transfer":
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path="source",
                    message=(
                        "measured_profile은 profile_kind=measured와 "
                        "propagation_model=measured_transfer를 사용해야 합니다."
                    ),
                )
            )
    elif profile_kind == "measured" or propagation_model == "measured_transfer":
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="source",
                message="Gaussian source에는 measured profile/model을 사용할 수 없습니다.",
            )
        )
    if profile_kind == "line_gaussian" and source_type != "free_space_gaussian":
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="source.profile_kind",
                message="line_gaussian은 두 waist radius가 명시된 free_space_gaussian으로 정의합니다.",
            )
        )
    m2_x = float(source_config.get("m2_x", 1.0))
    m2_y = float(source_config.get("m2_y", 1.0))
    if profile_kind == "circular_gaussian":
        same_m2 = math.isclose(m2_x, m2_y, rel_tol=1e-12, abs_tol=0.0)
        same_waist = True
        if source_type == "free_space_gaussian":
            same_waist = math.isclose(
                float(source_config["waist_radius_x_m"]),
                float(source_config["waist_radius_y_m"]),
                rel_tol=1e-12,
                abs_tol=0.0,
            )
        if not same_m2 or not same_waist:
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path="source.profile_kind",
                    message="circular_gaussian은 x/y waist radius와 M²가 같아야 합니다.",
                )
            )
    if profile_kind == "line_gaussian" and source_type == "free_space_gaussian" and math.isclose(
        float(source_config["waist_radius_x_m"]),
        float(source_config["waist_radius_y_m"]),
        rel_tol=1e-12,
        abs_tol=0.0,
    ):
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="source.profile_kind",
                message="line_gaussian은 서로 다른 x/y waist radius가 필요합니다.",
            )
        )

    waist_values: tuple[float, float] | None = None
    if source_type == "fiber_gaussian" and source_config.get("mode_field_diameter_m") is not None:
        radius = float(source_config["mode_field_diameter_m"]) / 2.0
        waist_values = (radius, radius)
    elif source_type == "free_space_gaussian" and all(
        field in source_config for field in ("waist_radius_x_m", "waist_radius_y_m")
    ):
        waist_values = (
            float(source_config["waist_radius_x_m"]),
            float(source_config["waist_radius_y_m"]),
        )
    if wavelength is not None and waist_values is not None and all(value > 0.0 for value in waist_values):
        divergences = (
            m2_x * wavelength / (math.pi * waist_values[0]),
            m2_y * wavelength / (math.pi * waist_values[1]),
        )
        maximum_angle = max(divergences)
        if maximum_angle >= math.pi / 2.0:
            proxy_error = math.inf
        else:
            proxy_error = max(
                abs(math.sin(maximum_angle) - maximum_angle) / maximum_angle,
                abs(math.tan(maximum_angle) - maximum_angle) / maximum_angle,
            )
        if proxy_error > PARAXIAL_PROXY_TOLERANCE:
            warnings.append(
                Diagnostic(
                    source=source_text,
                    path="source.propagation_model",
                    message=(
                        f"Maximum Gaussian divergence half-angle {maximum_angle:.6g} rad에서 "
                        f"small-angle geometric proxy error {proxy_error:.3e}가 "
                        f"tolerance {PARAXIAL_PROXY_TOLERANCE:.1e}를 넘습니다."
                    ),
                    hint="Non-paraxial 또는 measured-profile model의 필요성을 검토하세요.",
                    severity="warning",
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
        component_optical = component["optical"]
        catalog_model = str(component_optical.get("source_model", ""))
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
        comparable_fields = ["wavelength_m", "optical_power_w", "m2_x", "m2_y"]
        if source_type == "fiber_gaussian":
            comparable_fields.extend(
                ["mode_field_diameter_m", "mode_field_diameter_definition"]
            )
        elif source_type == "free_space_gaussian":
            comparable_fields.extend(["waist_radius_x_m", "waist_radius_y_m"])
        differences: list[str] = []
        for field in comparable_fields:
            if field not in source_config or field not in component_optical:
                continue
            scenario_value = source_config[field]
            catalog_value = component_optical[field]
            if isinstance(scenario_value, (int, float)) and isinstance(catalog_value, (int, float)):
                matches = math.isclose(
                    float(scenario_value),
                    float(catalog_value),
                    rel_tol=1e-12,
                    abs_tol=0.0,
                )
            else:
                matches = scenario_value == catalog_value
            if not matches:
                differences.append(field)
        policy = str(source_config["catalog_parameter_policy"])
        if differences and policy == "match_nominal":
            diagnostics.append(
                Diagnostic(
                    source=source_text,
                    path="source.catalog_parameter_policy",
                    message=(
                        "Scenario source 값이 catalog nominal과 다릅니다: "
                        + ", ".join(differences)
                    ),
                    hint="의도한 변경이면 catalog_parameter_policy=explicit_override를 사용하세요.",
                )
            )
        elif differences:
            warnings.append(
                Diagnostic(
                    source=source_text,
                    path="source.catalog_parameter_policy",
                    message="Catalog nominal을 명시적으로 override한 값: " + ", ".join(differences),
                    severity="warning",
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
    command_angle = _require_finite(
        scanner.get("static_command_angle_rad", 0.0),
        source=source_text,
        path="scanner.static_command_angle_rad",
        diagnostics=diagnostics,
    )
    if (
        command_angle is not None
        and amplitude is not None
        and not is_static
        and abs(command_angle) > amplitude + 1e-15
    ):
        diagnostics.append(
            Diagnostic(
                source=source_text,
                path="scanner.static_command_angle_rad",
                message="Static command angle은 mechanical_amplitude_rad 범위 안에 있어야 합니다.",
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
                hint="해당 후속 Phase 구현 전까지 report에서 not_evaluated로 취급하세요.",
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
