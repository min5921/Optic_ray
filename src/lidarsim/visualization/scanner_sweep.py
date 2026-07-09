"""Static scanner sweep visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FormatStrFormatter, NullFormatter

from lidarsim.scanner import ScannerSweepResult


def _sample_dicts(result: ScannerSweepResult | dict[str, Any]) -> list[dict[str, Any]]:
    data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    return list(data["samples"])


def _values(samples: list[dict[str, Any]], field: str) -> np.ndarray:
    values = []
    for sample in samples:
        value = sample.get(field)
        values.append(np.nan if value is None else float(value))
    return np.asarray(values, dtype=np.float64)


def render_scanner_sweep_view(
    result: ScannerSweepResult | dict[str, Any],
    output_path: Path,
    *,
    dpi: int = 150,
) -> Path:
    """Render static scanner angle sweep hit/return trends."""

    samples = _sample_dicts(result)
    if not samples:
        raise ValueError("scanner sweep plot에는 최소 1개의 sample이 필요합니다.")
    angles = _values(samples, "command_angle_deg")
    local_u = np.asarray(
        [
            np.nan
            if sample.get("target_local_coordinates_m") is None
            else float(sample["target_local_coordinates_m"][0])
            for sample in samples
        ],
        dtype=np.float64,
    )
    local_v = np.asarray(
        [
            np.nan
            if sample.get("target_local_coordinates_m") is None
            else float(sample["target_local_coordinates_m"][1])
            for sample in samples
        ],
        dtype=np.float64,
    )
    received_power = _values(samples, "estimated_received_power_w")

    fig, (hit_ax, power_ax) = plt.subplots(2, 1, figsize=(9.2, 7.2), sharex=True)
    hit_ax.plot(angles, local_u, marker="o", label="target local u")
    hit_ax.plot(angles, local_v, marker="s", label="target local v")
    hit_ax.axhline(0.0, color="#868e96", linewidth=0.8, linestyle="--")
    hit_ax.set_ylabel("Target local coordinate (m)")
    hit_ax.set_title("Static scanner command-angle sweep")
    hit_ax.xaxis.set_major_formatter(FormatStrFormatter("%.3g"))
    hit_ax.yaxis.set_major_formatter(FormatStrFormatter("%.3g"))
    hit_ax.xaxis.set_minor_formatter(NullFormatter())
    hit_ax.yaxis.set_minor_formatter(NullFormatter())
    hit_ax.xaxis.get_offset_text().set_visible(False)
    hit_ax.yaxis.get_offset_text().set_visible(False)
    hit_ax.grid(True, alpha=0.25)
    hit_ax.legend(loc="best")

    received_power_nw = received_power * 1.0e9
    power_ax.plot(angles, received_power_nw, marker="o", color="#2b8a3e")
    power_ax.set_ylabel("Estimated received power (nW)")
    power_ax.set_xlabel("Static scanner command angle (deg)")
    power_ax.xaxis.set_major_formatter(FormatStrFormatter("%.3g"))
    power_ax.yaxis.set_major_formatter(FormatStrFormatter("%.3g"))
    power_ax.xaxis.set_minor_formatter(NullFormatter())
    power_ax.yaxis.set_minor_formatter(NullFormatter())
    power_ax.xaxis.get_offset_text().set_visible(False)
    power_ax.yaxis.get_offset_text().set_visible(False)
    power_ax.grid(True, alpha=0.25, which="both")

    for sample in samples:
        if sample.get("sample_status") not in {"positive_return", "zero_return"}:
            power_ax.annotate(
                str(sample.get("sample_status")),
                xy=(float(sample["command_angle_deg"]), 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(0, -18),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                rotation=30,
                color="#d9480f",
            )

    fig.tight_layout()
    path = output_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
