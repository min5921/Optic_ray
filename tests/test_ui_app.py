from __future__ import annotations

from pathlib import Path

from lidarsim.config import load_project
from lidarsim.ui.app import _component_options, _project_argument, _selection_event_element_id


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
