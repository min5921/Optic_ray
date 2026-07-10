# UI variant configuration

`lidarsim ui configs/project.yaml`에서 저장한 scenario와 project YAML이 이 directory에 생성된다.

- 원본 baseline은 직접 덮어쓰지 않는다.
- 각 variant project는 CLI에서 다시 `validate`, `optical-train`, `workspace`, `dashboard`로 실행할 수 있다.
- 유지할 설정만 검토 후 Git에 commit한다.
- PNG, CSV, report와 HTML 결과는 `results/ui_runs/`에 생성되며 Git에 추가하지 않는다.
