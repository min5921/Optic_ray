"""Phase 0.1 상태를 한눈에 확인하는 standalone HTML review."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

from lidarsim.config.physical import IMPLEMENTED_OUTPUTS
from lidarsim.results.reports import Phase0Report


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status_badge(value: str) -> str:
    safe = _escape(value)
    css_class = "ok" if value in {"pass", "comparative", "calibrated", "implemented"} else "warn"
    if value in {"fail", "out_of_validity"}:
        css_class = "error"
    return f'<span class="badge {css_class}">{safe}</span>'


def write_review_html(
    project: Any,
    report: Phase0Report,
    placement_image: str | Path,
    output_path: str | Path,
) -> Path:
    """외부 server 없이 열 수 있는 self-contained HTML review를 저장한다."""

    image_path = Path(placement_image).resolve()
    image_uri = "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")
    scenario = project.active_scenario
    placement = report.placement["elements"]
    component_rows: list[str] = []
    for element_id, element in placement.items():
        record = project.catalog[element["component_ref"]].data
        origin = ", ".join(f"{float(value):.6g}" for value in element["translation_world_m"])
        interfaces = ", ".join(
            f"{port_id}:{port['interface_type']}"
            for port_id, port in element["ports"].items()
        ) or "-"
        component_rows.append(
            "<tr>"
            f"<td>{_escape(element_id)}</td>"
            f"<td>{_escape(record.get('component_type'))}</td>"
            f"<td><code>{_escape(element['component_ref'])}</code></td>"
            f"<td>{_escape(record.get('model_level'))}</td>"
            f"<td><code>[{_escape(origin)}] m</code></td>"
            f"<td>{_escape(interfaces)}</td>"
            "</tr>"
        )

    output_rows = []
    for output in scenario["outputs"]:
        implemented = output in IMPLEMENTED_OUTPUTS
        output_rows.append(
            "<tr>"
            f"<td><code>{_escape(output)}</code></td>"
            f"<td>{_status_badge('implemented' if implemented else 'not_evaluated')}</td>"
            "</tr>"
        )

    warning_items = "".join(
        f"<li><pre>{_escape(warning)}</pre></li>" for warning in report.accuracy.warnings
    ) or "<li>없음</li>"
    convergence_rows = "".join(
        "<tr>"
        f"<td><code>{_escape(check.check_id)}</code></td>"
        f"<td>{_status_badge(check.status)}</td>"
        f"<td>{_escape(check.message)}</td>"
        "</tr>"
        for check in report.convergence.checks
    )
    source = scenario["source"]
    receiver = scenario["receiver"]
    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Optic Ray Phase 0.1 Review</title>
<style>
body {{ margin: 0; background: #f4f6f8; color: #1f2933; font-family: "Malgun Gothic", "Noto Sans KR", sans-serif; }}
main {{ max-width: 1180px; margin: auto; padding: 24px; }}
h1, h2 {{ margin-bottom: 10px; }}
.subtitle {{ color: #52606d; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 18px 0; }}
.card, section {{ background: white; border: 1px solid #d9e2ec; border-radius: 10px; padding: 16px; box-shadow: 0 2px 5px #0000000d; }}
.card strong {{ display: block; color: #52606d; font-size: 13px; margin-bottom: 8px; }}
section {{ margin: 16px 0; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #e4e7eb; padding: 9px; text-align: left; vertical-align: top; }}
th {{ background: #f0f4f8; }}
.badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-weight: 700; font-size: 12px; }}
.ok {{ background: #d3f9d8; color: #166534; }} .warn {{ background: #fff3bf; color: #854d0e; }} .error {{ background: #ffe3e3; color: #991b1b; }}
.hero {{ width: 100%; height: auto; border-radius: 6px; }}
.callout {{ border-left: 5px solid #f59f00; background: #fff9db; padding: 12px; }}
code, pre {{ font-family: Consolas, monospace; white-space: pre-wrap; margin: 0; }}
</style>
</head>
<body><main>
<h1>Phase 0.1 LiDAR setup review</h1>
<div class="subtitle"><code>{_escape(project.project['project_id'])} / {_escape(scenario['scenario_id'])}</code> · config <code>{_escape(project.config_hash)}</code></div>
<div class="cards">
  <div class="card"><strong>Scenario 목적</strong>{_status_badge(report.accuracy.model_purpose)}</div>
  <div class="card"><strong>Hardware readiness</strong>{_status_badge(report.accuracy.hardware_readiness)}</div>
  <div class="card"><strong>Confidence</strong>{_status_badge(report.accuracy.confidence_level)}</div>
  <div class="card"><strong>Receiver</strong>{_escape(report.accuracy.receiver_model)}</div>
  <div class="card"><strong>Energy</strong>{_status_badge(report.energy_ledger.status)}</div>
  <div class="card"><strong>Convergence</strong>{_status_badge(report.convergence.overall_status)}</div>
</div>
<div class="callout">현재 baseline은 실제 제품 예측이 아니라 analytical regression 기준입니다. 실제 수신광 계산은 아직 수행하지 않습니다.</div>
<section><h2>Placement와 시야</h2><img class="hero" src="{image_uri}" alt="2D and 3D placement view"></section>
<section><h2>운전 조건</h2><table>
<tr><th>항목</th><th>값</th></tr>
<tr><td>Wavelength</td><td>{float(source['wavelength_m']):.9g} m</td></tr>
<tr><td>Source power</td><td>{float(source['optical_power_w']):.9g} W</td></tr>
<tr><td>Scanner</td><td>{_escape(scenario['scanner']['type'])}, ±{float(scenario['scanner']['mechanical_amplitude_rad']):.6g} rad mechanical</td></tr>
<tr><td>Receiver</td><td>{_escape(receiver['architecture'])}, aperture {float(receiver['aperture_diameter_m']):.6g} m, full FOV {float(receiver['full_fov_rad']):.6g} rad</td></tr>
</table></section>
<section><h2>Component와 port interface</h2><table>
<tr><th>Element</th><th>Type</th><th>Catalog ID</th><th>Model level</th><th>World origin</th><th>Port interface</th></tr>
{''.join(component_rows)}
</table></section>
<section><h2>요청 output 지원 상태</h2><table><tr><th>Output</th><th>상태</th></tr>{''.join(output_rows)}</table></section>
<section><h2>Numerical check</h2><table><tr><th>Check</th><th>상태</th><th>설명</th></tr>{convergence_rows}</table></section>
<section><h2>경고와 제한</h2><ul>{warning_items}</ul></section>
</main></body></html>"""
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    return destination
