"""Structured simulation·validation result contract."""

from .accuracy import ReadinessAssessment, assess_readiness
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
from .optical_train import Phase2OpticalTrainReport, build_phase2_optical_train_report

__all__ = [
    "AccuracyReport",
    "ReadinessAssessment",
    "assess_readiness",
    "ConvergenceCheck",
    "ConvergenceReport",
    "EnergyLedger",
    "Phase0Report",
    "RunManifest",
    "build_phase0_report",
    "BeamSample",
    "Phase1BeamReport",
    "build_phase1_beam_report",
    "Phase2OpticalTrainReport",
    "build_phase2_optical_train_report",
    "write_review_html",
]
