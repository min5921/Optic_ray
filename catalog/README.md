# Component and Material Catalog

Simulation configs reference stable IDs such as `custom:ideal_collimator_f20` instead of copying every component property into each scenario.

```text
catalog/
├─ components/
│  ├─ custom/
│  └─ thorlabs/
└─ materials/
   └─ custom/
```

Initial records are ideal analytical components. Commercial records will preserve manufacturer, part number, revision, wavelength validity, model level, provenance, tolerances, and any local vendor-asset references.

Changing `component_ref` in a scenario or experiment is the primary component-swap mechanism.
