from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project


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
    assert _widget_by_label(app.radio, "3D 보기 범위").value == "광학 헤드 확대"
    assert _widget_by_label(
        app.checkbox,
        "같은 ID의 기존 UI variant 덮어쓰기",
    ).value is True
    _widget_by_label(app.text_input, "Scenario ID").set_value("streamlit_test_variant")
    _widget_by_label(app.number_input, "Static command angle (deg)").set_value(1.0).run()
    assert any("아직 3D" in item.value for item in app.warning)
    assert any("현재 3D simulation 적용각: 0" in item.value for item in app.caption)
    _widget_by_label(app.number_input, "Samples per line").set_value(5)
    _widget_by_label(app.checkbox, "Ideal scanner path도 계산").uncheck()
    _widget_by_label(app.button, "변경값 반영 · 시뮬레이션").click().run()

    assert not app.exception
    assert any("완료" in item.value for item in app.success)
    output_dir = copied_project.parent / "ui_runs"
    assert (output_dir / "streamlit_test_variant.yaml").is_file()
    assert (output_dir / "streamlit_test_variant_project.yaml").is_file()
    scenario = yaml.safe_load(
        (output_dir / "streamlit_test_variant.yaml").read_text(encoding="utf-8")
    )
    assert scenario["scanner"]["static_command_angle_rad"] == "1 deg"
    result_directories = list(
        (copied_project.parents[1] / "results" / "ui_runs").glob("streamlit_test_variant_*")
    )
    assert len(result_directories) == 1
    scene = yaml.safe_load(
        (result_directories[0] / "viewport_scene.yaml").read_text(encoding="utf-8")
    )
    target_ray = next(ray for ray in scene["rays"] if ray["status"] == "target_hit")
    assert abs(float(target_ray["end_m"][2])) > 0.1

    _widget_by_label(app.number_input, "Static command angle (deg)").set_value(2.0).run()
    assert any("이미 있습니다" in item.value for item in app.info)
    _widget_by_label(app.button, "변경값 반영 · 시뮬레이션").click().run()

    assert not app.exception
    assert any("완료" in item.value for item in app.success)
    overwritten = yaml.safe_load(
        (output_dir / "streamlit_test_variant.yaml").read_text(encoding="utf-8")
    )
    assert overwritten["scanner"]["static_command_angle_rad"] == "2 deg"


def test_streamlit_app_refreshes_when_active_config_changes(
    copied_project: Path,
    project_root: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LIDARSIM_UI_PROJECT", str(copied_project))
    app_path = project_root / "src" / "lidarsim" / "ui" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60)

    app.run()
    assert not app.exception

    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scene"]["targets"][0]["geometry"]["center_m"] = ["12 m", "0 m", "0 m"]
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    refreshed_project = load_project(copied_project)

    app.run()

    assert not app.exception
    refreshed_scene = (
        copied_project.parents[1]
        / "results"
        / "ui_preview"
        / f"baseline_1550nm_{refreshed_project.config_hash[:8]}"
        / "viewport_scene.yaml"
    )
    assert refreshed_scene.is_file()
    scene = yaml.safe_load(refreshed_scene.read_text(encoding="utf-8"))
    target = next(item for item in scene["components"] if item["element_id"] == "target_plane")
    assert target["origin_world_m"] == pytest.approx([12.0, 0.0, 0.0])


def test_streamlit_project_draft_preserves_and_discards_multiple_objects(
    copied_project: Path,
    project_root: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LIDARSIM_UI_PROJECT", str(copied_project))
    app_path = project_root / "src" / "lidarsim" / "ui" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60)

    app.run()
    _widget_by_label(app.number_input, "Static command angle (deg)").set_value(1.0).run()
    assert any("변경 객체: scan_mirror" in item.value for item in app.caption)

    _widget_by_label(app.selectbox, "선택 객체").set_value("target_plane").run()
    _widget_by_label(app.number_input, "Target center X (m)").set_value(12.0).run()
    assert any(
        "scan_mirror, target_plane" in item.value
        for item in app.caption
    )

    _widget_by_label(app.button, "선택 객체 변경 버리기").click().run()
    assert not app.exception
    assert any("선택 객체의 draft 변경" in item.value for item in app.info)
    assert _widget_by_label(app.number_input, "Target center X (m)").value == pytest.approx(
        10.0
    )
    assert any("변경 객체: scan_mirror" in item.value for item in app.caption)

    _widget_by_label(app.number_input, "Target center X (m)").set_value(12.0).run()
    _widget_by_label(app.text_input, "Scenario ID").set_value("multi_object_streamlit")
    _widget_by_label(app.checkbox, "Ideal scanner path도 계산").uncheck()
    _widget_by_label(app.button, "변경값 반영 · 시뮬레이션").click().run()

    assert not app.exception
    scenario_path = copied_project.parent / "ui_runs" / "multi_object_streamlit.yaml"
    provenance_path = (
        copied_project.parent / "ui_runs" / "multi_object_streamlit_provenance.yaml"
    )
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    assert scenario["scanner"]["static_command_angle_rad"] == "1 deg"
    assert scenario["scene"]["targets"][0]["geometry"]["center_m"] == [
        "12 m",
        "0 m",
        "0 m",
    ]
    assert provenance_path.is_file()


def test_streamlit_honors_english_manual_draft_and_power_display_settings(
    copied_project: Path,
    project_root: Path,
    monkeypatch,
) -> None:
    raw_project = yaml.safe_load(copied_project.read_text(encoding="utf-8"))
    raw_project["ui"] = {"language": "en", "autosave_drafts": False}
    raw_project["display_units"]["power"] = "dBm"
    copied_project.write_text(
        yaml.safe_dump(raw_project, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setenv("LIDARSIM_UI_PROJECT", str(copied_project))
    app_path = project_root / "src" / "lidarsim" / "ui" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60)

    app.run()

    assert not app.exception
    assert app.title[0].value == "Optic Ray Assembly Workspace"
    assert _widget_by_label(app.selectbox, "Selected object").value == "scan_mirror"
    assert _widget_by_label(app.radio, "3D view range").value == "Optical head close-up"
    assert any(str(metric.value).endswith("dBm") for metric in app.metric)
    assert any("display_units.power" in item.value for item in app.warning)

    _widget_by_label(app.number_input, "Static command angle (deg)").set_value(1.0).run()
    _widget_by_label(app.button, "Add selected object to draft").click().run()
    assert any("Changed objects: scan_mirror" in item.value for item in app.caption)
