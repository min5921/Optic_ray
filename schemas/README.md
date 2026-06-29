# Configuration schema

이 directory의 JSON Schema Draft 2020-12 파일은 Phase 0 validation contract를 정의한다.

- `project.schema.json`
- `scenario.schema.json`
- `experiment.schema.json`
- `component.schema.json`
- `material.schema.json`
- `stl_metadata.schema.json`
- `measurement.schema.json`
- `phase0_report.schema.json`
- `common.schema.json`

물리량 field는 다음 중 하나를 입력받는다.

- Field suffix에 해당하는 canonical unit으로 이미 표현된 숫자
- `1550 nm`, `10 mW`, `20 mm`, `5 deg`, `10 Hz`처럼 단위가 포함된 문자열

현재 loader는 물리량을 변경 불가능한 SI/radian resolved config로 변환하고, 기본적으로 알 수 없는 field를 거부하며, catalog·file reference를 확인하고, 사람이 이해할 수 있는 diagnostic을 출력한다.

`phase0_report.schema.json`은 run manifest, accuracy·confidence, energy ledger, convergence와 resolved placement report를 검증한다.
