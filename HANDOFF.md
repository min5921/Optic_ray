# Project Handoff

Last updated: 2026-06-28 (Asia/Seoul)

## Current State

- The active project direction is defined in `docs/PROJECT_VISION.md` Draft v0.2.
- The original coherent FMCW LiDAR source package is preserved under `docs/original/coherent-fmcw-lidar-sim-docs/`.
- Multi-computer Git, Codex, line-ending, secret, and generated-output conventions are configured.
- GitHub remote `origin` is connected to `https://github.com/min5921/Optic_ray.git`, and `main` is synchronized.
- No simulator source code has been implemented yet.
- The project focus is the 3D placement of catalog-backed or custom optical components, user-defined point/line/area beams, collimator optics, custom scanners, target interaction, and receiver return analysis.
- Draft v0.2 adds model-fidelity contracts, commercial component catalogs, optical/CAD import, coordinate frames, rigid transforms, optical ports, placement constraints, structured results, visualization, and tolerance analysis.
- Provisional Phase 0-5 defaults are accepted in `docs/specs/INITIAL_BASELINE.md`; all values remain replaceable through configuration.
- `configs/baseline_1550nm.yaml` and an example wavelength/collimator swap experiment define the initial configuration workflow.
- `configs/project.yaml` now collects catalog, asset, measurement, scenario, experiment, baseline, result, display-unit, and UI settings.
- User-facing quantity values accept explicit units such as `1550 nm`, `10 mW`, `20 mm`, `5 deg`, and `10 Hz`.
- FreeCAD source and STL mesh folders, STL sidecar metadata, and initial ideal component/material catalog records are prepared.
- Draft JSON Schema contracts cover project, scenario, experiment, component, material, STL metadata, and measurement metadata.
- Accuracy/calibration, UX, energy/convergence, and measurement-data contracts are documented; measurement asset templates are prepared.
- `docs/USER_MANUAL.md` explains every planned user-editable condition, component replacement, FreeCAD/STL workflow, experiment comparison, and future CLI workflow.
- The active target is Phase 0: configuration/catalog validation, coordinate/placement primitives, STL metadata loading, and a minimal viewer skeleton.
- The Python virtual environment and dependencies have not been installed or verified yet.

## Decisions to Preserve

- `docs/PROJECT_VISION.md` defines the active scope and order; the original documents remain physics references.
- The radiometric received-power path is validated before adding coherent FMCW and speckle layers.
- `relative_design` is the initial accuracy mode; `absolute_radiometric` requires calibrated input/path/material/receiver data, and `coherent_fmcw` adds phase/coherence requirements.
- No wavelength, component, scanner, target, receiver, or material value is hard-coded in simulation logic; scenarios and experiments supply them.
- STL is the initial user geometry exchange format. STL units, role, material, placement, and scanner pivot/axis come from explicit YAML sidecar metadata.
- Lens STL is mechanical/visual geometry only; its optical behavior comes from an ideal, catalog, prescription, or measured model.
- CPU correctness and analytical validation come before optional GPU acceleration.
- Project state moves between computers through Git; credentials and machine-local Codex state do not.
- Conversation history may be opened with the same OpenAI account, but this file remains the durable source of continuation context.

## Best Next Action

Implement the Phase 0 unit-aware YAML loader and JSON Schema validator for `configs/project.yaml`, resolve catalog/assets into an immutable SI config, then add coordinate/placement primitives and STL/measurement metadata validation.

## Verification

- `docs/PROJECT_VISION.md` reviewed and expanded to Draft v0.2, including optical component placement and commercial/custom optical-system inputs.
- Configuration-driven condition changes, component swaps, accepted initial defaults, and FreeCAD/STL workflow are documented.
- User-facing configuration and replacement manual added and linked from the project entry points.
- Baseline/experiment YAML, ideal component/material catalog records, and asset folders are present but not executable yet.
- JSON Schema files are syntactically valid but are not wired to a YAML/schema runtime yet.
- Original documents remain preserved under `docs/original/coherent-fmcw-lidar-sim-docs/`.
- Git safety files and multi-computer workflow added.
- Local `main` is configured to track `origin/main` on GitHub.
- Simulator tests: not available yet because Phase 1 has not been implemented.

## Session Update Template

When ending a future session, replace the current-state sections above and record:

- What changed
- Important decisions and assumptions
- Tests run and their results
- Known issues or uncommitted work
- The single best next action
