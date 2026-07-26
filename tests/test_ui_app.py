from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lidarsim.config import load_project
from lidarsim.ui.app import (
    _component_options,
    _format_power,
    _project_argument,
    _render_metrics,
    _result_directory,
    _selection_event_element_id,
    _text,
)


class _MetricColumn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def metric(self, label: str, value: str, *, help: str | None = None) -> None:
        self.calls.append((label, value, help))


class _MetricStreamlit:
    def __init__(self) -> None:
        self.columns_result: list[_MetricColumn] = []

    def columns(self, count: int) -> list[_MetricColumn]:
        result = [_MetricColumn() for _ in range(count)]
        self.columns_result.extend(result)
        return result


def test_ui_project_argument_prefers_environment(
    project_root: Path,
    monkeypatch,
) -> None:
    project_path = project_root / "configs" / "project.yaml"
    monkeypatch.setenv("LIDARSIM_UI_PROJECT", str(project_path))

    assert _project_argument() == project_path.resolve()


def test_ui_component_options_keep_compatible_component_type(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    options = _component_options(project, "custom:ideal_collimator_f20")

    assert options == ["custom:ideal_collimator_f20", "custom:ideal_collimator_f35"]


def test_ui_plotly_selection_ignores_non_component_payload() -> None:
    assert _selection_event_element_id(None) is None
    assert _selection_event_element_id({"selection": {"points": [{}]}}) is None


def test_ui_project_settings_drive_language_power_and_result_root(
    copied_project: Path,
) -> None:
    project = load_project(copied_project)

    assert _text("ko", "selected_object") == "선택 객체"
    assert _text("en", "selected_object") == "Selected object"
    assert _format_power(0.01, "mW") == "10 mW"
    assert _format_power(0.001, "dBm") == "0 dBm"
    assert _result_directory(project, "variant", "1234567890") == (
        copied_project.parents[1] / "results" / "ui_runs" / "variant_12345678"
    ).resolve()


def test_r2_r3_r4_metrics_distinguish_calculated_zero_from_not_evaluated() -> None:
    streamlit = _MetricStreamlit()
    run = SimpleNamespace(
        summary={
            "estimated_power_on_target_w": 0.01,
            "estimated_received_power_w": 2.5e-9,
            "power_at_return_mirror_w": 0.0,
            "power_at_fiber_plane_w": None,
            "target_to_fiber_plane_link_loss_db": None,
            "fiber_coupling_efficiency": 0.0,
            "power_coupled_into_fiber_w": 0.0,
            "target_to_fiber_coupled_link_loss_db": None,
            "detector_input_status": "blocked",
            "power_at_detector_input_w": 0.0,
            "fiber_coupled_to_detector_input_link_loss_db": None,
            "target_to_detector_input_link_loss_db": None,
            "source_to_detector_input_round_trip_link_loss_db": None,
        }
    )

    _render_metrics(streamlit, run, language="ko", power_unit="nW")

    values = [column.calls[0][1] for column in streamlit.columns_result]
    assert values == [
        "1e+07 nW",
        "2.5 nW",
        "0 nW",
        "N/A",
        "N/A",
        "not_evaluated",
        "0",
        "0 nW",
        "N/A",
        "blocked",
        "0 nW",
        "N/A",
        "N/A",
        "N/A",
    ]
    labels = [column.calls[0][0] for column in streamlit.columns_result]
    assert labels[1:] == [
        "Virtual aperture (regression)",
        "Return mirror power",
        "Fiber-plane power",
        "Target→fiber-plane loss",
        "Fiber coupling status",
        "Fiber coupling efficiency",
        "Coupled fiber power",
        "Target→coupled-fiber loss",
        "Detector boundary status",
        "Detector optical input power",
        "Fiber→detector loss",
        "Target→detector loss",
        "Source→detector round-trip loss",
    ]
    assert "gaussian_alignment_proxy" in streamlit.columns_result[5].calls[0][2]
    assert "gaussian_alignment_proxy" in streamlit.columns_result[6].calls[0][2]
    assert "optical input boundary" in streamlit.columns_result[9].calls[0][2]
    assert "Photocurrent" in streamlit.columns_result[10].calls[0][2]
