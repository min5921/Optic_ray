"""Streamlit parameter and numeric-placement workspace for UI Phase 0.2/B."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any

from lidarsim.config import find_project_root, load_project
from lidarsim.ui.runner import UiSimulationRun, run_ui_simulation
from lidarsim.ui.simulation_variant import (
    AssemblyElementEdits,
    SimulationParameterEdits,
    SimulationVariantResult,
    create_simulation_variant,
)


def _project_argument() -> Path:
    configured = os.environ.get("LIDARSIM_UI_PROJECT")
    if configured:
        return Path(configured).resolve()
    for value in sys.argv[1:]:
        if value.lower().endswith((".yaml", ".yml")):
            return Path(value).resolve()
    return (Path.cwd() / "configs" / "project.yaml").resolve()


def _component_options(project: Any, current_ref: str) -> list[str]:
    current_type = str(project.catalog[current_ref].data["component_type"])
    return sorted(
        entry.identifier
        for entry in project.catalog.entries.values()
        if entry.kind == "component"
        and str(entry.data["component_type"]) == current_type
    )


def _result_directory(project_path: Path, scenario_id: str, config_hash: str) -> Path:
    return (
        find_project_root(project_path)
        / "results"
        / "ui_runs"
        / f"{scenario_id}_{config_hash[:8]}"
    )


def _render_result(st: Any, variant: SimulationVariantResult | None, run: UiSimulationRun) -> None:
    summary = run.summary
    columns = st.columns(3)
    columns[0].metric(
        "Target power",
        f"{float(summary['estimated_power_on_target_w']) * 1e3:.6g} mW",
    )
    columns[1].metric(
        "Receiver power",
        f"{float(summary['estimated_received_power_w']) * 1e9:.6g} nW",
    )
    link_loss = summary.get("link_loss_db")
    columns[2].metric(
        "Link loss",
        "N/A" if link_loss is None else f"{float(link_loss):.6g} dB",
    )

    left, right = st.columns(2)
    left.image(str(run.workspace_image_path), caption="3D optical bench")
    right.image(str(run.optical_train_image_path), caption="Optical train")
    if run.scanner_path_image_path is not None:
        st.image(str(run.scanner_path_image_path), caption="Ideal scanner command path")

    st.caption(f"재현 project: {run.project_path}")
    st.caption(f"결과 directory: {run.output_directory}")
    st.caption(f"Standalone dashboard: {run.dashboard_path}")
    if variant is not None:
        with st.expander("저장된 변경 field"):
            st.code("\n".join(variant.changed_fields))
    if run.warnings:
        with st.expander(f"경고와 model limitation ({len(run.warnings)})"):
            for warning in run.warnings:
                st.warning(warning)


def run_streamlit_app(project_path: str | Path | None = None) -> None:
    """Render and execute the browser UI without making UI state authoritative."""

    import streamlit as st

    source_project_path = Path(project_path).resolve() if project_path else _project_argument()
    st.set_page_config(page_title="Optic Ray Workspace", layout="wide")
    st.title("Optic Ray Workspace")
    st.caption("UI Phase 0.2/B · parameter editor + numeric placement + simulation")
    st.info(
        "모든 변경은 variant YAML로 저장한 뒤 동일한 Python/schema/physics 경로로 실행합니다. "
        "UI 내부 상태는 simulation의 source of truth가 아닙니다."
    )

    try:
        project = load_project(source_project_path)
    except Exception as exc:
        st.error(f"Project를 열 수 없습니다: {exc}")
        st.stop()
        return

    scenario = project.active_scenario
    elements = list(scenario["optical_assembly"]["elements"])
    targets = list(scenario["scene"]["targets"])
    element_ids = [str(item["id"]) for item in elements]
    target_ids = [str(item["id"]) for item in targets]

    st.sidebar.header("Project")
    st.sidebar.code(str(source_project_path))
    st.sidebar.caption(f"scenario: {scenario['scenario_id']}")
    st.sidebar.caption(f"config: {project.config_hash[:12]}")
    selected_element_id = st.sidebar.selectbox("편집 component", element_ids)
    selected_target_id = st.sidebar.selectbox("편집 target", target_ids)
    waveform_options = ["static", "triangle", "sinusoidal"]
    current_waveform = str(scenario["scanner"]["waveform"])
    waveform_index = (
        waveform_options.index(current_waveform) if current_waveform in waveform_options else 0
    )
    selected_waveform = st.sidebar.selectbox(
        "Scanner waveform",
        waveform_options,
        index=waveform_index,
    )

    element = next(item for item in elements if str(item["id"]) == selected_element_id)
    target = next(item for item in targets if str(item["id"]) == selected_target_id)
    placement = element["placement"]
    placement_mode = str(placement["mode"])
    current_ref = str(element["component_ref"])
    component_options = _component_options(project, current_ref)
    target_geometry = target["geometry"]
    receiver = scenario["receiver"]
    scanner = scenario["scanner"]
    source = scenario["source"]

    if "default_variant_id" not in st.session_state:
        st.session_state["default_variant_id"] = f"{scenario['scenario_id']}_ui_variant"

    with st.form("simulation_editor"):
        st.subheader("Variant")
        variant_id = st.text_input(
            "Scenario ID",
            value=st.session_state["default_variant_id"],
            help="Baseline을 덮어쓰지 않고 configs/ui_runs 아래에 저장합니다.",
        )
        overwrite = st.checkbox("같은 ID의 기존 UI variant 덮어쓰기", value=False)

        st.subheader("광원과 scanner")
        source_col, scanner_col = st.columns(2)
        wavelength_nm = source_col.number_input(
            "Wavelength (nm)",
            min_value=1.0,
            value=float(source["wavelength_m"]) * 1e9,
        )
        optical_power_mw = source_col.number_input(
            "Source power (mW)",
            min_value=0.0,
            value=float(source["optical_power_w"]) * 1e3,
        )
        static_angle_deg = scanner_col.number_input(
            "Static command angle (deg)",
            value=math.degrees(float(scanner.get("static_command_angle_rad", 0.0))),
        )
        amplitude_deg = scanner_col.number_input(
            "Mechanical amplitude (deg)",
            min_value=0.0,
            value=math.degrees(float(scanner["mechanical_amplitude_rad"])),
            disabled=selected_waveform == "static",
        )
        frequency_hz = scanner_col.number_input(
            "Frequency (Hz)",
            min_value=0.0,
            value=float(scanner["frequency_hz"]),
            disabled=selected_waveform == "static",
        )
        samples_per_line = scanner_col.number_input(
            "Samples per line",
            min_value=1,
            value=int(scanner["samples_per_line"]),
            step=1,
        )

        st.subheader("Target와 receiver")
        target_col, receiver_col = st.columns(2)
        center = [float(value) for value in target_geometry["center_m"]]
        target_center = tuple(
            target_col.number_input(f"Target center {axis} (m)", value=center[index])
            for index, axis in enumerate("XYZ")
        )
        target_normal_values = [float(value) for value in target_geometry["normal"]]
        target_normal = tuple(
            target_col.number_input(
                f"Target normal {axis}",
                value=target_normal_values[index],
            )
            for index, axis in enumerate("XYZ")
        )
        target_width_m = target_col.number_input(
            "Target width (m)", min_value=1.0e-6, value=float(target_geometry["width_m"])
        )
        target_height_m = target_col.number_input(
            "Target height (m)", min_value=1.0e-6, value=float(target_geometry["height_m"])
        )
        receiver_aperture_mm = receiver_col.number_input(
            "Receiver aperture (mm)",
            min_value=1.0e-6,
            value=float(receiver["aperture_diameter_m"]) * 1e3,
        )
        receiver_fov_deg = receiver_col.number_input(
            "Receiver full FOV (deg)",
            min_value=1.0e-6,
            max_value=180.0,
            value=math.degrees(float(receiver["full_fov_rad"])),
        )
        receiver_efficiency = receiver_col.number_input(
            "Receiver optical efficiency",
            min_value=0.0,
            max_value=1.0,
            value=float(receiver["optical_efficiency"]),
        )
        receiver_position_values = [float(value) for value in receiver["position_m"]]
        receiver_position = tuple(
            receiver_col.number_input(
                f"Receiver position {axis} (m)",
                value=receiver_position_values[index],
            )
            for index, axis in enumerate("XYZ")
        )
        receiver_direction_values = [float(value) for value in receiver["direction"]]
        receiver_direction = tuple(
            receiver_col.number_input(
                f"Receiver direction {axis}",
                value=receiver_direction_values[index],
            )
            for index, axis in enumerate("XYZ")
        )

        st.subheader(f"Component — {selected_element_id}")
        component_ref = st.selectbox(
            "Compatible component reference",
            component_options,
            index=component_options.index(current_ref),
        )
        st.caption(f"placement mode: {placement_mode}")
        if placement_mode == "absolute":
            translation = [float(value) for value in placement["translation_m"]]
            quaternion = [float(value) for value in placement["quaternion_wxyz"]]
            translation_m = tuple(
                st.number_input(f"Position {axis} (m)", value=translation[index])
                for index, axis in enumerate("XYZ")
            )
            quaternion_wxyz = tuple(
                st.number_input(f"Quaternion {axis}", value=quaternion[index], format="%.9f")
                for index, axis in enumerate("WXYZ")
            )
            axial_gap_mm = None
            transverse_offset_mm = None
            clocking_deg = None
            misalignment_deg = None
        else:
            translation_m = None
            quaternion_wxyz = None
            axial_gap_mm = st.number_input(
                "Axial gap (mm)",
                value=float(placement.get("axial_gap_m", 0.0)) * 1e3,
            )
            offset = [float(value) * 1e3 for value in placement.get("transverse_offset_m", (0, 0))]
            transverse_offset_mm = tuple(
                st.number_input(f"Transverse offset {axis} (mm)", value=offset[index])
                for index, axis in enumerate("UV")
            )
            clocking_deg = st.number_input(
                "Clocking (deg)",
                value=math.degrees(float(placement.get("clocking_rad", 0.0))),
            )
            misalignment = [
                math.degrees(float(value))
                for value in placement.get("angular_misalignment_rad", (0, 0))
            ]
            misalignment_deg = tuple(
                st.number_input(f"Angular misalignment {axis} (deg)", value=misalignment[index])
                for index, axis in enumerate(("X", "Y"))
            )

        include_scanner_path = st.checkbox("Ideal scanner path도 계산", value=True)
        submitted = st.form_submit_button("Variant 저장 · 검증 · 시뮬레이션", type="primary")

    if submitted:
        root = find_project_root(source_project_path)
        output_dir = root / "configs" / "ui_runs"
        scenario_output = output_dir / f"{variant_id}.yaml"
        project_output = output_dir / f"{variant_id}_project.yaml"
        parameter_edits = SimulationParameterEdits(
            wavelength_m=f"{wavelength_nm:.12g} nm",
            optical_power_w=f"{optical_power_mw:.12g} mW",
            scanner_static_command_angle_rad=f"{static_angle_deg:.12g} deg",
            scanner_mechanical_amplitude_rad=(
                "0 deg" if selected_waveform == "static" else f"{amplitude_deg:.12g} deg"
            ),
            scanner_frequency_hz=(
                "0 Hz" if selected_waveform == "static" else f"{frequency_hz:.12g} Hz"
            ),
            scanner_waveform=selected_waveform,
            scanner_samples_per_line=int(samples_per_line),
            target_id=selected_target_id,
            target_center_m=tuple(f"{value:.12g} m" for value in target_center),
            target_normal=target_normal,
            target_width_m=f"{target_width_m:.12g} m",
            target_height_m=f"{target_height_m:.12g} m",
            receiver_position_m=tuple(f"{value:.12g} m" for value in receiver_position),
            receiver_direction=receiver_direction,
            receiver_aperture_diameter_m=f"{receiver_aperture_mm:.12g} mm",
            receiver_full_fov_rad=f"{receiver_fov_deg:.12g} deg",
            receiver_optical_efficiency=float(receiver_efficiency),
        )
        if placement_mode == "absolute":
            element_edits = AssemblyElementEdits(
                element_id=selected_element_id,
                component_ref=component_ref,
                translation_m=translation_m,
                quaternion_wxyz=quaternion_wxyz,
            )
        else:
            assert axial_gap_mm is not None
            assert transverse_offset_mm is not None
            assert clocking_deg is not None
            assert misalignment_deg is not None
            element_edits = AssemblyElementEdits(
                element_id=selected_element_id,
                component_ref=component_ref,
                axial_gap_m=f"{axial_gap_mm:.12g} mm",
                transverse_offset_m=tuple(
                    f"{value:.12g} mm" for value in transverse_offset_mm
                ),
                clocking_rad=f"{clocking_deg:.12g} deg",
                angular_misalignment_rad=tuple(
                    f"{value:.12g} deg" for value in misalignment_deg
                ),
            )
        try:
            with st.spinner("Variant를 검증하고 optical simulation을 실행하는 중입니다..."):
                variant = create_simulation_variant(
                    project_path=source_project_path,
                    scenario_id=variant_id,
                    scenario_output=scenario_output,
                    project_output=project_output,
                    parameter_edits=parameter_edits,
                    element_edits=element_edits,
                    overwrite=overwrite,
                )
                run = run_ui_simulation(
                    variant.project_path,
                    output_directory=_result_directory(
                        variant.project_path,
                        variant.scenario_id,
                        variant.config_hash,
                    ),
                    include_scanner_path=include_scanner_path,
                )
            st.session_state["last_variant"] = variant
            st.session_state["last_run"] = run
            st.success("Variant 저장, validation과 simulation이 완료되었습니다.")
        except Exception as exc:
            st.error(f"실행 실패: {exc}")

    if "last_run" not in st.session_state:
        preview_dir = (
            find_project_root(source_project_path)
            / "results"
            / "ui_preview"
            / f"{scenario['scenario_id']}_{project.config_hash[:8]}"
        )
        try:
            with st.spinner("현재 baseline workspace를 준비하는 중입니다..."):
                st.session_state["last_run"] = run_ui_simulation(
                    source_project_path,
                    output_directory=preview_dir,
                    include_scanner_path=False,
                )
                st.session_state["last_variant"] = None
        except Exception as exc:
            st.error(f"Baseline preview 실패: {exc}")

    last_run = st.session_state.get("last_run")
    if isinstance(last_run, UiSimulationRun):
        _render_result(st, st.session_state.get("last_variant"), last_run)


if __name__ == "__main__":
    run_streamlit_app()


__all__ = ["run_streamlit_app"]
