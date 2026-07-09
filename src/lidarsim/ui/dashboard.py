"""Read-only Phase 2.3 optical workspace dashboard HTML."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import yaml

from lidarsim.results import Phase2OpticalTrainReport
from lidarsim.ui.assembly import ViewportScene


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _fmt(value: Any, *, unit: str = "", digits: int = 6) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _escape(value)
    if abs(number) >= 1.0e4 or (0.0 < abs(number) < 1.0e-3):
        rendered = f"{number:.{digits}e}"
    else:
        rendered = f"{number:.{digits}g}"
    return f"{rendered} {unit}".strip()


def _status_badge(value: Any) -> str:
    text = str(value)
    css_class = "ok" if text in {"pass", "inside_fov", "implemented"} else "warn"
    if text in {"fail", "outside_fov", "error", "invalid_geometry"}:
        css_class = "error"
    return f'<span class="badge {css_class}">{_escape(text)}</span>'


def _image_uri(path: str | Path) -> str:
    image_path = Path(path).resolve()
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return "data:image/png;base64," + payload


def _file_link(path: str | Path | None, *, label: str) -> str:
    if path is None:
        return "-"
    resolved = Path(path).resolve()
    return f'<code>{_escape(resolved)}</code> <span class="muted">({label})</span>'


def _card(label: str, value: str) -> str:
    return f'<div class="card"><strong>{_escape(label)}</strong>{value}</div>'


def _warning_items(report_data: dict[str, Any], scene: ViewportScene) -> str:
    warnings: list[str] = []
    warnings.extend(str(item) for item in report_data["accuracy"].get("warnings", ()))
    warnings.extend(str(item) for item in report_data["optical_train"].get("warnings", ()))
    warnings.extend(scene.warnings)
    for footprint in report_data["target_footprints"]:
        warnings.extend(str(item) for item in footprint.get("warnings", ()))
    for item in report_data["receiver_return"].get("returns", ()):
        warnings.extend(str(warning) for warning in item.get("warnings", ()))
    unique = list(dict.fromkeys(warnings))
    return "".join(f"<li><pre>{_escape(item)}</pre></li>" for item in unique) or "<li>없음</li>"


def _power_ledger_rows(report_data: dict[str, Any]) -> str:
    rows = []
    for entry in report_data["optical_train"]["power_ledger"]:
        rows.append(
            "<tr>"
            f"<td><code>{_escape(entry['element_id'])}</code></td>"
            f"<td>{_escape(entry['mechanism'])}</td>"
            f"<td>{_fmt(entry['input_power_w'], unit='W')}</td>"
            f"<td>{_fmt(entry['output_power_w'], unit='W')}</td>"
            f"<td>{_fmt(entry['loss_w'], unit='W')}</td>"
            f"<td>{_fmt(entry['transmission_fraction'])}</td>"
            f"<td>{_escape(entry.get('model_source', '-'))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _component_rows(report_data: dict[str, Any]) -> str:
    rows = []
    for item in report_data["optical_train"]["component_reports"]:
        if item.get("component_type") == "scanner_mirror":
            detail = (
                f"cmd={_fmt(item.get('scanner_command_angle_rad'), unit='rad')}, "
                f"incidence={_fmt(item.get('incidence_angle_rad'), unit='rad')}, "
                f"aperture={_escape(item.get('aperture_status'))}, "
                f"R={_fmt(item.get('power_reflectivity'))}"
            )
        else:
            aperture = item.get("aperture_clip", {})
            detail = (
                f"EFL={_fmt(item.get('effective_focal_length_m'), unit='m')}, "
                f"aperture={_escape(aperture.get('status', '-'))}, "
                f"T={_fmt(item.get('power_transmission'))}"
            )
        rows.append(
            "<tr>"
            f"<td><code>{_escape(item['element_id'])}</code></td>"
            f"<td>{_escape(item['component_type'])}</td>"
            f"<td><code>{_escape(item['component_ref'])}</code></td>"
            f"<td>{_escape(item.get('model_level', '-'))}</td>"
            f"<td>{_escape(detail)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _target_rows(report_data: dict[str, Any]) -> str:
    rows = []
    for item in report_data["target_footprints"]:
        rows.append(
            "<tr>"
            f"<td><code>{_escape(item['target_id'])}</code></td>"
            f"<td>{_status_badge('hit' if item['hit'] else item.get('miss_reason'))}</td>"
            f"<td>{_fmt(item.get('distance_to_target_m'), unit='m')}</td>"
            f"<td>{_fmt(item.get('projected_footprint_major_radius_m'), unit='m')}</td>"
            f"<td>{_fmt(item.get('projected_footprint_minor_radius_m'), unit='m')}</td>"
            f"<td>{_fmt(item.get('estimated_power_on_target_w'), unit='W')}</td>"
            f"<td>{_escape(item.get('clipped_by_target_bounds'))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _receiver_rows(report_data: dict[str, Any]) -> str:
    rows = []
    for item in report_data["receiver_return"]["returns"]:
        rows.append(
            "<tr>"
            f"<td><code>{_escape(item['target_id'])}</code></td>"
            f"<td>{_status_badge(item['status'])}</td>"
            f"<td>{_status_badge(item['receiver_fov_status'])}</td>"
            f"<td>{_fmt(item.get('material_reflectivity'))}</td>"
            f"<td>{_fmt(item.get('receiver_distance_m'), unit='m')}</td>"
            f"<td>{_fmt(item.get('estimated_received_power_w'), unit='W')}</td>"
            f"<td>{_fmt(item.get('link_loss_db'), unit='dB')}</td>"
            "</tr>"
        )
    return "".join(rows)


def _scanner_path_rows(scanner_path_data: dict[str, Any]) -> str:
    rows = []
    for item in scanner_path_data["samples"]:
        local = item.get("target_local_coordinates_m")
        rows.append(
            "<tr>"
            f"<td>{_fmt(1.0e3 * item['time_s'], unit='ms')}</td>"
            f"<td>{_fmt(item['line_position'])}</td>"
            f"<td>{_fmt(item['command_angle_deg'], unit='deg')}</td>"
            f"<td>{_status_badge(item['sample_status'])}</td>"
            f"<td>{'-' if local is None else _fmt(local[0], unit='m')}</td>"
            f"<td>{'-' if local is None else _fmt(local[1], unit='m')}</td>"
            f"<td>{_fmt(1.0e9 * item['estimated_received_power_w'], unit='nW')}</td>"
            "</tr>"
        )
    return "".join(rows)


def _assumption_items(report_data: dict[str, Any]) -> str:
    assumptions: list[str] = []
    assumptions.extend(str(item) for item in report_data["model"].get("limitations", ()))
    assumptions.extend(str(item) for item in report_data["receiver_return"].get("assumptions", ()))
    for footprint in report_data["target_footprints"]:
        assumptions.extend(str(item) for item in footprint.get("assumptions", ()))
    unique = list(dict.fromkeys(assumptions))
    return "".join(f"<li>{_escape(item)}</li>" for item in unique) or "<li>없음</li>"


def write_workspace_dashboard_html(
    *,
    project: Any,
    report: Phase2OpticalTrainReport | dict[str, Any],
    scene: ViewportScene,
    workspace_image: str | Path,
    optical_train_image: str | Path,
    output_path: str | Path,
    report_path: str | Path | None = None,
    scene_path: str | Path | None = None,
    scanner_path: Any | None = None,
    scanner_path_image: str | Path | None = None,
    scanner_path_report_path: str | Path | None = None,
    scanner_path_csv_path: str | Path | None = None,
) -> Path:
    """Phase 2.3 read-only optical workspace dashboard를 self-contained HTML로 저장한다."""

    report_data = report.to_dict() if hasattr(report, "to_dict") else dict(report)
    summary = report_data["summary"]
    accuracy = report_data["accuracy"]
    workspace_uri = _image_uri(workspace_image)
    optical_train_uri = _image_uri(optical_train_image)
    scanner_path_data = (
        None if scanner_path is None else scanner_path.to_dict() if hasattr(scanner_path, "to_dict") else dict(scanner_path)
    )
    scanner_path_uri = None if scanner_path_image is None else _image_uri(scanner_path_image)
    summary_yaml = yaml.safe_dump(summary, sort_keys=False, allow_unicode=True)
    scene_counts = {
        "components": len(scene.components),
        "ports": len(scene.ports),
        "guides": len(scene.guides),
        "rays": len(scene.rays),
        "footprints": len(scene.footprints),
    }
    scene_yaml = yaml.safe_dump(scene_counts, sort_keys=False, allow_unicode=True)
    scanner_file_rows = ""
    if scanner_path_report_path is not None:
        scanner_file_rows += (
            "<tr><td>Scanner path YAML</td><td>"
            f"{_file_link(scanner_path_report_path, label='ideal path report')}</td></tr>"
        )
    if scanner_path_csv_path is not None:
        scanner_file_rows += (
            "<tr><td>Scanner path CSV</td><td>"
            f"{_file_link(scanner_path_csv_path, label='table')}</td></tr>"
        )
    if scanner_path_image is not None:
        scanner_file_rows += (
            "<tr><td>Scanner path PNG</td><td>"
            f"{_file_link(scanner_path_image, label='plot')}</td></tr>"
        )
    scanner_path_section = ""
    if scanner_path_data is not None and scanner_path_uri is not None:
        scanner_summary_yaml = yaml.safe_dump(
            scanner_path_data["summary"],
            sort_keys=False,
            allow_unicode=True,
        )
        scanner_path_section = f"""
<section><h2>Scanner path — ideal forward line</h2>
<div class="callout">
이 section은 optional ideal command-path reference입니다. Motor/galvo dynamics, lag, jitter,
bidirectional return stroke와 calibration table은 아직 포함하지 않습니다.
</div>
<div class="cards">
  {_card("Waveform", _escape(scanner_path_data["waveform"]))}
  {_card("Samples", _fmt(scanner_path_data["sample_count"]))}
  {_card("Line duration", _fmt(scanner_path_data["line_duration_s"], unit="s"))}
  {_card("Positive returns", _fmt(scanner_path_data["summary"]["positive_return_count"]))}
</div>
<img class="hero" src="{scanner_path_uri}" alt="Scanner path plot">
<h3>Scanner path samples</h3>
<table>
<tr><th>Time</th><th>Line pos.</th><th>Command</th><th>Status</th><th>Target u</th><th>Target v</th><th>P_rx</th></tr>
{_scanner_path_rows(scanner_path_data)}
</table>
<details><summary>Scanner path summary</summary><pre>{_escape(scanner_summary_yaml)}</pre></details>
</section>"""
    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Optic Ray Workspace Dashboard</title>
<style>
body {{ margin: 0; background: #f4f6f8; color: #1f2933; font-family: "Malgun Gothic", "Noto Sans KR", sans-serif; }}
main {{ max-width: 1320px; margin: auto; padding: 24px; }}
h1, h2, h3 {{ margin-bottom: 10px; }}
.subtitle, .muted {{ color: #52606d; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
.card, section {{ background: white; border: 1px solid #d9e2ec; border-radius: 12px; padding: 16px; box-shadow: 0 2px 5px #0000000d; }}
.card strong {{ display: block; color: #52606d; font-size: 13px; margin-bottom: 8px; }}
section {{ margin: 16px 0; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #e4e7eb; padding: 9px; text-align: left; vertical-align: top; }}
th {{ background: #f0f4f8; }}
.badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-weight: 700; font-size: 12px; }}
.ok {{ background: #d3f9d8; color: #166534; }} .warn {{ background: #fff3bf; color: #854d0e; }} .error {{ background: #ffe3e3; color: #991b1b; }}
.grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
.hero {{ width: 100%; height: auto; border-radius: 8px; border: 1px solid #e4e7eb; }}
.callout {{ border-left: 5px solid #f59f00; background: #fff9db; padding: 12px; border-radius: 6px; }}
code, pre {{ font-family: Consolas, monospace; white-space: pre-wrap; margin: 0; }}
details {{ margin-top: 10px; }}
</style>
</head>
<body><main>
<h1>Optic Ray Workspace Dashboard</h1>
<div class="subtitle">
  <code>{_escape(project.project['project_id'])} / {_escape(project.active_scenario['scenario_id'])}</code>
  · config <code>{_escape(project.config_hash)}</code>
</div>
<div class="cards">
  {_card("Overall", _status_badge(summary["overall_status"]))}
  {_card("Hardware readiness", _status_badge(accuracy["hardware_readiness"]))}
  {_card("Final power", _fmt(summary["final_power_w"], unit="W"))}
  {_card("Total transmission", _fmt(summary["total_transmission"]))}
  {_card("Target hits", _fmt(summary["target_hit_count"]))}
  {_card("Power on target", _fmt(summary["estimated_power_on_target_w"], unit="W"))}
  {_card("Received power", _fmt(summary["estimated_received_power_w"], unit="W"))}
  {_card("Link loss", _fmt(summary["link_loss_db"], unit="dB"))}
</div>
<div class="callout">
현재 dashboard는 read-only 결과 viewer입니다. Placement edit, snapping, constraint, scanner time dynamics는 아직 구현하지 않았으며,
모든 값은 YAML config와 Phase 2.3 report에서 생성됩니다.
</div>
<section><h2>생성 파일</h2><table>
<tr><th>파일</th><th>경로</th></tr>
<tr><td>Dashboard HTML</td><td><code>{_escape(Path(output_path).resolve())}</code></td></tr>
<tr><td>Phase 2 report YAML</td><td>{_file_link(report_path, label="schema/report")}</td></tr>
<tr><td>ViewportScene YAML</td><td>{_file_link(scene_path, label="UI contract")}</td></tr>
{scanner_file_rows}
</table></section>
<section><h2>시각화</h2><div class="grid2">
<div><h3>Optical assembly workspace</h3><img class="hero" src="{workspace_uri}" alt="Optical assembly workspace"></div>
<div><h3>Optical train radius / power</h3><img class="hero" src="{optical_train_uri}" alt="Optical train plot"></div>
</div></section>
{scanner_path_section}
<section><h2>Optical component report</h2><table>
<tr><th>Element</th><th>Type</th><th>Catalog</th><th>Model level</th><th>주요 값</th></tr>
{_component_rows(report_data)}
</table></section>
<section><h2>Power ledger</h2><table>
<tr><th>Element</th><th>Mechanism</th><th>Input</th><th>Output</th><th>Loss</th><th>Transmission</th><th>Source</th></tr>
{_power_ledger_rows(report_data)}
</table></section>
<section><h2>Target footprint</h2><table>
<tr><th>Target</th><th>Status</th><th>Distance</th><th>Major radius</th><th>Minor radius</th><th>Power on target</th><th>Clipped</th></tr>
{_target_rows(report_data)}
</table></section>
<section><h2>Receiver return</h2><table>
<tr><th>Target</th><th>Status</th><th>FOV</th><th>Reflectivity</th><th>Distance</th><th>Received power</th><th>Link loss</th></tr>
{_receiver_rows(report_data)}
</table></section>
<section><h2>경고</h2><ul>{_warning_items(report_data, scene)}</ul></section>
<section><h2>가정과 한계</h2><ul>{_assumption_items(report_data)}</ul></section>
<section><h2>Raw summary</h2>
<details open><summary>Phase 2 summary</summary><pre>{_escape(summary_yaml)}</pre></details>
<details><summary>Viewport scene counts</summary><pre>{_escape(scene_yaml)}</pre></details>
</section>
</main></body></html>"""
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    return destination


__all__ = ["write_workspace_dashboard_html"]
