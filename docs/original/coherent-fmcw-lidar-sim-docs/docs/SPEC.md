# Specification

## Project Goal

Build a Python-based coherent FMCW LiDAR forward simulator that can model:

1. beam source and beam propagation
2. M², divergence, waist, line beam, elliptical beam
3. optical elements such as lenses, apertures, mirrors, beam expanders, scanner mirrors
4. time-dependent scanner motion
5. STL/CAD scene geometry
6. material-dependent reflection
7. rough surface speckle
8. coherent field summation
9. FMCW beat signal generation
10. receiver optics and coherent mixing
11. FFT/CZT range processing
12. GPU-accelerated batch processing as an optional backend

## Non-Goal of Initial Version

The initial version is not a full Maxwell solver and should not attempt to model:

- full electromagnetic field solution
- full diffraction around object edges
- polarization-dependent multilayer coating physics
- complete lens aberration from first principles
- nonlinear laser cavity dynamics
- full detector semiconductor physics

These may be added later as specialized modules.

## Core Architecture

```text
Beam source
    ↓
Optical system
    ↓
Scanner dynamics
    ↓
Scene / STL / visible patch
    ↓
Surface scatterer sampling
    ↓
Material / roughness / retroreflector model
    ↓
Complex field coherent sum
    ↓
Receiver optics
    ↓
FMCW beat signal
    ↓
Noise model
    ↓
FFT / CZT / peak detection
    ↓
Range image / intensity image / speckle map / point cloud
```

## Required Python Packages

Base requirements:

```text
numpy
scipy
matplotlib
trimesh
pyvista
pytest
```

Optional GPU requirements:

```text
cupy-cuda12x or cupy-cuda13x
torch
numba
```

GPU packages must be optional. The project must run and pass core tests with NumPy only.

## Units

- Length: meter
- Time: second
- Frequency: Hz
- Optical power: watt
- Wavelength: meter
- Internal angle: radian
- User-facing angle: degree allowed, converted internally to radian
- Complex signal: complex128 for CPU validation, complex64 optional for GPU performance

## Coordinate System

Global coordinate:

- x: forward
- y: lateral
- z: up

Default LiDAR source position:

```text
[0, 0, 0]
```

Default beam direction:

```text
+x
```

Beam local coordinate:

- z': propagation direction
- x': horizontal transverse beam axis
- y': vertical transverse beam axis

## Determinism

All stochastic models must accept a random seed.

This includes:

- scatterer generation
- roughness height map generation
- random phase generation
- scanner jitter
- noise generation
