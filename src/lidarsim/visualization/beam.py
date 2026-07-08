"""Phase 1 Gaussian beam envelope와 local irradiance plot."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "optic-ray-matplotlib"),
)

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullFormatter, ScalarFormatter

from lidarsim.beam import BeamState


def render_beam_view(
    beam: BeamState,
    output_path: str | Path,
    *,
    z_max_m: float,
    sample_count: int = 201,
    profile_distance_m: float | None = None,
    grid_size: int = 301,
    extent_radii: float = 4.0,
    dpi: int = 150,
    hardware_readiness: str = "analytical_only",
    paraxial_status: str = "not_evaluated",
) -> Path:
    """Radius envelope, irradiance map과 center cross-section을 PNG로 저장한다."""

    maximum = float(z_max_m)
    profile_distance = maximum if profile_distance_m is None else float(profile_distance_m)
    if maximum <= 0.0 or not 0.0 <= profile_distance <= maximum:
        raise ValueError("Plot distance 범위가 올바르지 않습니다.")
    distances = np.linspace(0.0, maximum, int(sample_count), dtype=np.float64)
    radius_x, radius_y = beam.radius_at(distances)
    profile = beam.sample_profile(
        distance_m=profile_distance,
        grid_size=grid_size,
        extent_radii=extent_radii,
    )

    figure, axes = plt.subplots(1, 3, figsize=(15.0, 5.2), constrained_layout=True)
    axes[0].plot(distances, np.asarray(radius_x) * 1e3, label="x radius")
    axes[0].plot(distances, np.asarray(radius_y) * 1e3, label="y radius", linestyle="--")
    positive_radii = np.concatenate((np.asarray(radius_x), np.asarray(radius_y)))
    if float(np.max(positive_radii) / np.min(positive_radii)) > 50.0:
        axes[0].set_yscale("log")
        axes[0].yaxis.set_major_formatter(ScalarFormatter())
        axes[0].yaxis.set_minor_formatter(NullFormatter())
    rayleigh_markers = {
        "x Rayleigh": beam.rayleigh_range_x_m - beam.distance_from_waist_m,
        "y Rayleigh": beam.rayleigh_range_y_m - beam.distance_from_waist_m,
    }
    used_marker_positions: list[float] = []
    for label, marker in rayleigh_markers.items():
        if not 0.0 <= marker <= maximum:
            continue
        if any(abs(marker - used) <= maximum * 1e-9 for used in used_marker_positions):
            continue
        axes[0].axvline(marker, color="#777777", linestyle=":", linewidth=1.0, label=label)
        used_marker_positions.append(marker)
    axes[0].set_title("Free-space 1/e² radius")
    axes[0].set_xlabel("Distance from source plane (m)")
    axes[0].set_ylabel("Radius (mm)")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    extent = (
        profile.x_m[0] * 1e3,
        profile.x_m[-1] * 1e3,
        profile.y_m[0] * 1e3,
        profile.y_m[-1] * 1e3,
    )
    image = axes[1].imshow(
        profile.irradiance_w_m2,
        origin="lower",
        extent=extent,
        aspect="equal",
        cmap="inferno",
    )
    aspect_ratio = profile.radius_x_m / profile.radius_y_m
    axes[1].set_title(
        f"Irradiance at z={profile_distance:.6g} m\n"
        f"physical radius ratio x/y={aspect_ratio:.4g}"
    )
    axes[1].set_xlabel("Local x (mm)")
    axes[1].set_ylabel("Local y (mm)")
    figure.colorbar(image, ax=axes[1], label="W/m²")

    center_y = len(profile.y_m) // 2
    center_x = len(profile.x_m) // 2
    peak = float(np.max(profile.irradiance_w_m2))
    axes[2].plot(
        profile.x_m / profile.radius_x_m,
        profile.irradiance_w_m2[center_y, :] / peak,
        label=f"x / wx (wx={profile.radius_x_m * 1e3:.4g} mm)",
    )
    axes[2].plot(
        profile.y_m / profile.radius_y_m,
        profile.irradiance_w_m2[:, center_x] / peak,
        label=f"y / wy (wy={profile.radius_y_m * 1e3:.4g} mm)",
        linestyle="--",
    )
    axes[2].axhline(np.exp(-2.0), color="#777777", linewidth=1.0, linestyle=":")
    axes[2].set_title("Normalized center cross-section")
    axes[2].set_xlabel("Normalized local coordinate")
    axes[2].set_ylabel("I / I_peak")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    figure.suptitle(
        f"{beam.profile_kind} / {beam.propagation_model} | "
        f"λ={beam.wavelength_m * 1e9:.6g} nm, P={beam.power_w * 1e3:.6g} mW\n"
        f"Power error={profile.relative_power_error:.3e} | SOURCE FREE SPACE ONLY\n"
        f"READINESS: {hardware_readiness} | PARAXIAL: {paraxial_status}",
        fontsize=11,
        color="#9a3412" if hardware_readiness != "calibrated" else "#166534",
        weight="bold",
    )
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=int(dpi), facecolor="white")
    plt.close(figure)
    return destination
