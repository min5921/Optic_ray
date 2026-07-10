from __future__ import annotations

from pathlib import Path

import pytest


streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def _widget_by_label(widgets, label: str):
    return next(widget for widget in widgets if widget.label == label)


def test_streamlit_app_loads_and_runs_variant(
    copied_project: Path,
    project_root: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LIDARSIM_UI_PROJECT", str(copied_project))
    app_path = project_root / "src" / "lidarsim" / "ui" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60)

    app.run()

    assert not app.exception
    assert app.title[0].value == "Optic Ray Workspace"
    _widget_by_label(app.text_input, "Scenario ID").set_value("streamlit_test_variant")
    _widget_by_label(app.number_input, "Static command angle (deg)").set_value(1.0)
    _widget_by_label(app.number_input, "Samples per line").set_value(5)
    _widget_by_label(app.checkbox, "Ideal scanner path도 계산").uncheck()
    app.button[0].click().run()

    assert not app.exception
    assert any("완료" in item.value for item in app.success)
    output_dir = copied_project.parent / "ui_runs"
    assert (output_dir / "streamlit_test_variant.yaml").is_file()
    assert (output_dir / "streamlit_test_variant_project.yaml").is_file()
