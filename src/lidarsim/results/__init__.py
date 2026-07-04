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
from .html import write_review_html

__all__ = [
    "AccuracyReport",
    "ConvergenceCheck",
    "ConvergenceReport",
    "EnergyLedger",
    "Phase0Report",
    "RunManifest",
    "build_phase0_report",
    "write_review_html",
]
