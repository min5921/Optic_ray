# User Experience and Workflow Contract

- Status: Initial implementation contract
- Date: 2026-06-28

## 1. Primary User Goal

The shortest successful workflow is:

```text
open project
→ clone baseline scenario
→ change wavelength/component/placement
→ validate
→ run
→ compare with baseline
→ inspect 3D and metrics
→ export report
```

The user must not need to edit Python source code for this workflow.

## 2. Project Manager

The project view displays:

- active baseline;
- scenarios and experiments;
- catalog and asset search paths;
- unresolved/missing files;
- last validation/run status;
- modified config files;
- result availability;
- software/schema version.

## 3. Guided Setup Wizard

Steps:

1. choose accuracy mode;
2. choose wavelength/source;
3. add or select optical components;
4. place/connect components;
5. import FreeCAD/STL assets;
6. define scanner pivot/axis/motion;
7. define target/material;
8. define receiver;
9. select outputs and comparison baseline;
10. review warnings and estimated run cost.

Every wizard step writes the same versioned YAML used by CLI execution.

## 4. Unit-aware Input

User-facing fields accept quantities such as:

```text
1550 nm
10 mW
20 mm
5 deg
10 Hz
```

Rules:

- units are visible next to every field;
- unitless input is accepted only for dimensionless quantities;
- compatible units are converted to internal SI/radian values;
- resolved config records canonical SI values;
- display units can be changed without changing the physical config;
- locale-dependent decimal parsing must not make files ambiguous.

## 5. Validation Experience

Validation messages contain:

- severity: info/warning/error;
- config path or component ID;
- human-readable cause;
- physical consequence;
- suggested correction;
- whether execution is blocked.

Example:

```text
ERROR  optical_assembly.collimator
1550 nm is outside the declared coating range 600-1050 nm.
Result: transmission cannot be trusted.
Fix: choose a compatible coating/component or add measured data.
```

## 6. Component Selection and Swap

Catalog UI supports:

- manufacturer/part-number search;
- wavelength/aperture/focal-length filters;
- model-level and data-confidence filters;
- side-by-side specification comparison;
- port/placement compatibility preview;
- drop-in/reconnect/reoptimize placement policy;
- visible provenance and missing values.

## 7. FreeCAD/STL Import Wizard

The wizard displays:

- raw mesh bounding box;
- selected unit scale and SI dimensions;
- triangle count and topology warnings;
- axis/origin preview;
- role and material;
- scanner pivot/axis when applicable;
- optical-vs-visual geometry warning;
- 3D preview before acceptance.

## 8. Run Management

Before execution show:

- number of variant runs;
- estimated memory/time class;
- selected backend/precision;
- cache hit/miss status;
- expected outputs;
- blocking warnings.

During execution support:

- progress and current variant;
- cancel;
- partial result preservation;
- retry failed variants;
- log and warning stream;
- deterministic resume when supported.

## 9. Comparison Workspace

Display:

- baseline and selected variants;
- config diff;
- component/specification diff;
- placement diff;
- beam/footprint/scan overlays;
- link-budget waterfall;
- absolute and relative metric delta;
- uncertainty bands;
- confidence badges and warnings.

## 10. Reporting

Generate an HTML report first; PDF export is optional.

Report contents:

- project/scenario/experiment IDs;
- effective configs and hashes;
- component/data provenance;
- model level and accuracy mode;
- assumptions/warnings;
- 3D layout snapshot;
- key plots and metric tables;
- energy/convergence audit;
- software/schema version;
- run timestamp and duration.

## 11. Recovery and Versioning

- autosave drafts separately from authoritative config;
- undo/redo produces explicit config changes;
- schema migrations create backups and migration reports;
- missing vendor/local assets are reported without deleting references;
- UI state is never the only copy of physical parameters;
- crash recovery never overwrites the last valid config silently.

## 12. Usability Acceptance Tests

- a new user can clone and modify the baseline without Python edits;
- wavelength can be changed with `nm`, `um`, or `m` display units;
- swapping a collimator requires changing one catalog reference;
- importing an STL with missing units is blocked with a useful message;
- baseline and two variants can be compared in one workspace;
- every plotted result can reveal its source config and units;
- an exported report is sufficient to reproduce the run.
