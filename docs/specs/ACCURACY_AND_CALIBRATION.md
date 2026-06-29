# Accuracy, Confidence, and Calibration Contract

- Status: Initial implementation contract
- Date: 2026-06-28

## 1. Purpose

A numerically precise result is not automatically an accurate prediction of real hardware. Every result must state what it can legitimately represent.

## 2. Accuracy Modes

### `relative_design`

Purpose:

- compare wavelength, components, placement, scanner, target, or receiver variants;
- rank design alternatives;
- identify sensitivity and clipping risk.

Required data:

- internally consistent nominal parameters;
- identical comparison sampling and seeds;
- explicit assumptions.

This is the initial project mode. It does not claim calibrated absolute receiver power.

### `absolute_radiometric`

Purpose:

- predict optical power at the receiver aperture or detector with an uncertainty estimate.

Additional required data:

- calibrated source power/profile;
- component transmission/reflectivity;
- alignment and placement uncertainty;
- wavelength/angle-dependent material BRDF/BSDF;
- receiver aperture/optical-efficiency calibration;
- atmosphere/path model when relevant;
- measurement traceability.

### `coherent_fmcw`

Purpose:

- predict coherent field, speckle, beat waveform, spectrum, range, and optional velocity.

Additional required data:

- phase-consistent optical path;
- fixed scatterer/roughness model;
- laser coherence/linewidth/phase-noise data;
- chirp rate, linearity, timing and sample clock;
- LO/mixer/detector model;
- polarization/coherent-efficiency assumptions.

## 3. Uncertainty Classes

Track these separately:

- `numerical_error`: floating-point, discretization, mesh, quadrature and solver tolerance;
- `model_form_error`: paraxial, Gaussian, BRDF, thin-lens, frozen-scanner or other approximations;
- `input_uncertainty`: catalog tolerance and unknown parameters;
- `placement_uncertainty`: decenter, tilt, gap, pivot and calibration error;
- `measurement_uncertainty`: instrument calibration, noise and repeatability;
- `environmental_uncertainty`: temperature, atmosphere and vibration.

Do not combine them into one number unless the combination assumptions are explicit.

## 4. Confidence Badge

Every report and major result displays:

```yaml
accuracy_mode: relative_design
confidence_level: comparative
calibration_status: uncalibrated
model_level: paraxial_specification
material_data: assumed_lambertian
validity:
  wavelength: 1550 nm
  range: 10 m
warnings: []
```

Allowed confidence labels:

- `illustrative`: idealized demonstration only;
- `comparative`: suitable for relative variant ranking;
- `engineering_estimate`: supported by catalog/tolerance data;
- `calibrated`: fitted and validated against measurement in the stated range;
- `out_of_validity`: result produced for diagnosis but not reliable.

## 5. Calibration Workflow

```text
nominal config
→ import measurement metadata/data
→ verify units, coordinates and wavelength
→ choose calibratable parameters
→ fit on calibration dataset
→ freeze calibrated parameter set
→ validate on independent dataset
→ record residuals and validity range
```

Calibration rules:

- never fit and validate on the same dataset without labeling it;
- preserve nominal, fitted and measured values separately;
- constrain fitted parameters to physical bounds;
- store objective function, optimizer settings and random seed;
- report parameter correlation and identifiability warnings;
- do not use calibration to hide a known model mismatch.

## 6. Comparison Rules

For component or condition comparison:

- keep unchanged inputs identical;
- preserve target sampling and random scatterer map;
- distinguish drop-in placement from reoptimized placement;
- report absolute and relative metric changes;
- report compatibility and validity warnings;
- display uncertainty bands when available.

## 7. Acceptance Gates

### Relative-design release

- analytical beam/placement/energy tests pass;
- identical configs produce identical hashes/results;
- component swaps preserve declared comparison policy;
- numerical convergence is demonstrated;
- result confidence is visible.

### Absolute-radiometric release

- calibration data and metadata are present;
- link-budget audit closes within the declared tolerance;
- independent validation residuals are reported;
- extrapolation outside measured wavelength/angle/range is warned;
- receiver power uncertainty is reported.

### Coherent-FMCW release

- range and phase conventions are validated;
- coherent/incoherent contributions are not mixed silently;
- fixed scatterer identity is reproducible;
- FFT/range and phase-noise tests pass;
- CPU reference is retained for regression.
