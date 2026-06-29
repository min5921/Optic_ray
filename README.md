# Custom Beam, Scanner, and Optical Return Simulator

This project places catalog-backed or custom optical components in a 3D assembly and simulates user-defined point, line, and area beams passing through collimator optics and custom scanners, illuminating material-assigned targets, and returning optical power or coherent FMCW signals to a receiver.

## Project Direction

The active v0.2 project definition, component placement model, physical layers, outputs, development phases, validation scenarios, and open hardware decisions are maintained in [`docs/PROJECT_VISION.md`](docs/PROJECT_VISION.md).

Physical conditions and component choices are configuration-driven. Open [`configs/project.yaml`](configs/project.yaml), start from [`configs/baseline_1550nm.yaml`](configs/baseline_1550nm.yaml), then change unit-bearing values such as `1550 nm` or component references directly or through an experiment such as [`configs/experiments/component_swap.example.yaml`](configs/experiments/component_swap.example.yaml).

The accepted provisional defaults are documented in [`docs/specs/INITIAL_BASELINE.md`](docs/specs/INITIAL_BASELINE.md). FreeCAD/STL asset preparation is described in [`docs/specs/COORDINATES_AND_PLACEMENT.md`](docs/specs/COORDINATES_AND_PLACEMENT.md) and [`assets/README.md`](assets/README.md).

For step-by-step instructions on changing wavelength, source, optical components, placement, scanner, STL geometry, materials, receiver settings, outputs, and comparison experiments, read [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md).

The project distinguishes `relative_design`, `absolute_radiometric`, and `coherent_fmcw` accuracy modes. JSON validation contracts are under [`schemas/`](schemas/), while measured calibration/validation data belongs under [`assets/measurements/`](assets/measurements/).

## Phase 0 Quick Start

The first executable Phase 0 milestone validates project, scenario, experiment, component, material, unit, and cross-reference contracts:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
lidarsim validate configs/project.yaml
python -m pytest -q
```

`validate` resolves unit-bearing quantities to SI units/radians, rejects unknown fields and broken catalog/port references, and prints a reproducible physical-configuration SHA-256. Beam propagation and simulation commands are not implemented yet.

## Working Across Computers

Project files are synchronized through a private Git remote. Before starting work on any computer, read `AGENTS.md` and `HANDOFF.md`; the complete setup and handoff routine is in [`docs/MULTI_PC_WORKFLOW.md`](docs/MULTI_PC_WORKFLOW.md).

Machine-local environments, credentials, generated simulation results, and Codex state are intentionally excluded from version control.

The imported coherent FMCW LiDAR source documents are preserved under [`docs/original/coherent-fmcw-lidar-sim-docs/`](docs/original/coherent-fmcw-lidar-sim-docs/).

It combines:

- Gaussian beam propagation with M²
- ABCD matrix optical system modeling
- lens/aperture/mirror/scanner models
- scanner dynamics and time-dependent beam steering
- STL/CAD-based scene visibility
- material-dependent reflection
- rough surface scatterer sampling
- coherent speckle field summation
- FMCW beat signal generation
- FFT/CZT range processing
- range/intensity/speckle/point-cloud visualization
- optional GPU acceleration through backend abstraction

This is **not** a pure ray tracing engine.

Ray tracing is used for:

1. visibility
2. occlusion
3. scanner steering geometry
4. mirror reflection geometry
5. STL hit detection
6. visible surface patch selection

The LiDAR signal is generated from **coherent electric field summation** over surface scatterers.

Core idea:

```text
Scanner motion
    ↓
time-dependent BeamState
    ↓
moving beam footprint on target
    ↓
fixed rough scatterer map
    ↓
changing coherent field sum
    ↓
speckle decorrelation
    ↓
FMCW beat signal per pixel
    ↓
batch FFT
    ↓
range/intensity/speckle image
```

## Development Philosophy

Start with physically validated CPU reference models first. GPU acceleration is added after correctness is established.

Recommended order:

```text
FMCW single target
→ Gaussian beam + M²
→ lens/ABCD/aperture
→ rough surface speckle
→ receiver aperture
→ scanner dynamics
→ scanner-driven speckle decorrelation
→ backend abstraction
→ CuPy batch FFT
→ STL visible patch
→ material model
→ car/mirror/retroreflector scene
→ GPU acceleration for full frame
```

## Important Rules

- Do not treat each STL triangle as one optical scatterer.
- STL triangles are geometry and normal references only.
- Optical scatterers must be sampled separately on visible surface patches.
- Do not sum intensity first if speckle is required.
- Correct speckle calculation:

```text
E_rx = Σ A_i exp(jφ_i)
P_rx = |E_rx|²
```

- Incorrect speckle calculation:

```text
P_rx = Σ P_i
```

- Power and field amplitude must remain distinct:

```text
P ∝ |E|²
E ∝ sqrt(P)
```
