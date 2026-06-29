# Simulation configuration

모든 물리 조건과 부품 선택은 source code를 수정하지 않고 version이 관리되는 unit-aware configuration 파일에서 변경할 수 있어야 한다.

- `project.yaml`: catalog·asset·measurement 경로, scenario 목록, experiment, 활성 baseline과 표시 단위
- `baseline_1550nm.yaml`: 초기 analytical reference scenario
- `experiments/`: parameter 및 부품 교체 정의

현재 Phase 0 loader가 이 파일을 읽어 schema, unit과 상호 참조를 검증한다.

```powershell
lidarsim validate configs/project.yaml
```

Contract의 상세 내용은 [`../docs/specs/CONFIGURATION_AND_EXPERIMENTS.md`](../docs/specs/CONFIGURATION_AND_EXPERIMENTS.md)를 참고한다.

단계별 사용자 절차는 [`../docs/USER_MANUAL.md`](../docs/USER_MANUAL.md)에 있다.
