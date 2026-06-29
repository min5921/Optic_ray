# 사용자 경험·workflow contract

- 상태: 초기 구현 contract
- 작성일: 2026-06-28

## 1. 핵심 사용자 목표

가장 짧은 성공 workflow는 다음과 같다.

```text
project 열기
→ baseline scenario 복제
→ wavelength/component/placement 변경
→ validation
→ run
→ baseline과 비교
→ 3D와 metric 확인
→ report export
```

이 workflow에서 사용자가 Python source code를 수정할 필요가 없어야 한다.

## 2. Project manager

Project view에 다음 정보를 표시한다.

- Active baseline
- Scenario와 experiment
- Catalog·asset search path
- Resolve되지 않거나 누락된 파일
- 마지막 validation·run 상태
- 수정된 config 파일
- Result 존재 여부
- Software·schema version

## 3. Guided setup wizard

단계:

1. Accuracy mode 선택
2. Wavelength·source 선택
3. Optical component 추가 또는 선택
4. Component 배치·연결
5. FreeCAD·STL asset import
6. Scanner pivot·axis·motion 정의
7. Target·material 정의
8. Receiver 정의
9. Output과 comparison baseline 선택
10. Warning과 예상 run cost 검토

Wizard의 모든 단계는 CLI 실행에 사용하는 것과 동일한 versioned YAML을 작성한다.

## 4. Unit-aware input

사용자 입력 field는 다음과 같은 물리량을 허용한다.

```text
1550 nm
10 mW
20 mm
5 deg
10 Hz
```

규칙:

- 모든 field 옆에 unit을 표시한다.
- Unitless input은 dimensionless quantity에만 허용한다.
- 호환되는 unit은 내부 SI/radian 값으로 변환한다.
- Resolved config에는 canonical SI 값을 기록한다.
- 표시 unit을 변경해도 physical config는 바뀌지 않는다.
- Locale에 따른 decimal parsing 차이로 파일이 모호해지지 않아야 한다.

## 5. Validation 경험

Validation message에는 다음을 포함한다.

- Severity: info·warning·error
- Config path 또는 component ID
- 사람이 이해할 수 있는 원인
- 물리적 결과
- 권장 수정 방법
- 실행 차단 여부

예시:

```text
ERROR  optical_assembly.collimator
1550 nm가 선언된 coating 범위 600~1050 nm 밖에 있습니다.
결과: transmission을 신뢰할 수 없습니다.
수정: 호환되는 coating/component를 선택하거나 measured data를 추가하세요.
```

## 6. Component 선택과 교체

Catalog UI는 다음 기능을 지원한다.

- Manufacturer·part-number 검색
- Wavelength·aperture·focal-length filter
- Model-level·data-confidence filter
- Specification 나란히 비교
- Port·placement compatibility preview
- Drop-in·reconnect·reoptimize placement policy
- Provenance와 누락 value 표시

## 7. FreeCAD·STL import wizard

Wizard는 다음 정보를 표시한다.

- Raw mesh bounding box
- 선택한 unit scale과 SI dimension
- Triangle 수와 topology warning
- Axis·origin preview
- Role과 material
- 필요한 경우 scanner pivot·axis
- Optical geometry와 visual geometry 구분 warning
- 승인 전 3D preview

## 8. Run 관리

실행 전에 다음을 표시한다.

- Variant run 수
- 예상 memory·time class
- 선택한 backend·precision
- Cache hit·miss 상태
- 예상 output
- 실행을 막는 warning

실행 중 지원 기능:

- Progress와 현재 variant
- Cancel
- Partial result 보존
- 실패한 variant 재시도
- Log·warning stream
- 지원되는 경우 deterministic resume

## 9. Comparison workspace

다음 정보를 표시한다.

- Baseline과 선택한 variant
- Config diff
- Component·specification diff
- Placement diff
- Beam·footprint·scan overlay
- Link-budget waterfall
- Absolute·relative metric delta
- Uncertainty band
- Confidence badge와 warning

## 10. Reporting

먼저 HTML report를 생성하며 PDF export는 선택 사항이다.

Report 내용:

- Project·scenario·experiment ID
- Effective config와 hash
- Component·data provenance
- Model level과 accuracy mode
- Assumption·warning
- 3D layout snapshot
- 주요 plot과 metric table
- Energy·convergence audit
- Software·schema version
- Run timestamp와 duration

## 11. Recovery와 versioning

- Autosave draft는 authoritative config와 별도로 보관한다.
- Undo·redo는 명시적인 config 변경을 만든다.
- Schema migration은 backup과 migration report를 생성한다.
- 누락된 vendor·local asset은 reference를 삭제하지 않고 보고한다.
- UI state가 physical parameter의 유일한 사본이 되어서는 안 된다.
- Crash recovery가 마지막 valid config를 알리지 않고 덮어쓰지 않는다.

## 12. Usability 승인 test

- 새 사용자가 Python을 수정하지 않고 baseline을 복제하고 변경할 수 있다.
- `nm`, `um`, `m` 표시 unit으로 wavelength를 변경할 수 있다.
- Catalog reference 하나만 바꿔 collimator를 교체할 수 있다.
- Unit이 누락된 STL import를 유용한 message와 함께 차단한다.
- 하나의 workspace에서 baseline과 variant 두 개를 비교할 수 있다.
- 모든 plot에서 source config와 unit을 확인할 수 있다.
- Export한 report만으로 run을 재현할 수 있다.
