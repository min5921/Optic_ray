# Measurement Data and Traceability Contract

- Status: Initial implementation contract
- Date: 2026-06-28

## 1. Purpose

Measured data is required to move from relative design comparison toward calibrated prediction of real hardware.

## 2. Directory Layout

```text
assets/measurements/
├─ source_beam_profile/
├─ component_transmission/
├─ scanner_calibration/
├─ material_brdf/
├─ receiver_response/
└─ detector_calibration/
```

Each dataset includes a data file and metadata sidecar.

## 3. Required Metadata

```yaml
schema_version: 1
measurement_id: lab:source_profile_001
measurement_type: source_beam_profile
data_file: source_profile_001.csv

conditions:
  wavelength: 1550 nm
  temperature: 23 degC
  distance: 1 m

instrument:
  manufacturer: null
  model: null
  serial_number: null
  calibration_date: null

uncertainty:
  type: standard
  value: null
  confidence: null

coordinate_frame: measurement_frame
units: {}
acquired_at: null
operator: null
processing: []
source_hash: null
notes: null
```

## 4. Dataset Types

### Source beam profile

- x/y coordinates;
- irradiance or normalized intensity;
- reference plane/distance;
- total power;
- background/dark correction;
- beam-width convention;
- optional wavefront/phase.

### Component transmission

- wavelength;
- angle/polarization when relevant;
- input/output power;
- uncertainty;
- component revision and orientation.

### Scanner calibration

- command/time;
- measured angle or hit position;
- forward/backward direction;
- temperature/frequency/load;
- fit model and residuals.

### Material BRDF/BSDF

- wavelength;
- incident and outgoing angles;
- polarization when available;
- radiometric quantity and normalization;
- sample preparation/roughness;
- uncertainty.

### Receiver/detector response

- aperture/optical train configuration;
- wavelength/FOV/angle;
- power/photocurrent/voltage;
- gain/bandwidth/integration time;
- dark/noise/saturation data.

## 5. Import Rules

- never infer missing units;
- preserve raw data unchanged;
- store processed data separately with processing history;
- validate coordinate orientation and reference plane;
- do not extrapolate wavelength/angle/range silently;
- interpolation method and validity range are explicit;
- missing uncertainty lowers the result confidence level;
- content hashes connect results to exact inputs.

## 6. Calibration and Validation Split

Datasets have one role:

- `calibration`: parameter fitting;
- `validation`: independent performance check;
- `monitoring`: drift/repeatability;
- `reference`: visualization or qualitative comparison.

One dataset may not be relabeled silently after seeing results.

## 7. Comparison Output

Measurement comparison shows:

- simulation and measurement overlay;
- residual and relative error;
- uncertainty band;
- fit/validation dataset role;
- validity range;
- parameter values before/after calibration;
- confidence label;
- unresolved bias or model mismatch.
