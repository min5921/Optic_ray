# Simulation configuration

모든 물리 조건과 부품 선택은 source code를 수정하지 않고 version이 관리되는 unit-aware configuration 파일에서 변경할 수 있어야 한다.

- `project.yaml`: catalog·asset·measurement 경로, scenario 목록, experiment, 활성 baseline과 표시 단위
- `baseline_1550nm.yaml`: 초기 analytical reference scenario
- `line_beam_project.example.yaml`: numerical elliptical-Gaussian line-beam project 예제
- `experiments/`: parameter 및 부품 교체 정의
- `ui_runs/`: Streamlit UI가 생성한 검증 가능한 scenario/project variant

현재 loader가 이 파일을 읽어 schema, unit과 상호 참조를 검증하며 Phase 1 beam engine은 active source 설정을 사용한다.

Source의 `catalog_parameter_policy`가 `match_nominal`이면 scenario와 component catalog의 wavelength, power, waist/MFD와 M²가 같아야 한다. 의도적인 변경은 `explicit_override`로 표시해 결과 warning과 provenance에 남긴다.

```powershell
lidarsim validate configs/project.yaml
lidarsim beam configs/project.yaml --z-max-m "20 mm"
lidarsim beam configs/line_beam_project.example.yaml
lidarsim ui configs/project.yaml
```

`ui_runs/`의 YAML은 일회성 result가 아니라 재현 가능한 configuration이다. 검토 후 유지할 variant만 Git에 commit하고, simulation PNG/YAML/HTML 결과는 Git에서 제외되는 `results/ui_runs/`에 둔다.

Contract의 상세 내용은 [`../docs/specs/CONFIGURATION_AND_EXPERIMENTS.md`](../docs/specs/CONFIGURATION_AND_EXPERIMENTS.md)를 참고한다.

단계별 사용자 절차는 [`../docs/USER_MANUAL.md`](../docs/USER_MANUAL.md)에 있다.
