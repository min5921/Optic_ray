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
from .beam import BeamSample, Phase1BeamReport, build_phase1_beam_report

__all__ = [
    "AccuracyReport",
    "ConvergenceCheck",
    "ConvergenceReport",
    "EnergyLedger",
    "Phase0Report",
    "RunManifest",
    "build_phase0_report",
    "BeamSample",
    "Phase1BeamReport",
    "build_phase1_beam_report",
    "write_review_html",
]
