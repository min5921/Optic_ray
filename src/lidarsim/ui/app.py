"""3D optical bench 중심의 Streamlit simulation workspace."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any

from lidarsim.config import find_project_root, load_project
from lidarsim.ui.assembly import (
    MirrorTargetMatePreview,
    build_interactive_viewport_figure,
    build_viewport_scene,
    preview_mirror_target_mate,
)
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


def _selection_event_element_id(event: Any) -> str | None:
    """Streamlit Plotly selection payload에서 component id를 안전하게 꺼낸다."""

    if event is None:
        return None
    selection = event.get("selection") if isinstance(event, dict) else getattr(event, "selection", None)
    if selection is None:
        return None
    points = selection.get("points", ()) if isinstance(selection, dict) else getattr(selection, "points", ())
    if not points:
        return None
    first = points[0]
    custom = first.get("customdata") if isinstance(first, dict) else getattr(first, "customdata", None)
    if isinstance(custom, (list, tuple)) and custom:
        return str(custom[0])
    if isinstance(custom, str):
        return custom
    return None


def _stage_session_values(state: Any, values: dict[str, float]) -> None:
    for key, value in values.items():
        state[key] = float(value)


def _scanner_axis_keys(config_hash: str) -> tuple[str, str, str]:
    return tuple(
        f"scanner:{config_hash}:rotation_axis:{axis}"
        for axis in "xyz"
    )  # type: ignore[return-value]


def _same_values(first: tuple[float, ...], second: tuple[float, ...], *, atol: float = 1.0e-12) -> bool:
    return len(first) == len(second) and all(
        math.isclose(a, b, rel_tol=0.0, abs_tol=atol) for a, b in zip(first, second)
    )


def _ensure_preview_run(st: Any, project_path: Path, project: Any) -> UiSimulationRun:
    current = st.session_state.get("last_run")
    if isinstance(current, UiSimulationRun):
        current_project = load_project(current.project_path)
        if (
            getattr(current, "config_hash", None) == current_project.config_hash
        ):
            return current
        project_path = current_project.project_path
        project = current_project
        st.session_state["last_variant"] = None
    preview_dir = (
        find_project_root(project_path)
        / "results"
        / "ui_preview"
        / f"{project.active_scenario['scenario_id']}_{project.config_hash[:8]}"
    )
    with st.spinner("Config 변경을 읽고 광학 배치와 빔 경로를 계산하는 중입니다..."):
        current = run_ui_simulation(
            project_path,
            output_directory=preview_dir,
            include_scanner_path=False,
        )
    st.session_state["last_run"] = current
    st.session_state["last_variant"] = None
    return current


def _render_metrics(st: Any, run: UiSimulationRun) -> None:
    summary = run.summary
    columns = st.columns(3)
    columns[0].metric(
        "Target power",
        f"{float(summary['estimated_power_on_target_w']) * 1e3:.6g} mW",
    )
    columns[1].metric(
        "Virtual aperture estimate",
        f"{float(summary['estimated_received_power_w']) * 1e9:.6g} nW",
        help=(
            "현재 값은 분석용 virtual aperture 추정값입니다. 동일 scanner/collimator의 "
            "역방향 광로와 single-mode fiber 결합은 아직 포함하지 않습니다."
        ),
    )
    link_loss = summary.get("link_loss_db")
    columns[2].metric(
        "Link loss",
        "N/A" if link_loss is None else f"{float(link_loss):.6g} dB",
    )


def _render_run_details(
    st: Any,
    variant: SimulationVariantResult | None,
    run: UiSimulationRun,
) -> None:
    with st.expander("분석 결과와 재현 파일"):
        left, right = st.columns(2)
        left.image(str(run.optical_train_image_path), caption="Gaussian beam / power train")
        if run.scanner_path_image_path is not None:
            right.image(str(run.scanner_path_image_path), caption="Ideal scanner command path")
        else:
            right.caption("이번 실행에는 scanner path를 포함하지 않았습니다.")
        st.code(
            "\n".join(
                (
                    f"project: {run.project_path}",
                    f"report: {run.report_path}",
                    f"scene: {run.scene_path}",
                    f"results: {run.output_directory}",
                )
            )
        )
        if variant is not None:
            st.caption("저장된 변경 field")
            st.code("\n".join(variant.changed_fields))
    if run.warnings:
        with st.expander(f"경고와 model limitation ({len(run.warnings)})"):
            for warning in run.warnings:
                st.warning(warning)


def _render_mirror_mate(
    st: Any,
    preview: MirrorTargetMatePreview,
    *,
    quaternion_keys: tuple[str, str, str, str],
    scanner_axis_keys: tuple[str, str, str],
) -> None:
    st.markdown("#### Mirror → Target 정렬")
    residual_deg = math.degrees(preview.current_residual_angle_rad)
    rotation_deg = math.degrees(preview.required_rotation_angle_rad)
    if preview.status == "aligned":
        st.success(f"현재 reflected ray가 target center에 정렬되어 있습니다. residual {residual_deg:.6g}°")
    else:
        st.warning(f"Target center residual {residual_deg:.6g}° · 추천 pose 회전 {rotation_deg:.6g}°")
    staged_values = dict(zip(quaternion_keys, preview.recommended_quaternion_wxyz))
    staged_values.update(
        zip(scanner_axis_keys, preview.recommended_scanner_rotation_axis_world)
    )
    st.button(
        "추천 pose를 편집값에 적용",
        key=f"apply_mirror_mate:{preview.constraint_id}",
        disabled=not preview.can_apply,
        on_click=_stage_session_values,
        args=(st.session_state, staged_values),
        help="아직 파일을 바꾸지 않습니다. 아래 저장·검증·시뮬레이션을 눌러야 variant YAML에 기록됩니다.",
    )
    st.caption("파란 점선은 target-center 추천 ray와 추천 mirror normal입니다.")
    for warning in preview.warnings:
        st.warning(warning)


def _placement_editor(
    st: Any,
    project: Any,
    element: Any,
    *,
    mate_preview: MirrorTargetMatePreview | None,
) -> AssemblyElementEdits | None:
    element_id = str(element["id"])
    placement = element["placement"]
    mode = str(placement["mode"])
    current_ref = str(element["component_ref"])
    component_options = _component_options(project, current_ref)
    component_ref = st.selectbox(
        "Component model",
        component_options,
        index=component_options.index(current_ref),
        key=f"component_ref:{project.config_hash}:{element_id}",
    )
    st.caption(f"placement mode: {mode}")

    component_change = None if component_ref == current_ref else component_ref
    if mode == "absolute":
        translation = tuple(float(value) for value in placement["translation_m"])
        quaternion = tuple(float(value) for value in placement["quaternion_wxyz"])
        translation_keys = tuple(
            f"placement:{project.config_hash}:{element_id}:translation:{axis}"
            for axis in "xyz"
        )
        quaternion_keys = tuple(
            f"placement:{project.config_hash}:{element_id}:quaternion:{axis}"
            for axis in "wxyz"
        )
        if mate_preview is not None:
            _render_mirror_mate(
                st,
                mate_preview,
                quaternion_keys=quaternion_keys,  # type: ignore[arg-type]
                scanner_axis_keys=_scanner_axis_keys(project.config_hash),
            )
        position_columns = st.columns(3)
        edited_translation = tuple(
            position_columns[index].number_input(
                f"Position {axis.upper()} (m)",
                value=translation[index],
                key=translation_keys[index],
                format="%.9f",
            )
            for index, axis in enumerate("xyz")
        )
        quaternion_columns = st.columns(4)
        edited_quaternion = tuple(
            quaternion_columns[index].number_input(
                f"Quaternion {axis.upper()}",
                value=quaternion[index],
                key=quaternion_keys[index],
                format="%.9f",
            )
            for index, axis in enumerate("wxyz")
        )
        translation_change = None if _same_values(translation, edited_translation) else edited_translation
        quaternion_change = None if _same_values(quaternion, edited_quaternion) else edited_quaternion
        if component_change is None and translation_change is None and quaternion_change is None:
            return None
        return AssemblyElementEdits(
            element_id=element_id,
            component_ref=component_change,
            translation_m=translation_change,  # type: ignore[arg-type]
            quaternion_wxyz=quaternion_change,  # type: ignore[arg-type]
        )

    axial_gap = float(placement.get("axial_gap_m", 0.0))
    offset = tuple(float(value) for value in placement.get("transverse_offset_m", (0.0, 0.0)))
    clocking = float(placement.get("clocking_rad", 0.0))
    misalignment = tuple(
        float(value) for value in placement.get("angular_misalignment_rad", (0.0, 0.0))
    )
    edited_gap_mm = st.number_input(
        "Axial gap (mm)",
        value=axial_gap * 1e3,
        key=f"placement:{project.config_hash}:{element_id}:gap",
    )
    offset_columns = st.columns(2)
    edited_offset_mm = tuple(
        offset_columns[index].number_input(
            f"Transverse offset {axis.upper()} (mm)",
            value=offset[index] * 1e3,
            key=f"placement:{project.config_hash}:{element_id}:offset:{axis}",
        )
        for index, axis in enumerate("uv")
    )
    edited_clocking_deg = st.number_input(
        "Clocking (deg)",
        value=math.degrees(clocking),
        key=f"placement:{project.config_hash}:{element_id}:clocking",
    )
    angle_columns = st.columns(2)
    edited_misalignment_deg = tuple(
        angle_columns[index].number_input(
            f"Angular misalignment {axis.upper()} (deg)",
            value=math.degrees(misalignment[index]),
            key=f"placement:{project.config_hash}:{element_id}:misalignment:{axis}",
        )
        for index, axis in enumerate("xy")
    )
    gap_change = None if math.isclose(edited_gap_mm * 1e-3, axial_gap, abs_tol=1.0e-12) else f"{edited_gap_mm:.12g} mm"
    offset_change = None
    edited_offset = tuple(value * 1e-3 for value in edited_offset_mm)
    if not _same_values(offset, edited_offset):
        offset_change = tuple(f"{value:.12g} mm" for value in edited_offset_mm)
    clocking_change = None
    if not math.isclose(math.radians(edited_clocking_deg), clocking, abs_tol=1.0e-12):
        clocking_change = f"{edited_clocking_deg:.12g} deg"
    edited_misalignment = tuple(math.radians(value) for value in edited_misalignment_deg)
    misalignment_change = None
    if not _same_values(misalignment, edited_misalignment):
        misalignment_change = tuple(f"{value:.12g} deg" for value in edited_misalignment_deg)
    if all(
        value is None
        for value in (
            component_change,
            gap_change,
            offset_change,
            clocking_change,
            misalignment_change,
        )
    ):
        return None
    return AssemblyElementEdits(
        element_id=element_id,
        component_ref=component_change,
        axial_gap_m=gap_change,
        transverse_offset_m=offset_change,  # type: ignore[arg-type]
        clocking_rad=clocking_change,
        angular_misalignment_rad=misalignment_change,  # type: ignore[arg-type]
    )


def _selected_object_editor(
    st: Any,
    project: Any,
    selected_object_id: str,
    *,
    mate_preview: MirrorTargetMatePreview | None,
) -> tuple[SimulationParameterEdits, AssemblyElementEdits | None]:
    scenario = project.active_scenario
    elements = list(scenario["optical_assembly"]["elements"])
    element = next((item for item in elements if str(item["id"]) == selected_object_id), None)
    target = next(
        (item for item in scenario["scene"]["targets"] if str(item["id"]) == selected_object_id),
        None,
    )

    if element is not None:
        component_type = str(project.catalog[str(element["component_ref"])].data["component_type"])
        parameter_edits = SimulationParameterEdits()
        if component_type in {"fiber_source", "beam_source"}:
            source = scenario["source"]
            st.markdown("#### 광원 운전점")
            wavelength_nm = st.number_input(
                "Wavelength (nm)",
                min_value=1.0,
                value=float(source["wavelength_m"]) * 1e9,
                key=f"source:{project.config_hash}:wavelength",
            )
            optical_power_mw = st.number_input(
                "Source power (mW)",
                min_value=0.0,
                value=float(source["optical_power_w"]) * 1e3,
                key=f"source:{project.config_hash}:power",
            )
            parameter_edits = SimulationParameterEdits(
                wavelength_m=(
                    None
                    if math.isclose(wavelength_nm * 1e-9, float(source["wavelength_m"]), abs_tol=1.0e-15)
                    else f"{wavelength_nm:.12g} nm"
                ),
                optical_power_w=(
                    None
                    if math.isclose(optical_power_mw * 1e-3, float(source["optical_power_w"]), abs_tol=1.0e-15)
                    else f"{optical_power_mw:.12g} mW"
                ),
            )
        elif component_type == "scanner_mirror":
            scanner = scenario["scanner"]
            st.markdown("#### Scanner pose")
            static_angle_deg = st.number_input(
                "Static command angle (deg)",
                value=math.degrees(float(scanner.get("static_command_angle_rad", 0.0))),
                key=f"scanner:{project.config_hash}:static_angle",
            )
            axis_values = tuple(float(value) for value in scanner["rotation_axis_world"])
            axis_keys = _scanner_axis_keys(project.config_hash)
            axis_columns = st.columns(3)
            rotation_axis = tuple(
                axis_columns[index].number_input(
                    f"Rotation axis {axis.upper()}",
                    value=axis_values[index],
                    key=axis_keys[index],
                    format="%.9f",
                )
                for index, axis in enumerate("xyz")
            )
            with st.expander("Ideal scan path 설정"):
                waveform_options = ["static", "triangle", "sinusoidal"]
                current_waveform = str(scanner["waveform"])
                waveform = st.selectbox(
                    "Scanner waveform",
                    waveform_options,
                    index=waveform_options.index(current_waveform),
                    key=f"scanner:{project.config_hash}:waveform",
                )
                amplitude_deg = st.number_input(
                    "Mechanical amplitude (deg)",
                    min_value=0.0,
                    value=math.degrees(float(scanner["mechanical_amplitude_rad"])),
                    disabled=waveform == "static",
                    key=f"scanner:{project.config_hash}:amplitude",
                )
                frequency_hz = st.number_input(
                    "Frequency (Hz)",
                    min_value=0.0,
                    value=float(scanner["frequency_hz"]),
                    disabled=waveform == "static",
                    key=f"scanner:{project.config_hash}:frequency",
                )
                samples_per_line = st.number_input(
                    "Samples per line",
                    min_value=1,
                    value=int(scanner["samples_per_line"]),
                    step=1,
                    key=f"scanner:{project.config_hash}:samples",
                )
            parameter_edits = SimulationParameterEdits(
                scanner_static_command_angle_rad=(
                    None
                    if math.isclose(
                        math.radians(static_angle_deg),
                        float(scanner.get("static_command_angle_rad", 0.0)),
                        abs_tol=1.0e-12,
                    )
                    else f"{static_angle_deg:.12g} deg"
                ),
                scanner_rotation_axis_world=(
                    None
                    if _same_values(axis_values, rotation_axis)
                    else rotation_axis  # type: ignore[arg-type]
                ),
                scanner_mechanical_amplitude_rad=(
                    None
                    if math.isclose(
                        0.0 if waveform == "static" else math.radians(amplitude_deg),
                        float(scanner["mechanical_amplitude_rad"]),
                        abs_tol=1.0e-12,
                    )
                    else "0 deg" if waveform == "static" else f"{amplitude_deg:.12g} deg"
                ),
                scanner_frequency_hz=(
                    None
                    if math.isclose(
                        0.0 if waveform == "static" else frequency_hz,
                        float(scanner["frequency_hz"]),
                        abs_tol=1.0e-12,
                    )
                    else "0 Hz" if waveform == "static" else f"{frequency_hz:.12g} Hz"
                ),
                scanner_waveform=None if waveform == str(scanner["waveform"]) else waveform,
                scanner_samples_per_line=(
                    None if int(samples_per_line) == int(scanner["samples_per_line"]) else int(samples_per_line)
                ),
            )
        st.markdown("#### Component placement")
        return (
            parameter_edits,
            _placement_editor(st, project, element, mate_preview=mate_preview),
        )

    if target is not None:
        geometry = target["geometry"]
        st.markdown("#### Target plane")
        center_columns = st.columns(3)
        center = tuple(
            center_columns[index].number_input(
                f"Target center {axis.upper()} (m)",
                value=float(geometry["center_m"][index]),
                key=f"target:{project.config_hash}:{selected_object_id}:center:{axis}",
            )
            for index, axis in enumerate("xyz")
        )
        normal_columns = st.columns(3)
        normal = tuple(
            normal_columns[index].number_input(
                f"Target normal {axis.upper()}",
                value=float(geometry["normal"][index]),
                key=f"target:{project.config_hash}:{selected_object_id}:normal:{axis}",
            )
            for index, axis in enumerate("xyz")
        )
        width = st.number_input(
            "Target width (m)",
            min_value=1.0e-6,
            value=float(geometry["width_m"]),
            key=f"target:{project.config_hash}:{selected_object_id}:width",
        )
        height = st.number_input(
            "Target height (m)",
            min_value=1.0e-6,
            value=float(geometry["height_m"]),
            key=f"target:{project.config_hash}:{selected_object_id}:height",
        )
        return (
            SimulationParameterEdits(
                target_id=selected_object_id,
                target_center_m=(
                    None
                    if _same_values(
                        tuple(float(value) for value in geometry["center_m"]),
                        center,
                    )
                    else tuple(f"{value:.12g} m" for value in center)
                ),
                target_normal=(
                    None
                    if _same_values(
                        tuple(float(value) for value in geometry["normal"]),
                        normal,
                    )
                    else normal  # type: ignore[arg-type]
                ),
                target_width_m=(
                    None
                    if math.isclose(width, float(geometry["width_m"]), abs_tol=1.0e-12)
                    else f"{width:.12g} m"
                ),
                target_height_m=(
                    None
                    if math.isclose(height, float(geometry["height_m"]), abs_tol=1.0e-12)
                    else f"{height:.12g} m"
                ),
            ),
            None,
        )

    if selected_object_id == "receiver":
        receiver = scenario["receiver"]
        st.markdown("#### Receiver")
        position_columns = st.columns(3)
        position = tuple(
            position_columns[index].number_input(
                f"Receiver position {axis.upper()} (m)",
                value=float(receiver["position_m"][index]),
                key=f"receiver:{project.config_hash}:position:{axis}",
            )
            for index, axis in enumerate("xyz")
        )
        direction_columns = st.columns(3)
        direction = tuple(
            direction_columns[index].number_input(
                f"Receiver direction {axis.upper()}",
                value=float(receiver["direction"][index]),
                key=f"receiver:{project.config_hash}:direction:{axis}",
            )
            for index, axis in enumerate("xyz")
        )
        aperture_mm = st.number_input(
            "Receiver aperture (mm)",
            min_value=1.0e-6,
            value=float(receiver["aperture_diameter_m"]) * 1e3,
            key=f"receiver:{project.config_hash}:aperture",
        )
        fov_deg = st.number_input(
            "Receiver full FOV (deg)",
            min_value=1.0e-6,
            max_value=180.0,
            value=math.degrees(float(receiver["full_fov_rad"])),
            key=f"receiver:{project.config_hash}:fov",
        )
        efficiency = st.number_input(
            "Receiver optical efficiency",
            min_value=0.0,
            max_value=1.0,
            value=float(receiver["optical_efficiency"]),
            key=f"receiver:{project.config_hash}:efficiency",
        )
        return (
            SimulationParameterEdits(
                receiver_position_m=(
                    None
                    if _same_values(
                        tuple(float(value) for value in receiver["position_m"]),
                        position,
                    )
                    else tuple(f"{value:.12g} m" for value in position)
                ),
                receiver_direction=(
                    None
                    if _same_values(
                        tuple(float(value) for value in receiver["direction"]),
                        direction,
                    )
                    else direction  # type: ignore[arg-type]
                ),
                receiver_aperture_diameter_m=(
                    None
                    if math.isclose(
                        aperture_mm * 1e-3,
                        float(receiver["aperture_diameter_m"]),
                        abs_tol=1.0e-12,
                    )
                    else f"{aperture_mm:.12g} mm"
                ),
                receiver_full_fov_rad=(
                    None
                    if math.isclose(
                        math.radians(fov_deg),
                        float(receiver["full_fov_rad"]),
                        abs_tol=1.0e-12,
                    )
                    else f"{fov_deg:.12g} deg"
                ),
                receiver_optical_efficiency=(
                    None
                    if math.isclose(
                        float(efficiency),
                        float(receiver["optical_efficiency"]),
                        abs_tol=1.0e-12,
                    )
                    else float(efficiency)
                ),
            ),
            None,
        )

    st.info("이 객체는 아직 numeric editor를 제공하지 않습니다.")
    return SimulationParameterEdits(), None


def run_streamlit_app(project_path: str | Path | None = None) -> None:
    """Interactive 3D workspace를 실행하고 모든 변경을 variant YAML로 저장한다."""

    import streamlit as st

    source_project_path = Path(project_path).resolve() if project_path else _project_argument()
    st.set_page_config(page_title="Optic Ray Workspace", layout="wide")
    st.title("Optic Ray Workspace")
    st.caption("Interactive optical bench · numeric placement · MirrorTargetMate preview")

    try:
        baseline_project = load_project(source_project_path)
        last_run = _ensure_preview_run(st, source_project_path, baseline_project)
        view_project = load_project(last_run.project_path)
        scene = build_viewport_scene(view_project)
    except Exception as exc:
        st.error(f"Project를 열거나 simulation preview를 만들 수 없습니다: {exc}")
        st.stop()
        return

    flash = st.session_state.pop("flash_success", None)
    if flash:
        st.success(str(flash))
    pending_selection = st.session_state.pop("pending_selected_object_id", None)
    component_ids = [component.element_id for component in scene.components]
    if pending_selection in component_ids:
        st.session_state["selected_object_id"] = pending_selection
    if st.session_state.get("selected_object_id") not in component_ids:
        default_id = str(view_project.active_scenario["scanner"]["element_id"])
        st.session_state["selected_object_id"] = default_id if default_id in component_ids else component_ids[0]

    st.sidebar.header("Project")
    st.sidebar.caption(f"scenario: {view_project.active_scenario['scenario_id']}")
    st.sidebar.caption(f"config: {view_project.config_hash[:12]}")
    st.sidebar.code(str(view_project.project_path))
    selected_object_id = st.sidebar.selectbox(
        "선택 객체",
        component_ids,
        key="selected_object_id",
        help="3D component marker를 선택해도 이 값이 바뀝니다.",
    )
    st.sidebar.markdown("#### Guides")
    show_ports = st.sidebar.checkbox("Optical / port axes", value=True)
    show_frames = st.sidebar.checkbox("Component local frames", value=False)
    show_mirror = st.sidebar.checkbox("Mirror normal", value=True)
    show_target = st.sidebar.checkbox("Target plane", value=True)
    show_fov = st.sidebar.checkbox("Receiver FOV", value=False)
    visible_guides: set[str] = set()
    if show_ports:
        visible_guides.update(("port_axis", "reflected_direction"))
    if show_frames:
        visible_guides.add("component_local_frame")
    if show_mirror:
        visible_guides.add("mirror_normal")
    if show_target:
        visible_guides.add("target_plane_edge")
    if show_fov:
        visible_guides.update(("receiver_fov", "receiver_look"))

    if st.sidebar.button("Baseline으로 돌아가기"):
        st.session_state.pop("last_run", None)
        st.session_state.pop("last_variant", None)
        st.session_state["flash_success"] = "Baseline project로 돌아왔습니다."
        st.rerun()

    mate_preview = None
    selected_component = next(
        (component for component in scene.components if component.element_id == selected_object_id),
        None,
    )
    if selected_component is not None and selected_component.component_type == "scanner_mirror":
        try:
            mate_preview = preview_mirror_target_mate(
                view_project,
                mirror_element_id=selected_object_id,
            )
        except Exception as exc:
            st.sidebar.warning(f"MirrorTargetMate preview를 만들 수 없습니다: {exc}")

    viewport_column, inspector_column = st.columns((3.0, 1.45), gap="large")
    with viewport_column:
        figure = build_interactive_viewport_figure(
            scene,
            selected_element_id=selected_object_id,
            visible_guide_types=visible_guides,
            mirror_mate_preview=mate_preview,
        )
        event = st.plotly_chart(
            figure,
            width="stretch",
            key=f"assembly_viewport_v2:{view_project.config_hash}",
            on_select="rerun",
            selection_mode="points",
            config={"displaylogo": False, "scrollZoom": True},
        )
        picked = _selection_event_element_id(event)
        if picked in component_ids and picked != selected_object_id:
            st.session_state["pending_selected_object_id"] = picked
            st.rerun()
        _render_metrics(st, last_run)
        _render_run_details(
            st,
            st.session_state.get("last_variant"),
            last_run,
        )

    with inspector_column:
        st.subheader(selected_object_id)
        if "default_variant_id" not in st.session_state:
            st.session_state["default_variant_id"] = (
                f"{view_project.active_scenario['scenario_id']}_ui_variant"
            )
        with st.expander("Variant 저장 설정"):
            variant_id = st.text_input(
                "Scenario ID",
                value=st.session_state["default_variant_id"],
                help="Baseline을 덮어쓰지 않고 configs/ui_runs 아래에 저장합니다.",
            )
            overwrite = st.checkbox("같은 ID의 기존 UI variant 덮어쓰기", value=False)
            include_scanner_path = st.checkbox("Ideal scanner path도 계산", value=False)
        submitted = st.button(
            "변경값 반영 · 시뮬레이션",
            type="primary",
            width="stretch",
            help="현재 편집값을 variant YAML로 저장하고 검증한 뒤 3D와 결과를 갱신합니다.",
        )
        pending_status = st.empty()
        st.caption("선택한 객체의 값만 표시합니다. 입력 후 위 버튼을 눌러 3D에 반영합니다.")
        parameter_edits, element_edits = _selected_object_editor(
            st,
            view_project,
            selected_object_id,
            mate_preview=mate_preview,
        )
        has_pending_edits = (
            parameter_edits != SimulationParameterEdits() or element_edits is not None
        )
        if has_pending_edits:
            pending_status.warning("편집값이 아직 3D와 config에 반영되지 않았습니다.")
        else:
            pending_status.success("현재 입력값과 3D simulation이 일치합니다.")
        st.caption("UI는 source of truth가 아닙니다. 저장된 YAML과 CLI 실행이 같은 결과를 재현합니다.")

    if submitted:
        root = find_project_root(view_project.project_path)
        output_dir = root / "configs" / "ui_runs"
        scenario_output = output_dir / f"{variant_id}.yaml"
        project_output = output_dir / f"{variant_id}_project.yaml"
        try:
            with st.spinner("Variant를 저장하고 optical simulation을 실행하는 중입니다..."):
                variant = create_simulation_variant(
                    project_path=view_project.project_path,
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
            st.session_state["flash_success"] = (
                "Variant 저장, validation과 simulation이 완료되었습니다. 3D overlay를 갱신했습니다."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"실행 실패: {exc}")


if __name__ == "__main__":
    run_streamlit_app()


__all__ = [
    "_component_options",
    "_project_argument",
    "_selection_event_element_id",
    "run_streamlit_app",
]
