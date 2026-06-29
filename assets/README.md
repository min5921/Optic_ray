# Simulation Assets

This directory contains user-supplied geometry and related metadata.

```text
assets/
├─ source/freecad/   # optional editable FreeCAD source files
├─ meshes/           # STL files consumed by the simulator
└─ measurements/     # calibration and validation datasets
```

Rules:

- keep editable `.FCStd` source files separate from exported meshes;
- export moving parts and different materials as separate STL files;
- place a matching `.stl.yaml` sidecar next to every STL;
- never infer lens optical performance from STL geometry;
- do not commit vendor files when their license forbids redistribution;
- generated simulation results belong in `outputs/` or `results/`, not here.

See [`../docs/specs/COORDINATES_AND_PLACEMENT.md`](../docs/specs/COORDINATES_AND_PLACEMENT.md) for the import contract.
