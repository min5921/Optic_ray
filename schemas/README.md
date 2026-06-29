# Configuration Schemas

These JSON Schema Draft 2020-12 files define the Phase 0 validation contracts.

- `project.schema.json`
- `scenario.schema.json`
- `experiment.schema.json`
- `component.schema.json`
- `material.schema.json`
- `stl_metadata.schema.json`
- `measurement.schema.json`
- `common.schema.json`

Quantity fields accept either:

- a number already expressed in the canonical suffix unit, or
- a unit-bearing string such as `1550 nm`, `10 mW`, `20 mm`, `5 deg`, or `10 Hz`.

The future loader will convert quantities to immutable SI/radian resolved configs, reject unknown fields by default, resolve catalog/file references, and emit human-readable diagnostics.

The schema files currently define contracts only; the YAML loader and schema validator are part of Phase 0.
