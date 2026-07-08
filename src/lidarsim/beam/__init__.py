"""Beam state와 Gaussian propagation public API."""

from .factory import build_source_beam, default_propagation_distance_m
from .gaussian import (
    BeamState,
    GaussianProfileSample,
    SecondMoment1D,
    divergence_half_angle_rad,
    gaussian_radius_m,
    rayleigh_range_m,
)

__all__ = [
    "BeamState",
    "GaussianProfileSample",
    "SecondMoment1D",
    "build_source_beam",
    "default_propagation_distance_m",
    "divergence_half_angle_rad",
    "gaussian_radius_m",
    "rayleigh_range_m",
]
