"""Phase 2 optical train report visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_optical_train_view(
    report: Any,
    output_path: Path,
    *,
    dpi: int = 150,
) -> Path:
    """Phase 2 train report를 radius/power 요약 PNG로 그린다."""

    data = report.to_dict() if hasattr(report, "to_dict") else report
    states = data["optical_train"]["states"]
    x_m = [float(state["distance_along_path_m"]) for state in states]
    radius_x_mm = [float(state["beam_state"]["radius_x_m"]) * 1e3 for state in states]
    radius_y_mm = [float(state["beam_state"]["radius_y_m"]) * 1e3 for state in states]
    power_mw = [float(state["beam_state"]["power_w"]) * 1e3 for state in states]

    fig, axes = plt.subplots(2, 1, figsize=(9.0, 6.4), sharex=True)
    axes[0].plot(x_m, radius_x_mm, marker="o", label="x radius")
    axes[0].plot(x_m, radius_y_mm, marker="s", linestyle="--", label="y radius")
    axes[0].set_ylabel("1/e² radius (mm)")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    seen_positions: dict[float, int] = {}
    for state in states:
        x = float(state["distance_along_path_m"])
        duplicate_index = seen_positions.get(x, 0)
        seen_positions[x] = duplicate_index + 1
        label = str(state["label"])
        axes[0].axvline(x, color="0.75", linewidth=0.8, zorder=0)
        axes[0].annotate(
            label,
            xy=(x, max(radius_x_mm + radius_y_mm)),
            xytext=(4 + 11 * duplicate_index, -10 - 12 * duplicate_index),
            textcoords="offset points",
            rotation=75,
            fontsize=8,
            va="top",
        )

    axes[1].plot(x_m, power_mw, marker="o", color="#2ca02c")
    axes[1].set_xlabel("Optical path length from source output (m)")
    axes[1].set_ylabel("Power (mW)")
    axes[1].ticklabel_format(axis="y", style="plain", useOffset=False)
    axes[1].grid(True, alpha=0.3)

    summary = data["summary"]
    accuracy = data["accuracy"]
    receiver_power = float(summary.get("estimated_received_power_w", 0.0))
    title = (
        f"Phase 2 optical train | {summary['overall_status'].upper()} | "
        f"readiness={accuracy['hardware_readiness']} | final={summary['final_plane']} | "
        f"P_rx={receiver_power:.3e} W"
    )
    fig.suptitle(title)
    fig.tight_layout()

    resolved = output_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(resolved, dpi=dpi)
    plt.close(fig)
    return resolved
