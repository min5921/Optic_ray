"""Ideal scanner line-path visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FormatStrFormatter, NullFormatter

from lidarsim.scanner import ScannerPathResult


def _sample_dicts(result: ScannerPathResult | dict[str, Any]) -> list[dict[str, Any]]:
    data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    return list(data["samples"])


def _array(samples: list[dict[str, Any]], field: str) -> np.ndarray:
    return np.asarray([float(sample[field]) for sample in samples], dtype=np.float64)


def _local(samples: list[dict[str, Any]], index: int) -> np.ndarray:
    return np.asarray(
        [
            np.nan
            if sample.get("target_local_coordinates_m") is None
            else float(sample["target_local_coordinates_m"][index])
            for sample in samples
        ],
        dtype=np.float64,
    )


def _format_axis(ax: Any) -> None:
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.3g"))
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.3g"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.xaxis.get_offset_text().set_visible(False)
    ax.yaxis.get_offset_text().set_visible(False)
    ax.grid(True, alpha=0.25)


def render_scanner_path_view(
    result: ScannerPathResult | dict[str, Any],
    output_path: Path,
    *,
    dpi: int = 150,
) -> Path:
    """Render ideal scanner line command, hit coordinate and received power."""

    samples = _sample_dicts(result)
    if not samples:
        raise ValueError("scanner path plot에는 최소 1개의 sample이 필요합니다.")
    time_ms = _array(samples, "time_s") * 1.0e3
    command_deg = _array(samples, "command_angle_deg")
    local_u = _local(samples, 0)
    local_v = _local(samples, 1)
    received_nw = _array(samples, "estimated_received_power_w") * 1.0e9

    fig, axes = plt.subplots(3, 1, figsize=(9.4, 8.4), sharex=True)
    command_ax, hit_ax, power_ax = axes
    command_ax.plot(time_ms, command_deg, marker="o", color="#1c7ed6")
    command_ax.set_ylabel("Command angle (deg)")
    command_ax.set_title("Ideal scanner forward-line path")

    hit_ax.plot(time_ms, local_u, marker="o", label="target local u")
    hit_ax.plot(time_ms, local_v, marker="s", label="target local v")
    hit_ax.axhline(0.0, color="#868e96", linewidth=0.8, linestyle="--")
    hit_ax.set_ylabel("Target local coord. (m)")
    hit_ax.legend(loc="best")

    power_ax.plot(time_ms, received_nw, marker="o", color="#2b8a3e")
    power_ax.set_ylabel("P_rx (nW)")
    power_ax.set_xlabel("Time in forward line (ms)")

    for ax in axes:
        _format_axis(ax)

    fig.tight_layout()
    path = output_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
