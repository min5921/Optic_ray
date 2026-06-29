# Simulation Configurations

All physical conditions and component choices must be editable through versioned, unit-aware configuration files rather than source-code changes.

- `project.yaml`: catalog/asset/measurement paths, scenario list, experiments, active baseline and display units
- `baseline_1550nm.yaml`: initial analytical reference scenario
- `experiments/`: parameter and component-swap definitions

The files are contracts for the upcoming Phase 0 loader. They are not executable until the configuration schema and parser are implemented.

See [`../docs/specs/CONFIGURATION_AND_EXPERIMENTS.md`](../docs/specs/CONFIGURATION_AND_EXPERIMENTS.md).

The step-by-step user workflow is in [`../docs/USER_MANUAL.md`](../docs/USER_MANUAL.md).
