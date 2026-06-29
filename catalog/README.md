# 부품·재질 catalog

Simulation config는 각 scenario에 모든 부품 속성을 복사하지 않고 `custom:ideal_collimator_f20` 같은 안정적인 ID를 참조한다.

```text
catalog/
├─ components/
│  ├─ custom/
│  └─ thorlabs/
└─ materials/
   └─ custom/
```

초기 record는 analytical ideal component다. 향후 commercial record에는 manufacturer, part number, revision, 유효 wavelength, model level, provenance, tolerance와 local vendor asset reference를 보존한다.

Scenario나 experiment의 `component_ref`를 변경하는 것이 기본 부품 교체 방법이다.
