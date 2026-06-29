# Measurement Assets

Use this directory for measured data that calibrates or validates real hardware configurations.

Recommended subdirectories:

- `source_beam_profile/`
- `component_transmission/`
- `scanner_calibration/`
- `material_brdf/`
- `receiver_response/`
- `detector_calibration/`

Every dataset requires a metadata sidecar based on [`measurement_metadata.example.yaml`](measurement_metadata.example.yaml). Preserve raw data unchanged and store processed outputs separately.

See [`../../docs/specs/MEASUREMENT_DATA.md`](../../docs/specs/MEASUREMENT_DATA.md).
