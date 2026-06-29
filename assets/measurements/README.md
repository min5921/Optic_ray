# 측정 asset

실제 장비 configuration을 calibration하거나 validation하는 측정 data를 이 directory에 둔다.

권장 하위 directory:

- `source_beam_profile/`
- `component_transmission/`
- `scanner_calibration/`
- `material_brdf/`
- `receiver_response/`
- `detector_calibration/`

모든 dataset에는 [`measurement_metadata.example.yaml`](measurement_metadata.example.yaml)을 기준으로 작성한 metadata sidecar가 필요하다. Raw data는 변경하지 않고 보존하며, 처리된 output은 별도로 저장한다.

Metadata와 referenced data file은 다음 명령으로 검증한다.

```powershell
lidarsim inspect-measurement assets/measurements/<name>.measurement.yaml
```

자세한 내용은 [`../../docs/specs/MEASUREMENT_DATA.md`](../../docs/specs/MEASUREMENT_DATA.md)를 참고한다.
