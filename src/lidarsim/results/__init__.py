"""Structured simulation·validation result contract."""

from .reports import (
    AccuracyReport,
    ConvergenceCheck,
    ConvergenceReport,
    EnergyLedger,
    Phase0Report,
    RunManifest,
    build_phase0_report,
)

__all__ = [
    "AccuracyReport",
    "ConvergenceCheck",
    "ConvergenceReport",
    "EnergyLedger",
    "Phase0Report",
    "RunManifest",
    "build_phase0_report",
]
