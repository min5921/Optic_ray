"""Paraxial optical element와 transmitter train 계산 API."""

from .abcd import ABCDMatrix, apply_abcd_to_beam
from .aperture import (
    ApertureClipResult,
    circular_aperture_clip,
    circular_aperture_transmission_fraction,
)
from .mirror import (
    MirrorClipResult,
    MirrorInteractionResult,
    interact_flat_mirror,
    rectangular_mirror_clip,
    reflect_vector,
)
from .train import OpticalTrainResult, propagate_transmitter_train

__all__ = [
    "ABCDMatrix",
    "ApertureClipResult",
    "MirrorClipResult",
    "MirrorInteractionResult",
    "OpticalTrainResult",
    "apply_abcd_to_beam",
    "circular_aperture_clip",
    "circular_aperture_transmission_fraction",
    "interact_flat_mirror",
    "rectangular_mirror_clip",
    "reflect_vector",
    "propagate_transmitter_train",
]
