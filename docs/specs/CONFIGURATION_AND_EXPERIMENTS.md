# Configuration, Component Swap, and Experiment Contract

- Status: Initial implementation contract
- Date: 2026-06-28

## 1. Goal

The simulator must make it easy to answer questions such as:

- What changes when wavelength is replaced?
- What changes when a collimator, lens, mirror, scanner, target material, or receiver is replaced?
- Which component or parameter dominates beam size, clipping, scan coverage, return power, or SNR?
- How do nominal, tolerance, and measured configurations compare?

No physical equipment value may be hidden as an unexplained constant in simulation code.

## 2. Configuration Layers

The effective simulation configuration is built from explicit layers:

```text
project paths and active baseline
    ↓
schema defaults
    ↓
component catalog records
    ↓
system layout config
    ↓
scenario config
    ↓
experiment overrides
    ↓
validated immutable effective config
```

Each run stores the fully resolved effective config and its content hash.

User-facing quantities may be written as `1550 nm`, `10 mW`, `20 mm`, `5 deg`, or `10 Hz`. Unitless numeric values use the canonical suffix unit for backward compatibility. The resolved config stores SI/radian values.

## 3. Parameter Categories

### Source

- wavelength/spectrum
- optical power
- MFD/waist/M²
- spatial profile
- polarization/coherence

### Optical components

- `component_ref`
- model level
- focal length/prescription
- clear aperture
- coating/transmission
- placement and tolerances

### Scanner

- component/geometry reference
- pivot and axes
- waveform
- angle/frequency/timing
- calibration and errors

### Scene/material

- mesh reference
- placement
- material reference
- BRDF/BSDF/roughness parameters

### Receiver/detector

- component/assembly reference
- aperture/FOV
- optical efficiency
- detector responsivity/noise/saturation

### Numerical model

- accuracy mode and confidence requirements
- model fidelity
- sampling density
- tolerances
- random seed
- backend and dtype

## 4. Canonical and Derived Values

A physical quantity has one canonical input source. Derived values are calculated and reported, not independently edited when doing so would over-constrain the model.

Examples:

- input `wavelength_m`; derive optical frequency
- input source waist and M²; derive Gaussian divergence
- input scanner mechanical angle; derive reflected beam direction
- input aperture diameter; derive aperture area
- input radiometric quantities; derive received power

When a user provides both a canonical value and a measured derived value, the config must declare whether the latter is a validation target or a calibrated override.

## 5. Component Replacement

An assembly references a stable catalog ID instead of copying product data into every scenario.

```yaml
- id: collimator
  component_ref: thorlabs:TC12FC-1550
  placement_ref: placements.collimator
```

Replacing the component changes only `component_ref` unless the new component has incompatible ports or placement constraints. Compatibility validation must report:

- port type mismatch
- wavelength outside valid range
- aperture/profile mismatch
- mechanical envelope/collision change
- missing model data
- changed reference plane or working distance

Each component-swap experiment declares one placement policy:

- `preserve_existing_assembly`: keep the same mount/port gap and observe the direct drop-in result;
- `reconnect_ports`: rebuild port-to-port placement using the new component datums;
- `reoptimize_selected_parameters`: adjust only explicitly listed placement variables.

The initial comparison uses `preserve_existing_assembly`. Automatic reoptimization is never performed silently.

## 6. Override and Sweep Format

Experiments use explicit paths into the baseline config.

```yaml
sweeps:
  - parameter: source.wavelength_m
    values: [1310 nm, 1550 nm]

  - parameter: optical_assembly.elements[id=collimator].component_ref
    values:
      - custom:ideal_collimator_f20
      - custom:ideal_collimator_f35
```

Supported experiment forms:

- one-factor-at-a-time
- Cartesian parameter grid
- paired named variants
- tolerance Monte Carlo
- calibration fit

The experiment runner must calculate the number of runs before execution and require batching or confirmation for a large Cartesian grid.

## 7. Fair Comparison Rules

Variant comparisons use the same, where applicable:

- geometry and coordinate frames
- scan times/pixels
- target sampling
- receiver model
- numerical precision
- random seed/scatterer map
- output metrics

If a component swap changes a reference plane, port location, aperture, or valid wavelength, the comparison report must distinguish physical change from placement incompatibility.

## 8. Comparison Metrics

Initial metrics:

- output beam radius/divergence
- waist position
- clipping and transmission loss
- scan FOV and footprint size
- target peak/mean irradiance
- received aperture power in W and dBm
- relative/absolute change from baseline
- material/path contribution
- runtime and warning count

Later metrics:

- detector photocurrent/SNR
- FMCW range bias/resolution
- speckle statistics
- tolerance distribution

## 9. Result Organization

```text
results/<experiment_id>/
├─ experiment.yaml
├─ resolved_baseline.yaml
├─ variants.csv
├─ metrics.csv
├─ comparison.html
└─ runs/
   └─ <run_id>/
      ├─ effective_config.yaml
      ├─ manifest.json
      └─ result data
```

Generated results remain outside Git by default.

## 10. User Interface Requirements

The analysis UI should support:

- clone scenario
- edit values with visible units
- choose a catalog component from a drop-down
- display nominal/tolerance/measured provenance
- mark one scenario as baseline
- compare two or more variants
- sweep selected parameters
- show invalid combinations before simulation
- export the exact effective configuration
- show confidence/accuracy mode and calibration status

UI edits must produce the same versioned configuration that can be run from the command line. The GUI must not maintain a separate hidden project state.

## 11. Validation

- unknown config fields fail validation by default
- missing units or ambiguous STL scale fail validation
- invalid catalog references fail validation
- derived values are reproducible from canonical inputs
- applying the same override twice produces the same config hash
- baseline and identical variant produce zero metric delta
- random-seed-controlled comparisons are reproducible
- unit-bearing and canonical-SI forms resolve to the same physical config hash
- project paths and active baseline resolve without hidden UI state
