"""Receiver aperture and radiometric return APIs."""

from .radiometry import ReceiverReturn, estimate_lambertian_receiver_return, estimate_receiver_returns
from .reciprocal import (
    ReciprocalCenterRayResult,
    ReciprocalClosureResidual,
    ReciprocalPlaneHit,
    ResolvedPlaneFrame,
    trace_reciprocal_center_ray,
)
from .reciprocal_project import (
    ProjectReciprocalReturn,
    RECIPROCAL_ARCHITECTURE,
    evaluate_project_reciprocal_return,
    reverse_ideal_thin_lens_center_ray,
)
from .return_power import (
    ReciprocalReturnPowerResult,
    ReturnPowerLedgerEntry,
    estimate_reciprocal_return_power,
)
from .return_power_project import (
    ProjectReciprocalReturnPower,
    evaluate_project_reciprocal_return_power,
)

__all__ = [
    "ReciprocalCenterRayResult",
    "ReciprocalClosureResidual",
    "ReciprocalPlaneHit",
    "ProjectReciprocalReturn",
    "ProjectReciprocalReturnPower",
    "RECIPROCAL_ARCHITECTURE",
    "ReceiverReturn",
    "ReciprocalReturnPowerResult",
    "ReturnPowerLedgerEntry",
    "ResolvedPlaneFrame",
    "estimate_lambertian_receiver_return",
    "estimate_receiver_returns",
    "evaluate_project_reciprocal_return",
    "evaluate_project_reciprocal_return_power",
    "estimate_reciprocal_return_power",
    "reverse_ideal_thin_lens_center_ray",
    "trace_reciprocal_center_ray",
]
